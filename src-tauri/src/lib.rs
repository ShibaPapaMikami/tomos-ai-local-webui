mod runtime;

use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    thread,
    time::Duration,
};
#[cfg(feature = "development-runtime-override")]
use std::{env, path::PathBuf};
use tauri::{
    webview::PageLoadEvent, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent,
};

use runtime::{resolve_runtime_paths, RuntimeError, RuntimeSupervisor};

const SECOND_INSTANCE_FOCUS_DELAY_MS: u64 = 250;

#[cfg(feature = "development-runtime-override")]
fn development_resource_override() -> Option<PathBuf> {
    env::var_os("TOMOS_RESOURCE_ROOT").map(PathBuf::from)
}

#[cfg(not(feature = "development-runtime-override"))]
fn development_resource_override() -> Option<std::path::PathBuf> {
    None
}

fn refocus_after_second_instance(window: tauri::WebviewWindow) {
    let _ = window.show();
    let _ = window.unminimize();
    let _ = window.set_focus();

    tauri::async_runtime::spawn_blocking(move || {
        thread::sleep(Duration::from_millis(SECOND_INSTANCE_FOCUS_DELAY_MS));
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    });
}

pub fn run() {
    let supervisor = Arc::new(RuntimeSupervisor::default());
    let setup_supervisor = Arc::clone(&supervisor);
    let runtime_started = Arc::new(AtomicBool::new(false));

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                refocus_after_second_instance(window);
            }
        }))
        .setup(move |app| {
            let runtime = Arc::clone(&setup_supervisor);
            let development_override = development_resource_override();
            let runtime_paths = app
                .path()
                .resource_dir()
                .map_err(|_| RuntimeError::InvalidBundledRuntime)
                .and_then(|resource_dir| {
                    resolve_runtime_paths(&resource_dir, development_override.as_deref())
                });
            WebviewWindowBuilder::new(
                app,
                "main",
                WebviewUrl::App("desktop-starting.html".into()),
            )
            .title("TOMOS AI")
            .inner_size(1280.0, 820.0)
            .min_inner_size(960.0, 640.0)
            .center()
            .on_navigation(|url| {
                let bundled_asset =
                    url.scheme() == "tauri" || url.host_str() == Some("tauri.localhost");
                let tomos_local = url.scheme() == "http"
                    && url.host_str() == Some("127.0.0.1")
                    && url.port_or_known_default() == Some(54876);
                bundled_asset || tomos_local
            })
            .on_page_load(move |window, payload| {
                if payload.event() != PageLoadEvent::Finished
                    || runtime_started.swap(true, Ordering::SeqCst)
                {
                    return;
                }
                let runtime = Arc::clone(&runtime);
                let runtime_paths = runtime_paths.clone();
                tauri::async_runtime::spawn_blocking(move || {
                    let result = runtime_paths.and_then(|paths| runtime.start(&paths));
                    match result {
                        Ok(_) => {
                            let url = "http://127.0.0.1:54876/"
                                .parse()
                                .expect("valid TOMOS URL");
                            let _ = window.navigate(url);
                        }
                        Err(error) => {
                            let script = format!(
                                "window.TOMOS_DESKTOP_STARTUP.showError({:?});",
                                error.code()
                            );
                            let _ = window.eval(&script);
                        }
                    }
                });
            })
            .build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("TOMOS desktop app build failed");

    app.run(move |app_handle, event| match event {
        RunEvent::WindowEvent {
            label,
            event: WindowEvent::CloseRequested { .. } | WindowEvent::Destroyed,
            ..
        } if label == "main" => {
            supervisor.stop_owned();
            app_handle.exit(0);
        }
        RunEvent::Exit | RunEvent::ExitRequested { .. } => {
            supervisor.stop_owned();
        }
        _ => {}
    });
}
