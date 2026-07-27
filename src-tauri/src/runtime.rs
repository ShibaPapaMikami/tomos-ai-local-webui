use std::fs;
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
    InvalidBundledRuntime,
    MissingPython,
    PortInUse,
    ServerExited,
    Timeout,
}

impl RuntimeError {
    pub fn code(&self) -> &'static str {
        match self {
            Self::InvalidBundledRuntime => "invalid_bundled_runtime",
            Self::MissingPython => "missing_python",
            Self::PortInUse => "port_in_use",
            Self::ServerExited => "server_exited",
            Self::Timeout => "timeout",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimePaths {
    pub resource_root: PathBuf,
    pub python: PathBuf,
    pub server: PathBuf,
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

pub fn resolve_runtime_paths(
    resource_dir: &Path,
    development_override: Option<&Path>,
) -> Result<RuntimePaths, RuntimeError> {
    let resource_dir = canonical_directory(resource_dir)?;
    #[cfg(feature = "development-runtime-override")]
    let resolution_root = development_override.unwrap_or(&resource_dir);
    #[cfg(not(feature = "development-runtime-override"))]
    let _ = development_override;
    #[cfg(not(feature = "development-runtime-override"))]
    let resolution_root = &resource_dir;
    let resolution_root = canonical_directory(resolution_root)?;

    let resource_root = canonical_directory(&resolution_root.join("tomos"))?;
    if !resource_root.starts_with(&resolution_root) {
        return Err(RuntimeError::InvalidBundledRuntime);
    }

    let server = canonical_regular_file(&resource_root.join("server.py"), &resource_root)?;

    let python_root = canonical_directory(&resolution_root.join("python"))?;
    let python_bin = canonical_directory(&python_root.join("bin"))?;
    let python = python_bin
        .join("python3")
        .canonicalize()
        .map_err(|_| RuntimeError::InvalidBundledRuntime)?;
    if !python.is_file() || !python.starts_with(&python_root) || !is_executable(&python) {
        return Err(RuntimeError::InvalidBundledRuntime);
    }

    Ok(RuntimePaths {
        resource_root,
        python,
        server,
    })
}

fn canonical_directory(path: &Path) -> Result<PathBuf, RuntimeError> {
    let metadata = fs::symlink_metadata(path).map_err(|_| RuntimeError::InvalidBundledRuntime)?;
    if metadata.file_type().is_symlink() || !metadata.is_dir() {
        return Err(RuntimeError::InvalidBundledRuntime);
    }
    path.canonicalize()
        .map_err(|_| RuntimeError::InvalidBundledRuntime)
}

fn canonical_regular_file(path: &Path, parent: &Path) -> Result<PathBuf, RuntimeError> {
    let metadata = fs::symlink_metadata(path).map_err(|_| RuntimeError::InvalidBundledRuntime)?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(RuntimeError::InvalidBundledRuntime);
    }
    let canonical = path
        .canonicalize()
        .map_err(|_| RuntimeError::InvalidBundledRuntime)?;
    if !canonical.is_file() || !canonical.starts_with(parent) {
        return Err(RuntimeError::InvalidBundledRuntime);
    }
    Ok(canonical)
}

#[cfg(unix)]
fn is_executable(path: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;

    fs::metadata(path)
        .map(|metadata| metadata.permissions().mode() & 0o111 != 0)
        .unwrap_or(false)
}

#[cfg(not(unix))]
fn is_executable(_path: &Path) -> bool {
    true
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

fn build_server_command(paths: &RuntimePaths) -> Command {
    let mut command = Command::new(&paths.python);
    command
        .arg("-B")
        .arg(&paths.server)
        .arg("--host")
        .arg(TOMOS_HOST)
        .arg("--port")
        .arg(TOMOS_PORT.to_string())
        .current_dir(&paths.resource_root)
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    command
}

impl RuntimeSupervisor {
    pub fn start(&self, paths: &RuntimePaths) -> Result<RuntimeOwnership, RuntimeError> {
        match probe_port() {
            PortState::TomosReady => {
                *self.ownership.lock().expect("ownership lock") = Some(RuntimeOwnership::Reused);
                return Ok(RuntimeOwnership::Reused);
            }
            PortState::Occupied => return Err(RuntimeError::PortInUse),
            PortState::Free => {}
        }

        let child = build_server_command(paths)
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
    use std::fs;
    use std::sync::atomic::{AtomicUsize, Ordering};

    static FIXTURE_COUNTER: AtomicUsize = AtomicUsize::new(0);

    struct RuntimeFixture {
        root: PathBuf,
    }

    impl RuntimeFixture {
        fn valid() -> Self {
            let root = std::env::temp_dir().join(format!(
                "tomos-runtime-test-{}-{}",
                std::process::id(),
                FIXTURE_COUNTER.fetch_add(1, Ordering::Relaxed),
            ));
            let resources = root.join("Resources");
            fs::create_dir_all(resources.join("tomos")).expect("create TOMOS resource fixture");
            fs::create_dir_all(resources.join("python/bin")).expect("create Python resource fixture");
            fs::write(resources.join("tomos/server.py"), "# fixture\n")
                .expect("write server fixture");
            fs::write(resources.join("python/bin/python3"), "# fixture\n")
                .expect("write Python fixture");
            set_executable(&resources.join("python/bin/python3"), true);
            Self { root }
        }

        fn with_external_python() -> Self {
            let fixture = Self::valid();
            let resources = fixture.resources();
            let external_python = fixture.root.join("external-python3");
            fs::write(&external_python, "# external fixture\n").expect("write external Python fixture");
            let bundled_python = resources.join("python/bin/python3");
            fs::remove_file(&bundled_python).expect("remove bundled Python fixture");
            create_file_symlink(&external_python, &bundled_python);
            fixture
        }

        fn without_python() -> Self {
            let fixture = Self::valid();
            fs::remove_file(fixture.resources().join("python/bin/python3"))
                .expect("remove bundled Python fixture");
            fixture
        }

        fn symlinked_resources(&self) -> PathBuf {
            let resource_link = self.root.join("Resources-link");
            create_directory_symlink(&self.resources(), &resource_link);
            resource_link
        }

        fn with_tomos_symlink() -> Self {
            let fixture = Self::valid();
            let resources = fixture.resources();
            let tomos = resources.join("tomos");
            let real_tomos = resources.join("tomos-real");
            fs::rename(&tomos, &real_tomos).expect("move TOMOS resource fixture");
            create_directory_symlink(&real_tomos, &tomos);
            fixture
        }

        fn with_server_symlink() -> Self {
            let fixture = Self::valid();
            let tomos = fixture.resources().join("tomos");
            let server = tomos.join("server.py");
            let real_server = tomos.join("server-real.py");
            fs::rename(&server, &real_server).expect("move server fixture");
            create_file_symlink(&real_server, &server);
            fixture
        }

        fn with_python_parent_symlink() -> Self {
            let fixture = Self::valid();
            let python = fixture.resources().join("python");
            let bin = python.join("bin");
            let real_bin = python.join("bin-real");
            fs::rename(&bin, &real_bin).expect("move Python parent fixture");
            create_directory_symlink(&real_bin, &bin);
            fixture
        }

        fn with_internal_python_symlink() -> Self {
            let fixture = Self::valid();
            let bin = fixture.resources().join("python/bin");
            let python = bin.join("python3");
            let python_target = bin.join("python3.11");
            fs::rename(&python, &python_target).expect("move Python fixture");
            create_file_symlink(&python_target, &python);
            fixture
        }

        #[cfg(unix)]
        fn without_executable_python() -> Self {
            let fixture = Self::valid();
            set_executable(&fixture.resources().join("python/bin/python3"), false);
            fixture
        }

        fn resources(&self) -> PathBuf {
            self.root
                .join("Resources")
                .canonicalize()
                .expect("canonicalize resource fixture")
        }
    }

    impl Drop for RuntimeFixture {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    #[cfg(unix)]
    fn create_file_symlink(target: &Path, link: &Path) {
        std::os::unix::fs::symlink(target, link).expect("create external Python symlink");
    }

    #[cfg(windows)]
    fn create_file_symlink(target: &Path, link: &Path) {
        std::os::windows::fs::symlink_file(target, link)
            .expect("create external Python symlink");
    }

    #[cfg(unix)]
    fn create_directory_symlink(target: &Path, link: &Path) {
        std::os::unix::fs::symlink(target, link).expect("create resource directory symlink");
    }

    #[cfg(windows)]
    fn create_directory_symlink(target: &Path, link: &Path) {
        std::os::windows::fs::symlink_dir(target, link)
            .expect("create resource directory symlink");
    }

    #[cfg(unix)]
    fn set_executable(path: &Path, executable: bool) {
        use std::os::unix::fs::PermissionsExt;

        let mode = if executable { 0o755 } else { 0o644 };
        fs::set_permissions(path, fs::Permissions::from_mode(mode))
            .expect("set Python fixture permissions");
    }

    #[cfg(windows)]
    fn set_executable(_path: &Path, _executable: bool) {}

    #[test]
    fn resolves_bundled_runtime_inside_resource_dir() {
        let fixture = RuntimeFixture::valid();
        let paths = resolve_runtime_paths(&fixture.resources(), None).unwrap();
        assert!(paths.python.starts_with(fixture.resources()));
        assert!(paths.resource_root.starts_with(fixture.resources()));
        assert!(paths.server.is_absolute());
        assert!(paths.server.starts_with(&paths.resource_root));
    }

    #[test]
    fn rejects_python_outside_resource_dir() {
        let fixture = RuntimeFixture::with_external_python();
        assert_eq!(
            resolve_runtime_paths(&fixture.resources(), None),
            Err(RuntimeError::InvalidBundledRuntime)
        );
    }

    #[test]
    fn rejects_missing_bundled_python() {
        let fixture = RuntimeFixture::without_python();
        assert_eq!(
            resolve_runtime_paths(&fixture.resources(), None),
            Err(RuntimeError::InvalidBundledRuntime)
        );
    }

    #[test]
    fn rejects_symlinked_resource_dir() {
        let fixture = RuntimeFixture::valid();
        assert_eq!(
            resolve_runtime_paths(&fixture.symlinked_resources(), None),
            Err(RuntimeError::InvalidBundledRuntime)
        );
    }

    #[test]
    fn rejects_tomos_symlink() {
        let fixture = RuntimeFixture::with_tomos_symlink();
        assert_eq!(
            resolve_runtime_paths(&fixture.resources(), None),
            Err(RuntimeError::InvalidBundledRuntime)
        );
    }

    #[test]
    fn rejects_server_symlink() {
        let fixture = RuntimeFixture::with_server_symlink();
        assert_eq!(
            resolve_runtime_paths(&fixture.resources(), None),
            Err(RuntimeError::InvalidBundledRuntime)
        );
    }

    #[test]
    fn rejects_python_parent_symlink() {
        let fixture = RuntimeFixture::with_python_parent_symlink();
        assert_eq!(
            resolve_runtime_paths(&fixture.resources(), None),
            Err(RuntimeError::InvalidBundledRuntime)
        );
    }

    #[test]
    fn accepts_python_symlink_inside_resource_dir() {
        let fixture = RuntimeFixture::with_internal_python_symlink();
        let paths = resolve_runtime_paths(&fixture.resources(), None).unwrap();
        assert_eq!(
            paths.python,
            fixture
                .resources()
                .join("python/bin/python3.11")
                .canonicalize()
                .expect("canonicalize internal Python target")
        );
    }

    #[cfg(unix)]
    #[test]
    fn rejects_non_executable_python() {
        let fixture = RuntimeFixture::without_executable_python();
        assert_eq!(
            resolve_runtime_paths(&fixture.resources(), None),
            Err(RuntimeError::InvalidBundledRuntime)
        );
    }

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
    fn server_command_disables_bytecode_writes() {
        let fixture = RuntimeFixture::valid();
        let paths = resolve_runtime_paths(&fixture.resources(), None).expect("resolve fixture");
        let command = build_server_command(&paths);
        let args: Vec<_> = command.get_args().collect();
        let envs: Vec<_> = command.get_envs().collect();

        assert_eq!(args.first().and_then(|value| value.to_str()), Some("-B"));
        assert!(envs.iter().any(|(key, value)| {
            key.to_str() == Some("PYTHONDONTWRITEBYTECODE")
                && value.and_then(|item| item.to_str()) == Some("1")
        }));
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
        assert_eq!(
            RuntimeError::InvalidBundledRuntime.code(),
            "invalid_bundled_runtime"
        );
        assert_eq!(RuntimeError::MissingPython.code(), "missing_python");
        assert_eq!(RuntimeError::PortInUse.code(), "port_in_use");
        assert_eq!(RuntimeError::ServerExited.code(), "server_exited");
        assert_eq!(RuntimeError::Timeout.code(), "timeout");
    }
}
