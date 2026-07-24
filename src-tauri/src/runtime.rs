use std::env;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

pub const TOMOS_HOST: &str = "127.0.0.1";
pub const TOMOS_PORT: u16 = 54876;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PortState {
    Free,
    TomosReady,
    Occupied,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RuntimeOwnership {
    Reused,
    Owned,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RuntimeError {
    MissingResourceRoot,
    MissingPython,
    PortInUse,
    ServerExited,
    Timeout,
}

impl RuntimeError {
    pub fn code(&self) -> &'static str {
        match self {
            Self::MissingResourceRoot => "missing_resource_root",
            Self::MissingPython => "missing_python",
            Self::PortInUse => "port_in_use",
            Self::ServerExited => "server_exited",
            Self::Timeout => "timeout",
        }
    }
}

pub struct RuntimeSupervisor {
    child: Mutex<Option<Child>>,
    ownership: Mutex<Option<RuntimeOwnership>>,
}

impl Default for RuntimeSupervisor {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            ownership: Mutex::new(None),
        }
    }
}

pub fn resolve_resource_root() -> Result<PathBuf, RuntimeError> {
    if let Some(configured) = env::var_os("TOMOS_RESOURCE_ROOT") {
        let root = PathBuf::from(configured);
        if root.join("server.py").is_file() {
            return Ok(root);
        }
        return Err(RuntimeError::MissingResourceRoot);
    }
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(Path::to_path_buf)
        .ok_or(RuntimeError::MissingResourceRoot)?;
    if root.join("server.py").is_file() {
        Ok(root)
    } else {
        Err(RuntimeError::MissingResourceRoot)
    }
}

pub fn classify_health_response(response: &str) -> PortState {
    let compact = response.replace(' ', "");
    if (response.starts_with("HTTP/1.0 200") || response.starts_with("HTTP/1.1 200"))
        && compact.contains("\"appVersion\"")
    {
        PortState::TomosReady
    } else {
        PortState::Occupied
    }
}

fn probe_port() -> PortState {
    let address = SocketAddr::from(([127, 0, 0, 1], TOMOS_PORT));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(250)) else {
        return PortState::Free;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(4)));
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: {TOMOS_HOST}:{TOMOS_PORT}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return PortState::Occupied;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return PortState::Occupied;
    }
    classify_health_response(&response)
}

impl RuntimeSupervisor {
    pub fn start(&self, resource_root: &Path) -> Result<RuntimeOwnership, RuntimeError> {
        match probe_port() {
            PortState::TomosReady => {
                *self.ownership.lock().expect("ownership lock") = Some(RuntimeOwnership::Reused);
                return Ok(RuntimeOwnership::Reused);
            }
            PortState::Occupied => return Err(RuntimeError::PortInUse),
            PortState::Free => {}
        }

        let python = env::var("TOMOS_PYTHON").unwrap_or_else(|_| "python3".to_string());
        let child = Command::new(&python)
            .arg("server.py")
            .arg("--host")
            .arg(TOMOS_HOST)
            .arg("--port")
            .arg(TOMOS_PORT.to_string())
            .current_dir(resource_root)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| {
                if error.kind() == std::io::ErrorKind::NotFound {
                    RuntimeError::MissingPython
                } else {
                    RuntimeError::ServerExited
                }
            })?;

        *self.child.lock().expect("child lock") = Some(child);
        *self.ownership.lock().expect("ownership lock") = Some(RuntimeOwnership::Owned);

        let deadline = Instant::now() + Duration::from_secs(30);
        while Instant::now() < deadline {
            {
                let mut child_guard = self.child.lock().expect("child lock");
                if let Some(child) = child_guard.as_mut() {
                    if child
                        .try_wait()
                        .map_err(|_| RuntimeError::ServerExited)?
                        .is_some()
                    {
                        child_guard.take();
                        return Err(RuntimeError::ServerExited);
                    }
                }
            }
            if probe_port() == PortState::TomosReady {
                return Ok(RuntimeOwnership::Owned);
            }
            thread::sleep(Duration::from_millis(250));
        }

        self.stop_owned();
        Err(RuntimeError::Timeout)
    }

    pub fn stop_owned(&self) {
        let ownership = *self.ownership.lock().expect("ownership lock");
        if ownership != Some(RuntimeOwnership::Owned) {
            return;
        }
        if let Some(mut child) = self.child.lock().expect("child lock").take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        *self.ownership.lock().expect("ownership lock") = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_tomos_health_payload() {
        let response = "HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n{\"ok\":true,\"appVersion\":\"0.8.219\"}";
        assert_eq!(classify_health_response(response), PortState::TomosReady);
    }

    #[test]
    fn accepts_tomos_health_when_ollama_is_offline() {
        let response = "HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n{\"ok\":false,\"appVersion\":\"0.8.219\",\"ollama\":\"offline\"}";
        assert_eq!(classify_health_response(response), PortState::TomosReady);
    }

    #[test]
    fn rejects_foreign_http_payload() {
        let response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nhello";
        assert_eq!(classify_health_response(response), PortState::Occupied);
    }

    #[test]
    fn rejects_error_health_payload() {
        let response = "HTTP/1.1 500 Internal Server Error\r\n\r\n{\"ok\":false,\"appVersion\":\"0.8.219\"}";
        assert_eq!(classify_health_response(response), PortState::Occupied);
    }

    #[test]
    fn maps_runtime_errors_to_fixed_codes() {
        assert_eq!(RuntimeError::MissingPython.code(), "missing_python");
        assert_eq!(RuntimeError::PortInUse.code(), "port_in_use");
        assert_eq!(RuntimeError::ServerExited.code(), "server_exited");
        assert_eq!(RuntimeError::Timeout.code(), "timeout");
    }
}
