use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::process::{Command as StdCommand, Stdio};
use std::sync::Mutex;
use tauri::{command, AppHandle, Emitter, State};
use futures::StreamExt;
use tokio::io::{AsyncBufReadExt, AsyncReadExt, BufReader};
use tokio::process::Command;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const DETACHED_PROCESS: u32 = 0x00000008;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[derive(Debug, Serialize, Deserialize)]
pub struct OllamaMessage {
    pub role: String,
    pub content: String,
}

async fn read_text_response(resp: reqwest::Response, label: &str) -> Result<String, String> {
    let status = resp.status();
    let text = resp
        .text()
        .await
        .map_err(|e| format!("{} read error: {}", label, e))?;

    if !status.is_success() {
        let shortened = text.chars().take(400).collect::<String>();
        return Err(format!("{} returned {}: {}", label, status, shortened));
    }

    Ok(text)
}

async fn read_binary_response(resp: reqwest::Response, label: &str) -> Result<Vec<u8>, String> {
    let status = resp.status();
    let bytes = resp
        .bytes()
        .await
        .map_err(|e| format!("{} read error: {}", label, e))?;

    if !status.is_success() {
        return Err(format!("{} returned {}", label, status));
    }

    Ok(bytes.to_vec())
}

#[derive(Debug, Clone, Default)]
pub struct RuntimeProcessRecord {
    pub pid: Option<u32>,
    pub started_by_app: bool,
    pub path: Option<String>,
}

#[derive(Default)]
pub struct RuntimeManagerState {
    pub records: Mutex<HashMap<String, RuntimeProcessRecord>>,
    pub active_ollama_model: Mutex<Option<String>>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeServiceInfo {
    pub id: String,
    pub label: String,
    pub available: bool,
    pub running: bool,
    pub started_by_app: bool,
    pub progress: u8,
    pub detail: String,
    pub path: Option<String>,
    pub process_id: Option<u32>,
}

#[derive(Debug, Serialize, Clone)]
pub struct RuntimeActionResult {
    pub ok: bool,
    pub detail: String,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct HostPrivilegeStatus {
    pub platform: String,
    pub is_admin: bool,
    pub can_elevate: bool,
    pub detail: String,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct LinuxRuntimeCheckItem {
    pub id: String,
    pub label: String,
    pub required: bool,
    pub ready: bool,
    pub detail: String,
    pub path: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct LinuxRuntimeCheckReport {
    pub platform: String,
    pub is_linux: bool,
    pub ready: bool,
    pub needs_install: bool,
    pub workspace_path: Option<String>,
    pub marker_path: Option<String>,
    pub log_path: Option<String>,
    pub install_command: Option<String>,
    pub detail: String,
    pub items: Vec<LinuxRuntimeCheckItem>,
}

#[derive(Debug, Serialize, Clone)]
pub struct RuntimeProgressPayload {
    pub service: String,
    pub status: String,
    pub progress: u8,
    pub detail: String,
}

fn runtime_record(state: &State<RuntimeManagerState>, service: &str) -> RuntimeProcessRecord {
    state
        .records
        .lock()
        .ok()
        .and_then(|records| records.get(service).cloned())
        .unwrap_or_default()
}

fn set_runtime_record(
    state: &State<RuntimeManagerState>,
    service: &str,
    record: RuntimeProcessRecord,
) -> Result<(), String> {
    let mut records = state
        .records
        .lock()
        .map_err(|_| "Runtime manager lock failure".to_string())?;
    records.insert(service.to_string(), record);
    Ok(())
}

fn clear_runtime_record(state: &State<RuntimeManagerState>, service: &str) -> Result<(), String> {
    let mut records = state
        .records
        .lock()
        .map_err(|_| "Runtime manager lock failure".to_string())?;
    records.remove(service);
    Ok(())
}

fn normalize_ollama_model_name(model: &str) -> String {
    model.trim().trim_end_matches(":latest").to_string()
}

fn ollama_models_match(left: &str, right: &str) -> bool {
    normalize_ollama_model_name(left) == normalize_ollama_model_name(right)
}

fn get_active_ollama_model(state: &State<RuntimeManagerState>) -> Result<Option<String>, String> {
    state
        .active_ollama_model
        .lock()
        .map_err(|_| "Runtime manager lock failure".to_string())
        .map(|value| value.clone())
}

fn set_active_ollama_model(
    state: &State<RuntimeManagerState>,
    model: Option<String>,
) -> Result<(), String> {
    let mut active = state
        .active_ollama_model
        .lock()
        .map_err(|_| "Runtime manager lock failure".to_string())?;
    *active = model.map(|value| normalize_ollama_model_name(&value));
    Ok(())
}

async fn fetch_loaded_ollama_models() -> Result<Vec<String>, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| format!("Ollama client init failed: {}", e))?;

    let response = client
        .get("http://127.0.0.1:11434/api/ps")
        .send()
        .await
        .map_err(|e| format!("Ollama ps failed: {}", e))?;

    if !response.status().is_success() {
        return Ok(Vec::new());
    }

    let value = response
        .json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Ollama ps json failed: {}", e))?;

    Ok(value
        .get("models")
        .and_then(|models| models.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter_map(|entry| entry.get("name").and_then(|name| name.as_str()).map(|name| name.to_string()))
        .collect())
}

async fn wait_for_ollama_models_unloaded(timeout_ms: u64) -> Result<bool, String> {
    let deadline = std::time::Instant::now() + std::time::Duration::from_millis(timeout_ms);
    while std::time::Instant::now() < deadline {
        if fetch_loaded_ollama_models().await?.is_empty() {
            return Ok(true);
        }
        tokio::time::sleep(std::time::Duration::from_millis(350)).await;
    }

    Ok(fetch_loaded_ollama_models().await?.is_empty())
}

async fn wait_for_ollama_model_loaded(target_model: &str, timeout_ms: u64) -> Result<bool, String> {
    let deadline = std::time::Instant::now() + std::time::Duration::from_millis(timeout_ms);
    while std::time::Instant::now() < deadline {
        let loaded = fetch_loaded_ollama_models().await?;
        if loaded.iter().any(|name| ollama_models_match(name, target_model)) {
            return Ok(true);
        }
        tokio::time::sleep(std::time::Duration::from_millis(350)).await;
    }

    Ok(fetch_loaded_ollama_models()
        .await?
        .iter()
        .any(|name| ollama_models_match(name, target_model)))
}

fn env_path_candidates(name: &str) -> Vec<String> {
    let mut candidates = Vec::new();
    #[cfg(windows)]
    let local_app_data = std::env::var("LOCALAPPDATA").unwrap_or_default();
    #[cfg(windows)]
    let program_files = std::env::var("PROGRAMFILES").unwrap_or_default();
    #[cfg(windows)]
    let app_data = std::env::var("APPDATA").unwrap_or_default();

    if name == "ollama" {
        #[cfg(windows)]
        {
        candidates.push(format!(r"{}\Programs\Ollama\ollama.exe", local_app_data));
        candidates.push(format!(r"{}\Ollama\ollama.exe", program_files));
        }
        candidates.push("ollama".to_string());
    }

    if name == "comfyui" {
        // Consolidated location: modele/comfyui/comfyui next to the project root
        // Try both modele/comfyui and modele/comfyui/comfyui (nested move)
        if let Ok(cwd) = std::env::current_dir() {
            for ancestor in cwd.ancestors() {
                let modele = ancestor.join("modele");
                if modele.is_dir() {
                    // Check nested path first (modele/comfyui/comfyui/main.py)
                    let nested = modele.join("comfyui").join("comfyui");
                    if nested.join("main.py").exists() {
                        candidates.push(nested.to_string_lossy().to_string());
                    }
                    // Then flat path (modele/comfyui/main.py)
                    let flat = modele.join("comfyui");
                    if flat.join("main.py").exists() {
                        candidates.push(flat.to_string_lossy().to_string());
                    }
                    break;
                }
            }
        }
        #[cfg(windows)]
        candidates.push(format!(r"{}\AuroraIA\tools\comfyui", app_data));
    }

    candidates
}

fn command_exists(command: &str) -> bool {
    let finder = if cfg!(windows) { "where" } else { "which" };
    StdCommand::new(finder)
        .arg(command)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn command_path(command: &str) -> Option<String> {
    let finder = if cfg!(windows) { "where" } else { "which" };
    let output = StdCommand::new(finder)
        .arg(command)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let text = String::from_utf8_lossy(&output.stdout);
    text.lines()
        .map(str::trim)
        .find(|line| !line.is_empty())
        .map(|line| line.to_string())
}

fn detect_ollama_path() -> Option<String> {
    for candidate in env_path_candidates("ollama") {
        if candidate == "ollama" {
            if command_exists("ollama") {
                return Some(candidate);
            }
        } else if Path::new(&candidate).exists() {
            return Some(candidate);
        }
    }

    None
}

fn detect_comfyui_dir() -> Option<String> {
    env_path_candidates("comfyui")
        .into_iter()
        .find(|candidate| Path::new(candidate).join("main.py").exists())
}

fn detect_python_path() -> Option<String> {
    let mut candidates: Vec<String> = Vec::new();

    #[cfg(windows)]
    {
        let local_app_data = std::env::var("LOCALAPPDATA").unwrap_or_default();
        // Check Python 3.13 down to 3.10
        for version in (10..=13).rev() {
            candidates.push(format!(
                r"{}\Programs\Python\Python3{}\python.exe",
                local_app_data, version
            ));
        }
        candidates.push("python".to_string());
    }

    #[cfg(not(windows))]
    {
        candidates.push("python3".to_string());
        candidates.push("python".to_string());
    }

    for candidate in candidates {
        if candidate == "python" || candidate == "python3" {
            if command_exists(&candidate) {
                return Some(candidate);
            }
        } else if Path::new(&candidate).exists() {
            return Some(candidate);
        }
    }

    None
}

fn detect_preferred_python_path() -> Option<String> {
    if let Some(comfy_dir) = detect_comfyui_dir() {
        if let Some(comfy_python) = resolve_comfy_python(&comfy_dir) {
            return Some(comfy_python);
        }
    }

    detect_python_path()
}

fn is_process_elevated() -> bool {
    #[cfg(windows)]
    {
        let output = StdCommand::new("powershell")
            .args([
                "-NoProfile",
                "-Command",
                "$id=[Security.Principal.WindowsIdentity]::GetCurrent(); $p=New-Object Security.Principal.WindowsPrincipal($id); if($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { 'true' } else { 'false' }",
            ])
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .output();

        return output
            .ok()
            .map(|value| String::from_utf8_lossy(&value.stdout).trim().eq_ignore_ascii_case("true"))
            .unwrap_or(false);
    }

    #[cfg(not(windows))]
    {
        true
    }
}

fn resolve_comfy_python(comfy_dir: &str) -> Option<String> {
    #[cfg(windows)]
    {
    let embedded = Path::new(comfy_dir)
        .join("python_embeded")
        .join("python.exe");
    if embedded.exists() {
        return Some(embedded.to_string_lossy().to_string());
    }
    }

    let venv_root = Path::new(comfy_dir).join("venv");
    let venv_candidates = [
        venv_root.join("Scripts").join("python.exe"),
        venv_root.join("bin").join("python"),
        venv_root.join("bin").join("python3"),
    ];

    for candidate in venv_candidates {
        if candidate.exists() {
            return Some(candidate.to_string_lossy().to_string());
        }
    }

    detect_python_path()
}

fn looks_like_workspace_root(path: &Path) -> bool {
    path.join("package.json").exists()
        && path.join("src-tauri").join("tauri.conf.json").exists()
        && path.join("python-services").exists()
}

fn normalize_path(path: &Path) -> String {
    path.to_string_lossy().replace('\\', "/")
}

fn ps_escape(value: &str) -> String {
    value.replace('\'', "''")
}

fn sh_single_quote(value: &str) -> String {
    format!("'{}'", value.replace('\'', "'\"'\"'"))
}

fn is_probably_dev_tauri_session(exe_path: &Path) -> bool {
    let normalized = normalize_path(exe_path).to_lowercase();
    normalized.contains("/target/debug/") && resolve_workspace_root().is_some()
}

fn build_binary_elevation_script(exe_path: &Path, cwd: &Path, args: &[String]) -> String {
    let exe_ps = ps_escape(&exe_path.to_string_lossy());
    let cwd_ps = ps_escape(&cwd.to_string_lossy());
    let arg_list = args
        .iter()
        .map(|arg| format!("'{}'", ps_escape(arg)))
        .collect::<Vec<_>>()
        .join(", ");

    if arg_list.is_empty() {
        format!(
            "Start-Process -Verb RunAs -FilePath '{}' -WorkingDirectory '{}'",
            exe_ps, cwd_ps
        )
    } else {
        format!(
            "Start-Process -Verb RunAs -FilePath '{}' -WorkingDirectory '{}' -ArgumentList @({})",
            exe_ps, cwd_ps, arg_list
        )
    }
}

fn build_dev_stack_elevation_script(workspace_root: &Path) -> String {
    let root_ps = ps_escape(&workspace_root.to_string_lossy());
    let inner_command = format!("Set-Location '{}'; npm run tauri:dev", root_ps);
    let inner_ps = ps_escape(&inner_command);

    format!(
        "Start-Process -Verb RunAs -FilePath 'powershell.exe' -WorkingDirectory '{}' -ArgumentList @('-NoLogo', '-NoExit', '-Command', '{}')",
        root_ps, inner_ps
    )
}

fn resolve_workspace_root() -> Option<PathBuf> {
    let mut candidates = Vec::new();

    for key in ["JUAN_BIKE_IA_WORKSPACE", "AURORA_IA_WORKSPACE"] {
        if let Ok(value) = std::env::var(key) {
            if !value.trim().is_empty() {
                candidates.push(PathBuf::from(value));
            }
        }
    }

    if let Ok(current_dir) = std::env::current_dir() {
        candidates.push(current_dir);
    }

    if let Ok(current_exe) = std::env::current_exe() {
        if let Some(parent) = current_exe.parent() {
            candidates.push(parent.to_path_buf());
        }
    }

    for candidate in candidates {
        for ancestor in candidate.ancestors() {
            if looks_like_workspace_root(ancestor) {
                return Some(ancestor.to_path_buf());
            }
        }
    }

    None
}

fn linux_runtime_script_path(root: &Path) -> PathBuf {
    root.join("scripts")
        .join("linux")
        .join("aurora-first-run.sh")
}

fn linux_runtime_marker_path(root: &Path) -> PathBuf {
    root.join("application").join(".aurora-linux-ready")
}

fn linux_runtime_log_path(root: &Path) -> PathBuf {
    root.join("application")
        .join("logs")
        .join("aurora-first-run.log")
}

fn push_runtime_command_item(items: &mut Vec<LinuxRuntimeCheckItem>, command: &str, required: bool) {
    let path = command_path(command);
    items.push(LinuxRuntimeCheckItem {
        id: command.to_string(),
        label: command.to_string(),
        required,
        ready: path.is_some(),
        detail: path
            .as_ref()
            .map(|value| format!("Disponible: {}", value))
            .unwrap_or_else(|| "Introuvable dans PATH".to_string()),
        path,
    });
}

fn push_runtime_path_item(
    items: &mut Vec<LinuxRuntimeCheckItem>,
    id: &str,
    label: &str,
    path: PathBuf,
    required: bool,
) {
    let ready = path.exists();
    items.push(LinuxRuntimeCheckItem {
        id: id.to_string(),
        label: label.to_string(),
        required,
        ready,
        detail: if ready {
            "Present".to_string()
        } else {
            "Manquant".to_string()
        },
        path: Some(normalize_path(&path)),
    });
}

fn probe_torch_cuda(python_path: &Path) -> LinuxRuntimeCheckItem {
    let script = "import torch\nprint(torch.__version__)\nprint(torch.version.cuda)\nprint(torch.cuda.is_available())\nprint(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no-gpu')\nprint(','.join(torch.cuda.get_arch_list()) if torch.cuda.is_available() else '')\n";
    let output = StdCommand::new(python_path)
        .arg("-c")
        .arg(script)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output();

    match output {
        Ok(value) if value.status.success() => {
            let stdout = String::from_utf8_lossy(&value.stdout);
            let lines = stdout.lines().map(str::trim).collect::<Vec<_>>();
            let cuda_available = lines.get(2).map(|line| *line == "True").unwrap_or(false);
            let arch_list = lines.get(4).copied().unwrap_or_default();
            let blackwell_ready = arch_list.contains("sm_120") || arch_list.contains("compute_120");
            LinuxRuntimeCheckItem {
                id: "torch_cuda".to_string(),
                label: "PyTorch CUDA".to_string(),
                required: true,
                ready: cuda_available && blackwell_ready,
                detail: format!(
                    "torch={}, cuda={}, gpu={}, arch={}",
                    lines.first().copied().unwrap_or("unknown"),
                    lines.get(1).copied().unwrap_or("unknown"),
                    lines.get(3).copied().unwrap_or("unknown"),
                    if arch_list.is_empty() { "none" } else { arch_list }
                ),
                path: Some(normalize_path(python_path)),
            }
        }
        Ok(value) => {
            let stderr = String::from_utf8_lossy(&value.stderr);
            LinuxRuntimeCheckItem {
                id: "torch_cuda".to_string(),
                label: "PyTorch CUDA".to_string(),
                required: true,
                ready: false,
                detail: format!("Probe echouee: {}", stderr.chars().take(240).collect::<String>()),
                path: Some(normalize_path(python_path)),
            }
        }
        Err(error) => LinuxRuntimeCheckItem {
            id: "torch_cuda".to_string(),
            label: "PyTorch CUDA".to_string(),
            required: true,
            ready: false,
            detail: format!("Python indisponible: {}", error),
            path: Some(normalize_path(python_path)),
        },
    }
}

fn linux_terminal_command(root: &Path, max_quality: bool, install_nvidia_driver: bool) -> String {
    let mut args = Vec::new();
    if max_quality {
        args.push("--max-quality");
    } else {
        args.push("--balanced");
    }
    if install_nvidia_driver {
        args.push("--install-nvidia-driver");
    }

    format!(
        "cd {} && bash scripts/linux/aurora-first-run.sh {}; echo; read -r -p 'AuroraIA Linux init terminee. Appuie Entree pour fermer.' _",
        sh_single_quote(&root.to_string_lossy()),
        args.join(" ")
    )
}

fn spawn_linux_runtime_terminal(root: &Path, max_quality: bool, install_nvidia_driver: bool) -> Result<(), String> {
    let command_line = linux_terminal_command(root, max_quality, install_nvidia_driver);
    let terminals: [(&str, Vec<&str>); 5] = [
        ("x-terminal-emulator", vec!["-e", "bash", "-lc"]),
        ("gnome-terminal", vec!["--", "bash", "-lc"]),
        ("konsole", vec!["-e", "bash", "-lc"]),
        ("xfce4-terminal", vec!["--command"]),
        ("xterm", vec!["-e", "bash", "-lc"]),
    ];

    for (terminal, prefix_args) in terminals {
        if !command_exists(terminal) {
            continue;
        }

        let mut cmd = StdCommand::new(terminal);
        for arg in prefix_args {
            cmd.arg(arg);
        }
        if terminal == "xfce4-terminal" {
            cmd.arg(format!("bash -lc {}", sh_single_quote(&command_line)));
        } else {
            cmd.arg(&command_line);
        }
        cmd.current_dir(root);
        cmd.stdin(Stdio::null());
        cmd.stdout(Stdio::null());
        cmd.stderr(Stdio::null());
        cmd.spawn()
            .map_err(|e| format!("Impossible d'ouvrir {}: {}", terminal, e))?;
        return Ok(());
    }

    let log_path = linux_runtime_log_path(root);
    if let Some(parent) = log_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Impossible de creer le dossier logs: {}", e))?;
    }
    let stdout = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("Impossible d'ouvrir le log first-run: {}", e))?;
    let stderr = stdout
        .try_clone()
        .map_err(|e| format!("Impossible de cloner le log first-run: {}", e))?;
    let mut args = vec!["scripts/linux/aurora-first-run.sh"];
    if max_quality {
        args.push("--max-quality");
    } else {
        args.push("--balanced");
    }
    if install_nvidia_driver {
        args.push("--install-nvidia-driver");
    }

    StdCommand::new("bash")
        .args(args)
        .current_dir(root)
        .stdin(Stdio::null())
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr))
        .spawn()
        .map_err(|e| format!("Impossible de lancer aurora-first-run.sh: {}", e))?;
    Ok(())
}

async fn ping_url(url: &str, timeout_seconds: u64) -> bool {
    let Ok(client) = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(timeout_seconds))
        .build()
    else {
        return false;
    };

    client
        .get(url)
        .send()
        .await
        .map(|response| response.status().is_success())
        .unwrap_or(false)
}

async fn emit_runtime_progress(
    app_handle: &AppHandle,
    service: &str,
    status: &str,
    progress: u8,
    detail: impl Into<String>,
) {
    let _ = app_handle.emit(
        "runtime-progress",
        RuntimeProgressPayload {
            service: service.to_string(),
            status: status.to_string(),
            progress,
            detail: detail.into(),
        },
    );
}

async fn wait_for_healthcheck(
    app_handle: &AppHandle,
    service: &str,
    url: &str,
    attempts: usize,
    interval_ms: u64,
) -> bool {
    for index in 0..attempts {
        if ping_url(url, 3).await {
            emit_runtime_progress(app_handle, service, "ready", 100, "Service pret.").await;
            return true;
        }

        let progress = 20 + (((index + 1) as f32 / attempts as f32) * 70.0) as u8;
        emit_runtime_progress(
            app_handle,
            service,
            "starting",
            progress,
            "Le service se prepare...",
        )
        .await;
        tokio::time::sleep(std::time::Duration::from_millis(interval_ms)).await;
    }

    false
}

fn runtime_service_snapshot(
    service: &str,
    available: bool,
    running: bool,
    detail: impl Into<String>,
    path: Option<String>,
    record: RuntimeProcessRecord,
) -> RuntimeServiceInfo {
    let RuntimeProcessRecord {
        pid,
        started_by_app,
        path: record_path,
    } = record;

    RuntimeServiceInfo {
        id: service.to_string(),
        label: if service == "ollama" {
            "Ollama"
        } else {
            "ComfyUI"
        }
        .to_string(),
        available,
        running,
        started_by_app,
        progress: if running { 100 } else { 0 },
        detail: detail.into(),
        path: path.or(record_path),
        process_id: pid,
    }
}

async fn inspect_runtime_service(
    state: &State<'_, RuntimeManagerState>,
    service: &str,
) -> RuntimeServiceInfo {
    let record = runtime_record(state, service);

    match service {
        "ollama" => {
            let path = detect_ollama_path();
            let running = ping_url("http://127.0.0.1:11434/api/version", 3).await;
            let detail = if running {
                if record.started_by_app {
                    "Ollama actif, lance par l application."
                } else {
                    "Ollama actif."
                }
            } else if path.is_some() {
                "Ollama installe et disponible pour demarrage a la demande."
            } else {
                "Ollama introuvable sur cette machine."
            };

            runtime_service_snapshot(service, path.is_some(), running, detail, path, record)
        }
        "comfyui" => {
            let path = detect_comfyui_dir();
            let running = ping_url("http://127.0.0.1:8188/system_stats", 3).await;
            let detail = if running {
                if record.started_by_app {
                    "ComfyUI actif, lance par l application."
                } else {
                    "ComfyUI actif."
                }
            } else if path.is_some() {
                "ComfyUI installe et disponible pour demarrage a la demande."
            } else {
                "ComfyUI introuvable dans le poste local."
            };

            runtime_service_snapshot(service, path.is_some(), running, detail, path, record)
        }
        _ => runtime_service_snapshot(
            service,
            false,
            false,
            "Service inconnu.",
            None,
            RuntimeProcessRecord::default(),
        ),
    }
}

async fn unload_ollama_models() -> Result<u32, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| format!("Ollama client init failed: {}", e))?;

    let ps_response = client
        .get("http://127.0.0.1:11434/api/ps")
        .send()
        .await
        .map_err(|e| format!("Ollama ps failed: {}", e))?;

    if !ps_response.status().is_success() {
        return Ok(0);
    }

    let ps_value: serde_json::Value = ps_response
        .json()
        .await
        .map_err(|e| format!("Ollama ps json failed: {}", e))?;

    let models = ps_value
        .get("models")
        .and_then(|value| value.as_array())
        .cloned()
        .unwrap_or_default();

    let mut unloaded = 0;
    for model in models {
        let Some(model_name) = model.get("name").and_then(|value| value.as_str()) else {
            continue;
        };

        let unload_response = client
            .post("http://127.0.0.1:11434/api/generate")
            .json(&serde_json::json!({
                "model": model_name,
                "prompt": "",
                "stream": false,
                "keep_alive": 0
            }))
            .send()
            .await;

        if unload_response.map(|response| response.status().is_success()).unwrap_or(false) {
            unloaded += 1;
        }
    }

    Ok(unloaded)
}

async fn free_comfyui_memory() -> Result<(), String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build()
        .map_err(|e| format!("ComfyUI client init failed: {}", e))?;

    let payload = serde_json::json!({
        "unload_models": true,
        "free_memory": true
    });

    let primary = client
        .post("http://127.0.0.1:8188/free")
        .json(&payload)
        .send()
        .await;

    if primary
        .as_ref()
        .map(|response| response.status().is_success())
        .unwrap_or(false)
    {
        return Ok(());
    }

    let fallback = client
        .post("http://127.0.0.1:8188/api/free")
        .json(&payload)
        .send()
        .await;

    if fallback
        .map(|response| response.status().is_success())
        .unwrap_or(false)
    {
        return Ok(());
    }

    Err("ComfyUI n a pas confirme la liberation de la VRAM.".to_string())
}

async fn ensure_ollama_model_installed(
    model: &str,
    app_handle: &AppHandle,
) -> Result<(), String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(7200))
        .build()
        .map_err(|e| format!("Ollama client init failed: {}", e))?;

    let tags_response = client
        .get("http://127.0.0.1:11434/api/tags")
        .send()
        .await
        .map_err(|e| format!("Ollama list failed: {}", e))?;

    if !tags_response.status().is_success() {
        return Err(format!(
            "Ollama list returned {} while checking {}",
            tags_response.status(),
            model
        ));
    }

    let tags_value: serde_json::Value = tags_response
        .json()
        .await
        .map_err(|e| format!("Ollama list json failed: {}", e))?;

    let installed = tags_value
        .get("models")
        .and_then(|value| value.as_array())
        .map(|models| {
            models.iter().any(|entry| {
                entry
                    .get("name")
                    .and_then(|value| value.as_str())
                    .map(|name| {
                        name == model
                            || name == format!("{}:latest", model)
                            || model == format!("{}:latest", name)
                            || name.split(':').next() == model.split(':').next()
                                && (model.contains(':') || name.ends_with(":latest"))
                    })
                    .unwrap_or(false)
            })
        })
        .unwrap_or(false);

    if installed {
        // Warn but allow if a legacy model is somehow still in VRAM
        let model_base = model.split(':').next().unwrap_or(model).to_lowercase();
        const LEGACY_BASES: &[&str] = &["llama3.1", "llama3.3", "llava"];
        if LEGACY_BASES.contains(&model_base.as_str()) {
            emit_runtime_progress(
                app_handle,
                "ollama",
                "warning",
                28,
                format!("ATTENTION: modele legacy '{}' detecte en VRAM. Migrez la configuration vers qwen3:30b-a3b-instruct-2507.", model),
            )
            .await;
        } else {
            emit_runtime_progress(
                app_handle,
                "ollama",
                "warming",
                28,
                format!("{} deja present dans la bibliotheque locale.", model),
            )
            .await;
        }
        return Ok(());
    }

    // Bloquer le telechargement de modeles legacy supprimes du projet
    {
        let model_base = model.split(':').next().unwrap_or(model).to_lowercase();
        const BLOCKED_BASES: &[&str] = &["llama3.1", "llama3.3", "llava"];
        if BLOCKED_BASES.contains(&model_base.as_str())
            || model.to_lowercase().contains("voxtral-mini-3b")
            || model.to_lowercase().contains("voxtral-mini-4b")
        {
            let msg = format!(
                "Telechargement bloque: '{}' est un modele legacy retire du projet. \
                 Verifiez la configuration — le modele principal doit etre qwen3:30b-a3b-instruct-2507.",
                model
            );
            emit_runtime_progress(app_handle, "ollama", "error", 0, msg.clone()).await;
            return Err(msg);
        }
    }

    emit_runtime_progress(
        app_handle,
        "ollama",
        "warming",
        16,
        format!("{} absent localement, telechargement en cours...", model),
    )
    .await;

    let pull_response = client
        .post("http://127.0.0.1:11434/api/pull")
        .json(&serde_json::json!({
            "name": model,
            "stream": true
        }))
        .send()
        .await
        .map_err(|e| format!("Ollama pull failed: {}", e))?;

    if !pull_response.status().is_success() {
        let status = pull_response.status();
        let detail = pull_response
            .text()
            .await
            .unwrap_or_else(|_| "details indisponibles".to_string());
        return Err(format!(
            "Installation automatique de {} impossible: {} ({})",
            model,
            status,
            detail.chars().take(240).collect::<String>()
        ));
    }

    let mut stream = pull_response.bytes_stream();
    let mut buffer = String::new();
    let mut last_progress = 16u8;

    while let Some(chunk_result) = stream.next().await {
        let chunk = chunk_result.map_err(|e| format!("Ollama pull stream failed: {}", e))?;
        buffer.push_str(&String::from_utf8_lossy(&chunk));

        while let Some(newline_index) = buffer.find('\n') {
            let line = buffer[..newline_index].trim().to_string();
            buffer = buffer[newline_index + 1..].to_string();

            if line.is_empty() {
                continue;
            }

            if let Ok(value) = serde_json::from_str::<serde_json::Value>(&line) {
                let status = value
                    .get("status")
                    .and_then(|entry| entry.as_str())
                    .unwrap_or("Telechargement en cours");
                let total = value.get("total").and_then(|entry| entry.as_u64());
                let completed = value.get("completed").and_then(|entry| entry.as_u64());

                let progress = if let (Some(total_bytes), Some(done_bytes)) = (total, completed) {
                    if total_bytes > 0 {
                        16 + (((done_bytes as f64 / total_bytes as f64) * 58.0).round() as u8)
                    } else {
                        last_progress
                    }
                } else {
                    std::cmp::min(74, last_progress.saturating_add(2))
                };

                last_progress = progress;
                emit_runtime_progress(
                    app_handle,
                    "ollama",
                    "warming",
                    progress,
                    format!("{} - {}", model, status),
                )
                .await;
            }
        }
    }

    if !buffer.trim().is_empty() {
        if let Ok(value) = serde_json::from_str::<serde_json::Value>(buffer.trim()) {
            let status = value
                .get("status")
                .and_then(|entry| entry.as_str())
                .unwrap_or("Telechargement termine");
            emit_runtime_progress(
                app_handle,
                "ollama",
                "warming",
                74,
                format!("{} - {}", model, status),
            )
            .await;
        }
    }

    Ok(())
}

async fn taskkill_pid(pid: u32) {
    if cfg!(windows) {
        let _ = Command::new("taskkill")
            .args(["/F", "/PID", &pid.to_string(), "/T"])
            .output()
            .await;
        return;
    }

    let _ = Command::new("kill")
        .args(["-TERM", &pid.to_string()])
        .output()
        .await;
}

#[command]
pub async fn ollama_chat(
    model: String,
    messages: Vec<OllamaMessage>,
    temperature: Option<f64>,
) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(600))
        .build()
        .map_err(|e| format!("Ollama client init failed: {}", e))?;

    let mut body = serde_json::json!({
        "model": model,
        "messages": messages,
        "stream": false,
    });

    if let Some(temp) = temperature {
        body["options"] = serde_json::json!({ "temperature": temp });
    }

    let resp = client
        .post("http://127.0.0.1:11434/api/chat")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Ollama chat connection failed: {}", e))?;

    read_text_response(resp, "Ollama chat").await
}

#[command]
pub async fn ollama_generate(model: String, prompt: String) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(600))
        .build()
        .map_err(|e| format!("Ollama client init failed: {}", e))?;

    let body = serde_json::json!({
        "model": model,
        "prompt": prompt,
        "stream": false,
    });

    let resp = client
        .post("http://127.0.0.1:11434/api/generate")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Ollama generate connection failed: {}", e))?;

    read_text_response(resp, "Ollama generate").await
}

#[command]
pub async fn ollama_list_models() -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Ollama client init failed: {}", e))?;

    let resp = client
        .get("http://127.0.0.1:11434/api/tags")
        .send()
        .await
        .map_err(|e| format!("Ollama list failed: {}", e))?;

    read_text_response(resp, "Ollama list").await
}

#[command]
pub async fn ollama_pull_model(model: String) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(7200))
        .build()
        .map_err(|e| format!("Ollama client init failed: {}", e))?;

    let body = serde_json::json!({ "name": model, "stream": false });

    let resp = client
        .post("http://127.0.0.1:11434/api/pull")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Ollama pull failed: {}", e))?;

    read_text_response(resp, "Ollama pull").await
}

#[command]
pub async fn comfyui_request(endpoint: String) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .build()
        .map_err(|e| format!("ComfyUI client init failed: {}", e))?;

    let url = format!("http://127.0.0.1:8188{}", endpoint);
    let resp = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("ComfyUI connection failed: {}", e))?;

    read_text_response(resp, "ComfyUI request").await
}

#[command]
pub async fn comfyui_queue_prompt(workflow: String) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .build()
        .map_err(|e| format!("ComfyUI client init failed: {}", e))?;

    let body = serde_json::json!({
        "prompt": serde_json::from_str::<serde_json::Value>(&workflow).map_err(|e| e.to_string())?
    });

    let resp = client
        .post("http://127.0.0.1:8188/prompt")
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("ComfyUI queue failed: {}", e))?;

    read_text_response(resp, "ComfyUI queue").await
}

#[command]
pub async fn comfyui_get_history(prompt_id: String) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .build()
        .map_err(|e| format!("ComfyUI client init failed: {}", e))?;

    let url = format!("http://127.0.0.1:8188/history/{}", prompt_id);
    let resp = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("ComfyUI history failed: {}", e))?;

    read_text_response(resp, "ComfyUI history").await
}

#[command]
pub async fn comfyui_get_image(filename: String, subfolder: String) -> Result<Vec<u8>, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .map_err(|e| format!("ComfyUI client init failed: {}", e))?;

    let url = format!(
        "http://127.0.0.1:8188/view?filename={}&subfolder={}&type=output",
        filename, subfolder
    );

    let resp = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("ComfyUI image fetch failed: {}", e))?;

    read_binary_response(resp, "ComfyUI image").await
}

#[derive(Debug, Serialize)]
pub struct HardwareProfile {
    pub os: String,
    pub cpu: String,
    pub cores: u32,
    pub ram_gb: f64,
    pub gpu: String,
    pub vram_gb: f64,
    pub vram_free_gb: f64,
}

#[derive(Debug, Serialize)]
pub struct HostRuntimeResources {
    pub total_ram_gb: f64,
    pub free_ram_gb: f64,
    pub memory_pressure: String,
}

async fn detect_cpu_name() -> String {
    // Try PowerShell first (works on all modern Windows, including Windows 11 without wmic).
    if let Ok(out) = Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_Processor).Name",
        ])
        .output()
        .await
    {
        let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if !text.is_empty() && out.status.success() {
            return text;
        }
    }

    // Fallback: wmic (deprecated on Windows 11 but still present on older builds).
    if let Ok(out) = Command::new("wmic")
        .args(["cpu", "get", "name", "/format:value"])
        .output()
        .await
    {
        let text = String::from_utf8_lossy(&out.stdout);
        if let Some(line) = text.lines().find(|l| l.starts_with("Name=")) {
            let name = line.trim_start_matches("Name=").trim().to_string();
            if !name.is_empty() {
                return name;
            }
        }
    }

    "Unknown CPU".to_string()
}

async fn detect_ram_gb() -> f64 {
    // Try PowerShell first.
    if let Ok(out) = Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize",
        ])
        .output()
        .await
    {
        let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if out.status.success() {
            if let Ok(kb) = text.parse::<f64>() {
                return kb / 1024.0 / 1024.0;
            }
        }
    }

    // Fallback: wmic.
    if let Ok(out) = Command::new("wmic")
        .args(["os", "get", "TotalVisibleMemorySize", "/format:value"])
        .output()
        .await
    {
        let text = String::from_utf8_lossy(&out.stdout);
        if let Some(line) = text.lines().find(|l| l.starts_with("TotalVisibleMemorySize=")) {
            if let Ok(kb) = line
                .trim_start_matches("TotalVisibleMemorySize=")
                .trim()
                .parse::<f64>()
            {
                return kb / 1024.0 / 1024.0;
            }
        }
    }

    0.0
}

async fn detect_free_ram_gb() -> f64 {
    if let Ok(out) = Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory",
        ])
        .output()
        .await
    {
        let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
        if out.status.success() {
            if let Ok(kb) = text.parse::<f64>() {
                return kb / 1024.0 / 1024.0;
            }
        }
    }

    if let Ok(out) = Command::new("wmic")
        .args(["os", "get", "FreePhysicalMemory", "/format:value"])
        .output()
        .await
    {
        let text = String::from_utf8_lossy(&out.stdout);
        if let Some(line) = text.lines().find(|l| l.starts_with("FreePhysicalMemory=")) {
            if let Ok(kb) = line
                .trim_start_matches("FreePhysicalMemory=")
                .trim()
                .parse::<f64>()
            {
                return kb / 1024.0 / 1024.0;
            }
        }
    }

    0.0
}

#[command]
pub async fn detect_hardware() -> Result<HardwareProfile, String> {
    let os_name = std::env::consts::OS.to_string();
    let cores = num_cpus::get() as u32;

    let (cpu, ram_gb) = tokio::join!(detect_cpu_name(), detect_ram_gb());

    let gpu_output = Command::new("nvidia-smi")
        .args(["--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"])
        .output()
        .await;

    let (gpu, vram_gb, vram_free_gb) = match gpu_output {
        Ok(out) if out.status.success() => {
            let text = String::from_utf8_lossy(&out.stdout);
            let parts: Vec<&str> = text.trim().split(',').collect();
            if parts.len() >= 3 {
                let name = parts[0].trim().to_string();
                let total: f64 = parts[1].trim().parse().unwrap_or(0.0) / 1024.0;
                let free: f64 = parts[2].trim().parse().unwrap_or(0.0) / 1024.0;
                (name, total, free)
            } else {
                ("GPU inconnu".into(), 0.0, 0.0)
            }
        }
        _ => ("Pas de GPU NVIDIA detecte".into(), 0.0, 0.0),
    };

    Ok(HardwareProfile {
        os: os_name,
        cpu,
        cores,
        ram_gb,
        gpu,
        vram_gb,
        vram_free_gb,
    })
}

#[command]
pub async fn inspect_host_resources() -> Result<HostRuntimeResources, String> {
    let (total_ram_gb, free_ram_gb) = tokio::join!(detect_ram_gb(), detect_free_ram_gb());
    let pressure = if free_ram_gb <= 6.0 {
        "critical"
    } else if free_ram_gb <= 12.0 {
        "high"
    } else if free_ram_gb <= 20.0 {
        "medium"
    } else {
        "low"
    };

    Ok(HostRuntimeResources {
        total_ram_gb,
        free_ram_gb,
        memory_pressure: pressure.to_string(),
    })
}

#[command]
pub fn get_host_privilege_status() -> Result<HostPrivilegeStatus, String> {
    #[cfg(windows)]
    {
        let is_admin = is_process_elevated();
        let dev_mode = std::env::current_exe()
            .ok()
            .map(|exe| is_probably_dev_tauri_session(&exe))
            .unwrap_or(false);
        return Ok(HostPrivilegeStatus {
            platform: "windows".to_string(),
            is_admin,
            can_elevate: true,
            detail: if is_admin {
                "Session deja elevee: installations et operations systeme peuvent etre pilotees sans reprompt applicatif.".to_string()
            } else if dev_mode {
                "Session non admin detectee en mode developpement: l elevation relancera la stack Tauri + Vite complete dans une console admin pour eviter l erreur localhost refuse.".to_string()
            } else {
                "Session non admin: Windows peut interrompre les auto-installations tant que le mode admin global n est pas active.".to_string()
            },
        });
    }

    #[cfg(not(windows))]
    {
        Ok(HostPrivilegeStatus {
            platform: std::env::consts::OS.to_string(),
            is_admin: true,
            can_elevate: false,
            detail: "Aucune elevation Windows requise sur cette plateforme.".to_string(),
        })
    }
}

#[command]
pub fn linux_runtime_check() -> Result<LinuxRuntimeCheckReport, String> {
    let platform = std::env::consts::OS.to_string();
    if !cfg!(target_os = "linux") {
        return Ok(LinuxRuntimeCheckReport {
            platform,
            is_linux: false,
            ready: true,
            needs_install: false,
            workspace_path: None,
            marker_path: None,
            log_path: None,
            install_command: None,
            detail: "Check Linux ignore sur cette plateforme.".to_string(),
            items: Vec::new(),
        });
    }

    let root = resolve_workspace_root()
        .ok_or_else(|| "Workspace AuroraIA introuvable pour le check Linux.".to_string())?;
    let app_dir = root.join("application");
    let script_path = linux_runtime_script_path(&root);
    let marker_path = linux_runtime_marker_path(&root);
    let log_path = linux_runtime_log_path(&root);
    let mut items = Vec::new();

    for command in [
        "git",
        "curl",
        "python3",
        "node",
        "npm",
        "cargo",
        "rustc",
        "blender",
        "cloudflared",
        "ollama",
        "nvidia-smi",
    ] {
        push_runtime_command_item(&mut items, command, true);
    }

    push_runtime_path_item(
        &mut items,
        "first_run_script",
        "Script first-run AuroraIA",
        script_path.clone(),
        true,
    );
    push_runtime_path_item(
        &mut items,
        "node_modules",
        "Dependances Node application",
        app_dir.join("node_modules"),
        true,
    );
    let venv_python = app_dir.join(".venv").join("bin").join("python");
    push_runtime_path_item(
        &mut items,
        "python_venv",
        "Python venv AuroraIA",
        venv_python.clone(),
        true,
    );
    push_runtime_path_item(
        &mut items,
        "comfyui",
        "ComfyUI local",
        root.join("modele").join("comfyui").join("main.py"),
        true,
    );
    push_runtime_path_item(
        &mut items,
        "hunyuan3d_21",
        "Hunyuan3D 2.1 externe",
        PathBuf::from(std::env::var("AURORA_EXTERNAL_DIR").unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_else(|_| "~".to_string());
            format!("{}/.local/share/auroraia/external", home)
        }))
        .join("Hunyuan3D-2.1"),
        true,
    );
    push_runtime_path_item(
        &mut items,
        "trellis2",
        "TRELLIS.2 experimental",
        PathBuf::from(std::env::var("AURORA_EXTERNAL_DIR").unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_else(|_| "~".to_string());
            format!("{}/.local/share/auroraia/external", home)
        }))
        .join("TRELLIS.2"),
        false,
    );

    if venv_python.exists() {
        items.push(probe_torch_cuda(&venv_python));
    } else {
        items.push(LinuxRuntimeCheckItem {
            id: "torch_cuda".to_string(),
            label: "PyTorch CUDA".to_string(),
            required: true,
            ready: false,
            detail: "Probe impossible tant que le venv AuroraIA manque.".to_string(),
            path: Some(normalize_path(&venv_python)),
        });
    }

    let missing_required = items
        .iter()
        .filter(|item| item.required && !item.ready)
        .map(|item| item.label.clone())
        .collect::<Vec<_>>();
    let ready = missing_required.is_empty() && marker_path.exists();

    Ok(LinuxRuntimeCheckReport {
        platform,
        is_linux: true,
        ready,
        needs_install: !ready,
        workspace_path: Some(normalize_path(&root)),
        marker_path: Some(normalize_path(&marker_path)),
        log_path: Some(normalize_path(&log_path)),
        install_command: Some("bash scripts/linux/aurora-first-run.sh --max-quality".to_string()),
        detail: if ready {
            "Runtime Linux AuroraIA pret.".to_string()
        } else if missing_required.is_empty() {
            "Runtime present, marqueur first-run absent: relance de verification conseillee.".to_string()
        } else {
            format!("Elements manquants: {}", missing_required.join(", "))
        },
        items,
    })
}

#[command]
pub fn linux_runtime_install_missing(
    max_quality: Option<bool>,
    install_nvidia_driver: Option<bool>,
) -> Result<RuntimeActionResult, String> {
    if !cfg!(target_os = "linux") {
        return Ok(RuntimeActionResult {
            ok: true,
            detail: "Installation Linux ignoree sur cette plateforme.".to_string(),
        });
    }

    let root = resolve_workspace_root()
        .ok_or_else(|| "Workspace AuroraIA introuvable pour l'installation Linux.".to_string())?;
    let script_path = linux_runtime_script_path(&root);
    if !script_path.exists() {
        return Err(format!("Script first-run introuvable: {}", normalize_path(&script_path)));
    }

    let use_max_quality = max_quality.unwrap_or(true);
    let use_driver_install = install_nvidia_driver.unwrap_or_else(|| !command_exists("nvidia-smi"));
    spawn_linux_runtime_terminal(&root, use_max_quality, use_driver_install)?;

    Ok(RuntimeActionResult {
        ok: true,
        detail: format!(
            "Initialisation Linux lancee. Log: {}",
            normalize_path(&linux_runtime_log_path(&root))
        ),
    })
}

#[command]
pub fn restart_application_as_admin() -> Result<RuntimeActionResult, String> {
    #[cfg(windows)]
    {
        if is_process_elevated() {
            return Ok(RuntimeActionResult {
                ok: true,
                detail: "L application tourne deja en mode admin.".to_string(),
            });
        }

        let exe_path = std::env::current_exe()
            .map_err(|e| format!("Impossible de localiser l executable courant: {}", e))?;
        let cwd = std::env::current_dir()
            .map_err(|e| format!("Impossible de localiser le dossier courant: {}", e))?;
        let launch_args = std::env::args().skip(1).collect::<Vec<_>>();
        let script = if is_probably_dev_tauri_session(&exe_path) {
            let workspace_root = resolve_workspace_root().ok_or_else(|| {
                "Impossible de relancer la stack admin: racine du workspace introuvable.".to_string()
            })?;
            build_dev_stack_elevation_script(&workspace_root)
        } else {
            build_binary_elevation_script(&exe_path, &cwd, &launch_args)
        };

        let status = StdCommand::new("powershell")
            .args(["-NoProfile", "-Command", &script])
            .status()
            .map_err(|e| format!("Impossible de demander l elevation Windows: {}", e))?;

        if !status.success() {
            return Err("L elevation admin a ete refusee ou annulee par Windows.".to_string());
        }

        std::process::exit(0);
    }

    #[cfg(not(windows))]
    {
        Err("Le mode admin automatise est seulement disponible sur Windows.".to_string())
    }
}

/// WS-V-P (2026-08-07) : quand l'UI appelle `video_generate.py` directement,
/// on la ré-achemine par `POST http://localhost:3001/api/video/render` du
/// bridge Flask. Objectif : sortie de plan vidéo passe TOUJOURS par la file
/// GPU, le prévol de stockage et le contrat `VideoJobSpec` canonique — même
/// depuis Tauri, où le raccourci `run_python_script` shortcuit historique
/// contournait tout ça (cf. PROMPT_REFONTE_MODULE_VIDEO §3.3).
///
/// Le contrat `run_python_script` avec le frontend reste inchangé : mêmes
/// arguments, même événement `python-progress`, même chaîne de sortie
/// retournée. Le reroutage est transparent.
///
/// Repli défensif : si le bridge n'est pas joignable (localhost 3001 down,
/// timeout, HTTP != 2xx, etc.), on retombe SILENCIEUSEMENT sur le spawn
/// direct historique — c'est un correctif, pas une régression.
async fn try_route_video_through_bridge(
    script_path: &str,
    args: &[String],
    app_handle: &tauri::AppHandle,
) -> Option<Result<String, String>> {
    let script_name = Path::new(script_path)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    if script_name != "video_generate.py" {
        return None; // pas concerné
    }

    // Extraction des flags les plus critiques. Absence = ne pas reroute.
    // Un dict `flag -> value` ; les booléens ne sont pas utilisés ici.
    let mut flags: HashMap<String, String> = HashMap::new();
    let mut i = 0;
    while i < args.len() {
        let a = &args[i];
        if a.starts_with("--") && i + 1 < args.len() && !args[i + 1].starts_with("--") {
            flags.insert(a[2..].to_string(), args[i + 1].clone());
            i += 2;
        } else if a.starts_with("--") {
            flags.insert(a[2..].to_string(), "true".to_string());
            i += 1;
        } else {
            i += 1;
        }
    }

    let prompt = flags.get("prompt").cloned();
    if prompt.is_none() {
        // Sans prompt on ne construit pas d'intention — laisse le worker direct
        // retourner son erreur explicite au lieu de bricoler.
        return None;
    }

    // Aspect deviné depuis width×height si les deux présents ; sinon 16:9.
    let (w_opt, h_opt) = (
        flags.get("width").and_then(|s| s.parse::<u32>().ok()),
        flags.get("height").and_then(|s| s.parse::<u32>().ok()),
    );
    let aspect: &str = match (w_opt, h_opt) {
        (Some(w), Some(h)) => {
            let r = w as f32 / h as f32;
            if (r - 16.0 / 9.0).abs() < 0.05 {
                "16:9"
            } else if (r - 9.0 / 16.0).abs() < 0.05 {
                "9:16"
            } else if (r - 1.0).abs() < 0.05 {
                "1:1"
            } else if (r - 4.0 / 3.0).abs() < 0.05 {
                "4:3"
            } else {
                "16:9"
            }
        }
        _ => "16:9",
    };

    // duration_s dérivée de num_frames si présent (fps=24 comme le worker),
    // sinon on laisse le builder appliquer son défaut (65 f ≈ 2,7 s).
    let duration_s: Option<f32> = flags
        .get("num_frames")
        .and_then(|s| s.parse::<u32>().ok())
        .map(|n| n as f32 / 24.0);

    let quality_mode = flags
        .get("quality_mode")
        .cloned()
        .unwrap_or_else(|| "auto".to_string());
    let seed = flags.get("seed").and_then(|s| s.parse::<i64>().ok());
    let motion_interp = flags
        .get("motion_interp")
        .and_then(|s| s.parse::<u32>().ok())
        .unwrap_or(1);

    // Construit l'intent JSON à envoyer au bridge.
    let mut intent = serde_json::Map::new();
    intent.insert("prompt".into(), serde_json::Value::String(prompt.unwrap()));
    intent.insert("aspect".into(), serde_json::Value::String(aspect.to_string()));
    if let Some(ds) = duration_s {
        intent.insert(
            "duration_s".into(),
            serde_json::Value::Number(
                serde_json::Number::from_f64(ds as f64).unwrap_or(serde_json::Number::from(0)),
            ),
        );
    }
    intent.insert("quality_mode".into(), serde_json::Value::String(quality_mode));
    if let Some(s) = seed {
        intent.insert("seed".into(), serde_json::Value::Number(s.into()));
    }
    if let Some(img) = flags.get("image") {
        intent.insert("image_path".into(), serde_json::Value::String(img.clone()));
    }
    if let Some(neg) = flags.get("negative_prompt") {
        intent.insert(
            "negative_prompt".into(),
            serde_json::Value::String(neg.clone()),
        );
    }
    intent.insert(
        "motion_interp".into(),
        serde_json::Value::Number((motion_interp as u64).into()),
    );
    if let Some(fs) = flags.get("force_strategy") {
        intent.insert(
            "force_strategy".into(),
            serde_json::Value::String(fs.clone()),
        );
    }
    let body = serde_json::json!({ "intent": serde_json::Value::Object(intent) });

    // Spawn : timeout court pour dry-run/spec-résolution, ensuite polling du
    // jobId sans timeout dur (les rendus vidéo durent des minutes).
    let client = match reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
    {
        Ok(c) => c,
        Err(_) => return None, // repli
    };
    let spawn_resp = match client
        .post("http://localhost:3001/api/video/render")
        .json(&body)
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => return None, // bridge down → repli sur spawn direct
    };
    if !spawn_resp.status().is_success() {
        return None; // spec invalide ou route absente → repli
    }
    let spawn_json: serde_json::Value = match spawn_resp.json().await {
        Ok(v) => v,
        Err(_) => return None,
    };
    let job_id = match spawn_json.get("jobId").and_then(|v| v.as_str()) {
        Some(s) => s.to_string(),
        None => return None,
    };
    let output_path = spawn_json
        .get("outputPath")
        .and_then(|v| v.as_str())
        .map(String::from);

    // Reroutage annoncé (utile pour audit/debug).
    let _ = app_handle.emit(
        "python-progress",
        format!("PROGRESS:route:bridge /api/video/render job={}", job_id),
    );

    // Polling long — chaque tour lit /api/python/job/<id> + emit progression.
    let poll_client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| e.to_string());
    let poll_client = match poll_client {
        Ok(c) => c,
        Err(_) => return None,
    };
    let mut last_emitted_len = 0usize;
    loop {
        tokio::time::sleep(std::time::Duration::from_millis(2500)).await;
        let job = match poll_client
            .get(format!("http://localhost:3001/api/python/job/{}", job_id))
            .send()
            .await
        {
            Ok(r) => r,
            Err(_) => continue,
        };
        if !job.status().is_success() {
            continue;
        }
        let job_data: serde_json::Value = match job.json().await {
            Ok(v) => v,
            Err(_) => continue,
        };
        let status = job_data
            .get("status")
            .and_then(|v| v.as_str())
            .unwrap_or("running");
        let output_str = job_data
            .get("output")
            .and_then(|v| v.as_str())
            .unwrap_or("");

        // Emit progressif : nouvelles lignes PROGRESS: uniquement.
        if output_str.len() > last_emitted_len {
            let fresh = &output_str[last_emitted_len..];
            for line in fresh.lines() {
                if line.starts_with("PROGRESS:") {
                    let _ = app_handle.emit("python-progress", line.to_string());
                }
            }
            last_emitted_len = output_str.len();
        }

        if status == "done" {
            let exit_code = job_data
                .get("exitCode")
                .and_then(|v| v.as_i64())
                .unwrap_or(0);
            if exit_code == 0 {
                let mut out = output_str.to_string();
                // Le contrat historique VideoView cherche `SAVED:<path>` puis
                // parcourt la stdout ; on lui rend la même forme, en ajoutant
                // outputPath du bridge si le SAVED: n'y était pas.
                if !out.contains("SAVED:") {
                    if let Some(p) = output_path.as_ref() {
                        out.push_str(&format!("\nSAVED:{}", p));
                    }
                }
                return Some(Ok(out));
            }
            let err = job_data
                .get("error")
                .and_then(|v| v.as_str())
                .unwrap_or("(no error field)");
            return Some(Err(format!(
                "bridge job {} failed exitCode={} error={}",
                job_id, exit_code, err
            )));
        }
        if status == "cancelled" || status == "died" {
            return Some(Err(format!("bridge job {} status={}", job_id, status)));
        }
        // sinon: running/queued → poll suivant
    }
}

#[command]
pub async fn run_python_script(
    script_path: String,
    args: Vec<String>,
    app_handle: tauri::AppHandle,
) -> Result<String, String> {
    let path = Path::new(&script_path);
    if !path.exists() {
        return Err(format!("Script not found: {}", script_path));
    }

    // 2026-08-07 : tentative de reroutage bridge pour video_generate.py.
    // Si le bridge est joignable et la route accepte l'intent, on utilise
    // la file GPU + le contrat canonique. Sinon on retombe sur le spawn
    // direct historique (pas de régression).
    if let Some(bridge_result) =
        try_route_video_through_bridge(&script_path, &args, &app_handle).await
    {
        return bridge_result;
    }

    let python_exe = detect_preferred_python_path().unwrap_or_else(|| "python".to_string());
    let mut cmd = Command::new(&python_exe);
    if let Some(script_dir) = path.parent() {
        cmd.current_dir(script_dir);
    }
    cmd.arg(&script_path);
    for arg in &args {
        cmd.arg(arg);
    }
    cmd.env("PYTHONUTF8", "1");
    cmd.env("HF_HUB_DISABLE_PROGRESS_BARS", "1");
    cmd.env("TOKENIZERS_PARALLELISM", "false");

    // Set AURORA_MODELS so cache_paths.py uses the consolidated modele/ directory
    if let Some(script_dir) = path.parent() {
        for ancestor in script_dir.ancestors() {
            let modele_dir = ancestor.join("modele");
            if modele_dir.is_dir() {
                cmd.env("AURORA_MODELS", modele_dir.to_string_lossy().as_ref());
                break;
            }
        }
    }

    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());

    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to spawn Python: {}", e))?;

    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;
    let stdout_app = app_handle.clone();

    let stdout_task = tokio::spawn(async move {
        let mut reader = BufReader::new(stdout).lines();
        let mut lines = Vec::new();

        while let Some(line) = reader.next_line().await.map_err(|e| e.to_string())? {
            if line.starts_with("PROGRESS:") {
                let _ = stdout_app.emit("python-progress", &line);
            }
            lines.push(line);
        }

        Ok::<Vec<String>, String>(lines)
    });

    let stderr_task = tokio::spawn(async move {
        let mut reader = BufReader::new(stderr).lines();
        let mut lines = Vec::new();

        while let Some(line) = reader.next_line().await.map_err(|e| e.to_string())? {
            lines.push(line);
        }

        Ok::<Vec<String>, String>(lines)
    });

    let status = child
        .wait()
        .await
        .map_err(|e| format!("Process error: {}", e))?;
    let stdout_lines = stdout_task
        .await
        .map_err(|e| format!("Stdout task failed: {}", e))??;
    let stderr_lines = stderr_task
        .await
        .map_err(|e| format!("Stderr task failed: {}", e))??;
    let full_output = stdout_lines.join("\n");

    if status.success() {
        Ok(full_output)
    } else {
        let mut compact_lines = Vec::new();
        let mut seen = HashSet::new();

        for line in stderr_lines
            .iter()
            .chain(stdout_lines.iter())
            .map(|line| line.trim())
            .filter(|line| !line.is_empty())
            .filter(|line| {
                !line.starts_with("PROGRESS:")
                    && !line.starts_with("THUMBNAIL:")
                    && !line.starts_with("SAVED:")
                    && !line.starts_with("VRAM_INFO:")
                    && !line.contains("FutureWarning:")
                    && !line.contains("allow_in_graph is deprecated")
                    && !line.starts_with("@maybe_allow_in_graph")
            })
            .rev()
        {
            if seen.insert(line.to_string()) {
                compact_lines.push(line.to_string());
            }

            if compact_lines.len() >= 8 {
                break;
            }
        }

        compact_lines.reverse();
        let error_payload = if compact_lines.is_empty() {
            "Aucune sortie exploitable n a ete retournee par le script.".to_string()
        } else {
            compact_lines.join(" | ")
        };

        Err(format!(
            "Script failed (exit {}): {}",
            status.code().unwrap_or(-1),
            error_payload
        ))
    }
}

#[command]
pub async fn run_workspace_command(
    executable: String,
    args: Vec<String>,
    cwd: String,
    timeout_ms: Option<u64>,
) -> Result<ProcessRunResult, String> {
    let cwd_path = Path::new(&cwd);
    if !cwd_path.exists() {
        return Err(format!("Working directory not found: {}", cwd));
    }

    let mut cmd = Command::new(&executable);
    cmd.current_dir(cwd_path);
    cmd.args(&args);
    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
    cmd.env("CI", "1");
    cmd.env("PYTHONUTF8", "1");
    cmd.env("HF_HUB_DISABLE_PROGRESS_BARS", "1");
    cmd.env("TOKENIZERS_PARALLELISM", "false");

    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to spawn command {}: {}", executable, e))?;

    let stdout = child
        .stdout
        .take()
        .ok_or("Failed to capture command stdout")?;
    let stderr = child
        .stderr
        .take()
        .ok_or("Failed to capture command stderr")?;

    let stdout_task = tokio::spawn(async move { read_process_output_lossy(stdout).await });
    let stderr_task = tokio::spawn(async move { read_process_output_lossy(stderr).await });

    let status = if let Some(timeout_ms) = timeout_ms {
        match tokio::time::timeout(std::time::Duration::from_millis(timeout_ms), child.wait()).await
        {
            Ok(wait_result) => wait_result.map_err(|e| format!("Process error: {}", e))?,
            Err(_) => {
                let _ = child.kill().await;
                return Err(format!(
                    "Command timed out after {}ms: {} {}",
                    timeout_ms,
                    executable,
                    args.join(" ")
                ));
            }
        }
    } else {
        child
            .wait()
            .await
            .map_err(|e| format!("Process error: {}", e))?
    };

    let stdout_output = stdout_task
        .await
        .map_err(|e| format!("Stdout task failed: {}", e))??;
    let stderr_output = stderr_task
        .await
        .map_err(|e| format!("Stderr task failed: {}", e))??;
    let output = join_process_output(stdout_output, stderr_output);

    Ok(ProcessRunResult {
        ok: status.success(),
        exit_code: status.code().unwrap_or(-1),
        output,
        command: if args.is_empty() {
            executable
        } else {
            format!("{} {}", executable, args.join(" "))
        },
    })
}

async fn read_process_output_lossy<R>(mut stream: R) -> Result<String, String>
where
    R: tokio::io::AsyncRead + Unpin,
{
    let mut bytes = Vec::new();
    stream
        .read_to_end(&mut bytes)
        .await
        .map_err(|e| e.to_string())?;
    Ok(String::from_utf8_lossy(&bytes).replace("\r\n", "\n"))
}

fn join_process_output(stdout: String, stderr: String) -> String {
    let stdout = stdout.trim_end_matches('\n');
    let stderr = stderr.trim_end_matches('\n');
    match (stdout.is_empty(), stderr.is_empty()) {
        (true, true) => String::new(),
        (false, true) => stdout.to_string(),
        (true, false) => stderr.to_string(),
        (false, false) => format!("{}\n{}", stdout, stderr),
    }
}

#[derive(Debug, Serialize)]
pub struct ServiceStatus {
    pub ollama: bool,
    pub comfyui: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessRunResult {
    pub ok: bool,
    pub exit_code: i32,
    pub output: String,
    pub command: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SpawnedProcessResult {
    pub ok: bool,
    pub pid: u32,
    pub command: String,
    pub stdout_log: Option<String>,
    pub stderr_log: Option<String>,
}

fn open_spawn_log(path: &str) -> Result<std::fs::File, String> {
    let log_path = Path::new(path);
    if let Some(parent) = log_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create log directory {}: {}", parent.display(), e))?;
    }

    std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path)
        .map_err(|e| format!("Failed to open log file {}: {}", log_path.display(), e))
}

#[command]
pub async fn spawn_workspace_command_detached(
    executable: String,
    args: Vec<String>,
    cwd: String,
    stdout_log: Option<String>,
    stderr_log: Option<String>,
) -> Result<SpawnedProcessResult, String> {
    let cwd_path = Path::new(&cwd);
    if !cwd_path.exists() {
        return Err(format!("Working directory not found: {}", cwd));
    }

    let mut cmd = StdCommand::new(&executable);
    cmd.current_dir(cwd_path);
    cmd.args(&args);
    cmd.stdin(Stdio::null());
    cmd.env("CI", "1");
    cmd.env("PYTHONUTF8", "1");
    cmd.env("HF_HUB_DISABLE_PROGRESS_BARS", "1");
    cmd.env("TOKENIZERS_PARALLELISM", "false");

    if let Some(path) = stdout_log.as_ref() {
        cmd.stdout(Stdio::from(open_spawn_log(path)?));
    } else {
        cmd.stdout(Stdio::null());
    }

    if let Some(path) = stderr_log.as_ref() {
        cmd.stderr(Stdio::from(open_spawn_log(path)?));
    } else {
        cmd.stderr(Stdio::null());
    }

    #[cfg(windows)]
    cmd.creation_flags(DETACHED_PROCESS | CREATE_NO_WINDOW);

    let child = cmd
        .spawn()
        .map_err(|e| format!("Failed to spawn detached command {}: {}", executable, e))?;

    let pid = child.id();
    drop(child);

    Ok(SpawnedProcessResult {
        ok: true,
        pid,
        command: if args.is_empty() {
            executable
        } else {
            format!("{} {}", executable, args.join(" "))
        },
        stdout_log,
        stderr_log,
    })
}

#[command]
pub async fn check_service_status() -> Result<ServiceStatus, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(3))
        .build()
        .map_err(|e| e.to_string())?;

    let ollama = client
        .get("http://127.0.0.1:11434/api/tags")
        .send()
        .await
        .is_ok();

    let comfyui = client
        .get("http://127.0.0.1:8188/system_stats")
        .send()
        .await
        .is_ok();

    Ok(ServiceStatus { ollama, comfyui })
}

#[command]
pub fn get_workspace_path() -> String {
    resolve_workspace_root()
        .map(|path| normalize_path(&path))
        .or_else(|| std::env::current_dir().ok().map(|path| normalize_path(&path)))
        .unwrap_or_else(|| ".".into())
}

#[command]
pub async fn fs_exists(path: String) -> Result<bool, String> {
    Ok(Path::new(&path).exists())
}

#[command]
pub async fn fs_mkdir(path: String) -> Result<(), String> {
    std::fs::create_dir_all(&path).map_err(|e| format!("mkdir failed: {}", e))
}

#[command]
pub async fn fs_read_text(path: String) -> Result<String, String> {
    std::fs::read_to_string(&path).map_err(|e| format!("read failed: {}", e))
}

#[command]
pub async fn fs_write_text(path: String, content: String) -> Result<(), String> {
    if let Some(parent) = Path::new(&path).parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    std::fs::write(&path, &content).map_err(|e| format!("write failed: {}", e))
}

#[command]
pub async fn fs_write_binary(path: String, bytes: Vec<u8>) -> Result<(), String> {
    if let Some(parent) = Path::new(&path).parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    std::fs::write(&path, bytes).map_err(|e| format!("write binary failed: {}", e))
}

#[command]
pub async fn fs_read_binary(path: String) -> Result<Vec<u8>, String> {
    std::fs::read(&path).map_err(|e| format!("read binary failed: {}", e))
}

#[command]
pub async fn fs_remove_dir_all(path: String) -> Result<(), String> {
    let p = Path::new(&path);
    if !p.exists() {
        return Ok(());
    }
    if p.is_file() {
        return std::fs::remove_file(p).map_err(|e| format!("remove file failed: {}", e));
    }
    std::fs::remove_dir_all(p).map_err(|e| format!("remove dir failed: {}", e))
}

#[command]
pub async fn fs_list_dir(path: String) -> Result<Vec<String>, String> {
    let p = Path::new(&path);
    if !p.exists() {
        return Ok(vec![]);
    }
    let entries = std::fs::read_dir(p).map_err(|e| format!("read dir failed: {}", e))?;
    let mut names: Vec<String> = Vec::new();
    for entry in entries.flatten() {
        if let Some(name) = entry.file_name().to_str() {
            names.push(name.to_string());
        }
    }
    Ok(names)
}

#[command]
pub async fn runtime_inspect_services(
    state: State<'_, RuntimeManagerState>,
) -> Result<Vec<RuntimeServiceInfo>, String> {
    Ok(vec![
        inspect_runtime_service(&state, "ollama").await,
        inspect_runtime_service(&state, "comfyui").await,
    ])
}

#[command]
pub async fn runtime_ensure_service(
    service: String,
    state: State<'_, RuntimeManagerState>,
    app_handle: AppHandle,
) -> Result<RuntimeServiceInfo, String> {
    match service.as_str() {
        "ollama" => {
            emit_runtime_progress(&app_handle, "ollama", "checking", 6, "Verification d Ollama...").await;

            if ping_url("http://127.0.0.1:11434/api/version", 3).await {
                return Ok(inspect_runtime_service(&state, "ollama").await);
            }

            let Some(ollama_path) = detect_ollama_path() else {
                emit_runtime_progress(&app_handle, "ollama", "error", 100, "Ollama introuvable.").await;
                return Err("Ollama introuvable sur cette machine.".to_string());
            };

            emit_runtime_progress(&app_handle, "ollama", "starting", 18, "Demarrage d Ollama...").await;

            let mut command = StdCommand::new(&ollama_path);
            command.arg("serve");
            command.stdin(Stdio::null());
            command.stdout(Stdio::null());
            command.stderr(Stdio::null());
            command.env("OLLAMA_MAX_LOADED_MODELS", "1");
            command.env("OLLAMA_NUM_PARALLEL", "1");
            command.env("OLLAMA_KEEP_ALIVE", "0");
            command.env("OLLAMA_MAX_QUEUE", "2");

            #[cfg(windows)]
            command.creation_flags(DETACHED_PROCESS | CREATE_NO_WINDOW);

            let child = command
                .spawn()
                .map_err(|e| format!("Impossible de lancer Ollama: {}", e))?;

            let pid = child.id();
            drop(child);

            let ready = wait_for_healthcheck(
                &app_handle,
                "ollama",
                "http://127.0.0.1:11434/api/version",
                20,
                1000,
            )
            .await;

            if !ready {
                emit_runtime_progress(&app_handle, "ollama", "error", 100, "Ollama n a pas repondu.").await;
                return Err("Ollama ne repond pas apres le lancement.".to_string());
            }

            set_runtime_record(
                &state,
                "ollama",
                RuntimeProcessRecord {
                    pid: Some(pid),
                    started_by_app: true,
                    path: Some(ollama_path),
                },
            )?;

            Ok(inspect_runtime_service(&state, "ollama").await)
        }
        "comfyui" => {
            emit_runtime_progress(&app_handle, "comfyui", "checking", 6, "Verification de ComfyUI...").await;

            if ping_url("http://127.0.0.1:8188/system_stats", 3).await {
                return Ok(inspect_runtime_service(&state, "comfyui").await);
            }

            let Some(comfy_dir) = detect_comfyui_dir() else {
                emit_runtime_progress(&app_handle, "comfyui", "error", 100, "ComfyUI introuvable.").await;
                return Err("ComfyUI n est pas installe ou son dossier est introuvable.".to_string());
            };

            let Some(python_path) = resolve_comfy_python(&comfy_dir) else {
                emit_runtime_progress(&app_handle, "comfyui", "error", 100, "Python ComfyUI introuvable.").await;
                return Err("Impossible de trouver le Python de ComfyUI.".to_string());
            };

            emit_runtime_progress(&app_handle, "comfyui", "starting", 18, "Demarrage de ComfyUI...").await;

            let stdout_log = Path::new(&comfy_dir).join("comfyui_stdout.log");
            let stderr_log = Path::new(&comfy_dir).join("comfyui_stderr.log");
            let stdout_handle = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(stdout_log)
                .ok();
            let stderr_handle = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(stderr_log)
                .ok();

            let mut command = StdCommand::new(&python_path);
            let main_py = Path::new(&comfy_dir).join("main.py");
            let main_py = main_py.to_string_lossy().to_string();
            command.args([
                main_py.as_str(),
                "--listen",
                "127.0.0.1",
                "--port",
                "8188",
            ]);
            command.current_dir(&comfy_dir);
            command.stdin(Stdio::null());
            command.stdout(stdout_handle.map(Stdio::from).unwrap_or_else(Stdio::null));
            command.stderr(stderr_handle.map(Stdio::from).unwrap_or_else(Stdio::null));

            #[cfg(windows)]
            command.creation_flags(DETACHED_PROCESS | CREATE_NO_WINDOW);

            let mut child = command
                .spawn()
                .map_err(|e| format!("Impossible de lancer ComfyUI: {}", e))?;
            let pid = child.id();

            for step in 0..90 {
                if ping_url("http://127.0.0.1:8188/system_stats", 3).await {
                    set_runtime_record(
                        &state,
                        "comfyui",
                        RuntimeProcessRecord {
                            pid: Some(pid),
                            started_by_app: true,
                            path: Some(comfy_dir.clone()),
                        },
                    )?;

                    emit_runtime_progress(&app_handle, "comfyui", "ready", 100, "ComfyUI pret.").await;
                    drop(child);
                    return Ok(inspect_runtime_service(&state, "comfyui").await);
                }

                if child
                    .try_wait()
                    .map_err(|e| format!("ComfyUI startup check failed: {}", e))?
                    .is_some()
                {
                    emit_runtime_progress(&app_handle, "comfyui", "error", 100, "ComfyUI a quitte pendant le demarrage.").await;
                    return Err("ComfyUI a quitte pendant le demarrage.".to_string());
                }

                let progress = 20 + (((step + 1) as f32 / 90.0) * 70.0) as u8;
                emit_runtime_progress(
                    &app_handle,
                    "comfyui",
                    "starting",
                    progress,
                    "ComfyUI charge ses dependances et ses nodes...",
                )
                .await;
                tokio::time::sleep(std::time::Duration::from_millis(2000)).await;
            }

            emit_runtime_progress(&app_handle, "comfyui", "error", 100, "ComfyUI n a pas fini de demarrer.").await;
            Err("ComfyUI ne repond pas apres le lancement.".to_string())
        }
        _ => Err(format!("Service runtime inconnu: {}", service)),
    }
}

#[command]
pub async fn runtime_ensure_ollama_model_available(
    model: String,
    app_handle: AppHandle,
) -> Result<RuntimeActionResult, String> {
    ensure_ollama_model_installed(&model, &app_handle).await?;

    emit_runtime_progress(
        &app_handle,
        "ollama",
        "ready",
        100,
        format!("{} est disponible localement.", model),
    )
    .await;

    Ok(RuntimeActionResult {
        ok: true,
        detail: format!("{} est disponible localement.", model),
    })
}

#[command]
pub async fn runtime_prepare_ollama_model(
    model: String,
    state: State<'_, RuntimeManagerState>,
    app_handle: AppHandle,
) -> Result<RuntimeActionResult, String> {
    ensure_ollama_model_installed(&model, &app_handle).await?;
    let normalized_target = normalize_ollama_model_name(&model);
    let active_model = get_active_ollama_model(&state)?;
    let loaded_models = fetch_loaded_ollama_models().await.unwrap_or_default();

    // Check if the model is already active in VRAM — skip the unload/reload cycle.
    let already_loaded = active_model
        .as_ref()
        .map(|active| ollama_models_match(active, &normalized_target))
        .unwrap_or(false)
        && loaded_models
            .iter()
            .any(|loaded| ollama_models_match(loaded, &normalized_target));

    if already_loaded {
        emit_runtime_progress(
            &app_handle,
            "ollama",
            "ready",
            100,
            format!("{} est deja charge en memoire.", model),
        )
        .await;
        return Ok(RuntimeActionResult {
            ok: true,
            detail: format!("{} deja actif en VRAM.", model),
        });
    }

    emit_runtime_progress(
        &app_handle,
        "ollama",
        "warming",
        52,
        format!("Liberation complete des anciens modeles avant {}", model),
    )
    .await;

    let _ = unload_ollama_models().await;
    // 31/07: 18 s d'attente puis ERREUR FATALE — sous pression memoire, un
    // modele de 19 Go met plus longtemps a se vider et CHAQUE generation
    // echouait ici (« Ollama n a pas libere correctement les modeles
    // precedents avant le swap », vu en boucle par l'utilisateur). Or
    // OLLAMA_MAX_LOADED_MODELS=1: Ollama evince DE LUI-MEME l'ancien modele
    // au chargement du nouveau. On attend plus longtemps, et un dechargement
    // lent devient un simple avertissement — jamais un echec.
    let unloaded = wait_for_ollama_models_unloaded(60_000).await?;
    if !unloaded {
        emit_runtime_progress(
            &app_handle,
            "ollama",
            "warming",
            55,
            "Dechargement lent — Ollama evincera l'ancien modele au chargement du nouveau.",
        )
        .await;
    }

    emit_runtime_progress(
        &app_handle,
        "ollama",
        "warming",
        72,
        format!("Chargement de {} en memoire...", model),
    )
    .await;

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(300))
        .build()
        .map_err(|e| format!("Ollama client init failed: {}", e))?;

    // 31/07: (1) keep_alive 8m re-parquait un gros modele pendant les etapes
    // lourdes (politique globale: 60s); (2) une erreur de connexion pendant
    // que le serveur Ollama (re)demarre faisait echouer TOUTE la preparation
    // (« Ollama warmup failed: error sending request » vu par l'utilisateur).
    // Le warmup est best-effort: 3 essais espacés, puis on continue sans lui.
    let mut warm_result = None;
    for attempt in 0..3u8 {
        match client
            .post("http://127.0.0.1:11434/api/generate")
            .json(&serde_json::json!({
                "model": model,
                "prompt": "",
                "stream": false,
                "keep_alive": "60s"
            }))
            .send()
            .await
        {
            Ok(resp) => { warm_result = Some(resp); break; }
            Err(err) => {
                emit_runtime_progress(
                    &app_handle,
                    "ollama",
                    "warming",
                    58,
                    format!("Ollama pas encore joignable (essai {}/3): {}", attempt + 1, err),
                )
                .await;
                tokio::time::sleep(std::time::Duration::from_secs(4)).await;
            }
        }
    }
    let Some(response) = warm_result else {
        emit_runtime_progress(
            &app_handle,
            "ollama",
            "ready",
            100,
            "Warmup saute (Ollama indisponible) — le premier appel reel chargera le modele.".to_string(),
        )
        .await;
        return Ok(RuntimeActionResult {
            ok: true,
            detail: format!("{} sera charge au premier appel (warmup saute).", model),
        });
    };

    // Le warmup est best-effort : si Ollama retourne une erreur (ex. 500 OOM, fichier
    // corrompu), on ne bloque pas le pipeline — le premier vrai appel generate/chat
    // produira un message d'erreur explicite. On emet simplement un avertissement.
    if !response.status().is_success() {
        let _ = set_active_ollama_model(&state, None);
        let status = response.status();
        let body = response
            .text()
            .await
            .unwrap_or_default();
        let body_short = body.trim().chars().take(220).collect::<String>();
        let detail = if body_short.is_empty() {
            format!("HTTP {}", status)
        } else {
            format!("HTTP {} — {}", status, body_short)
        };

        emit_runtime_progress(
            &app_handle,
            "ollama",
            "ready",
            100,
            format!("Avertissement warmup {} : {}. Le modele sera charge a la demande.", model, detail),
        )
        .await;

        return Ok(RuntimeActionResult {
            ok: true,
            detail: format!("Warmup echoue ({}), chargement a la demande au premier appel.", detail),
        });
    }

    let loaded = wait_for_ollama_model_loaded(&normalized_target, 20_000).await?;
    if !loaded {
        let _ = set_active_ollama_model(&state, None);
        emit_runtime_progress(
            &app_handle,
            "ollama",
            "error",
            100,
            format!("{} n a pas confirme son chargement en memoire.", model),
        )
        .await;
        return Err(format!("Le chargement de {} n a pas ete confirme par Ollama.", model));
    }

    set_active_ollama_model(&state, Some(normalized_target.clone()))?;

    emit_runtime_progress(
        &app_handle,
        "ollama",
        "ready",
        100,
        format!("{} est pret.", model),
    )
    .await;

    Ok(RuntimeActionResult {
        ok: true,
        detail: format!("{} est charge.", model),
    })
}

#[command]
pub async fn runtime_release_service(
    service: String,
    model: Option<String>,
    state: State<'_, RuntimeManagerState>,
    app_handle: AppHandle,
) -> Result<RuntimeServiceInfo, String> {
    match service.as_str() {
        "ollama" => {
            emit_runtime_progress(&app_handle, "ollama", "releasing", 92, "Liberation des modeles Ollama...").await;

            let unloaded = unload_ollama_models().await.unwrap_or(0);
            let _ = wait_for_ollama_models_unloaded(12_000).await;
            let _ = set_active_ollama_model(&state, None);
            let record = runtime_record(&state, "ollama");

            if record.started_by_app {
                if let Some(pid) = record.pid {
                    taskkill_pid(pid).await;
                }
                clear_runtime_record(&state, "ollama")?;
                emit_runtime_progress(&app_handle, "ollama", "stopped", 100, "Ollama arrete apres liberation.").await;
            } else {
                emit_runtime_progress(
                    &app_handle,
                    "ollama",
                    "ready",
                    100,
                    format!("{} modele(s) decharges, serveur conserve.", unloaded),
                )
                .await;
            }

            let mut snapshot = inspect_runtime_service(&state, "ollama").await;
            snapshot.detail = if snapshot.started_by_app {
                "Ollama gere par l application.".to_string()
            } else if unloaded > 0 {
                format!("{} modele(s) decharges, serveur laisse actif.", unloaded)
            } else if let Some(model_name) = model {
                format!("{} libere si charge, serveur laisse actif.", model_name)
            } else {
                "Aucune charge Ollama active.".to_string()
            };
            Ok(snapshot)
        }
        "comfyui" => {
            emit_runtime_progress(&app_handle, "comfyui", "releasing", 92, "Liberation de la VRAM ComfyUI...").await;

            let _ = free_comfyui_memory().await;
            let record = runtime_record(&state, "comfyui");

            if record.started_by_app {
                if let Some(pid) = record.pid {
                    taskkill_pid(pid).await;
                }
                clear_runtime_record(&state, "comfyui")?;
                emit_runtime_progress(&app_handle, "comfyui", "stopped", 100, "ComfyUI arrete apres liberation.").await;
            } else {
                emit_runtime_progress(&app_handle, "comfyui", "ready", 100, "ComfyUI libere, serveur conserve.").await;
            }

            let mut snapshot = inspect_runtime_service(&state, "comfyui").await;
            snapshot.detail = if snapshot.started_by_app {
                "ComfyUI gere par l application.".to_string()
            } else {
                "VRAM liberee, serveur laisse actif.".to_string()
            };
            Ok(snapshot)
        }
        _ => Err(format!("Service runtime inconnu: {}", service)),
    }
}

// ---------------------------------------------------------------------------
// Agent Pipeline State — gestion d'etat pour la fidelite au prompt initial
// Garantit que l'IA ne devie jamais du prompt initial au cours de ses
// iterations de correction (Architecte -> Codeur -> Auditeur).
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentPipelineSnapshot {
    pub original_prompt: String,
    pub current_phase: String,
    pub iteration: u32,
    pub active_role: String,
    pub architecture_plan_hash: Option<String>,
    pub files_generated: u32,
    pub errors_encountered: u32,
    pub last_error_summary: Option<String>,
}

#[derive(Default)]
pub struct AgentPipelineState {
    pub snapshot: Mutex<Option<AgentPipelineSnapshot>>,
}

#[command]
pub fn agent_pipeline_init(
    prompt: String,
    state: State<'_, AgentPipelineState>,
) -> Result<(), String> {
    let mut snapshot = state
        .snapshot
        .lock()
        .map_err(|_| "Agent pipeline lock failure".to_string())?;
    *snapshot = Some(AgentPipelineSnapshot {
        original_prompt: prompt,
        current_phase: "init".to_string(),
        iteration: 0,
        active_role: "architecte".to_string(),
        architecture_plan_hash: None,
        files_generated: 0,
        errors_encountered: 0,
        last_error_summary: None,
    });
    Ok(())
}

#[command]
pub fn agent_pipeline_update(
    phase: String,
    role: String,
    iteration: u32,
    files_generated: u32,
    errors_encountered: u32,
    last_error: Option<String>,
    state: State<'_, AgentPipelineState>,
) -> Result<(), String> {
    let mut snapshot = state
        .snapshot
        .lock()
        .map_err(|_| "Agent pipeline lock failure".to_string())?;
    if let Some(ref mut snap) = *snapshot {
        snap.current_phase = phase;
        snap.active_role = role;
        snap.iteration = iteration;
        snap.files_generated = files_generated;
        snap.errors_encountered = errors_encountered;
        snap.last_error_summary = last_error;
    }
    Ok(())
}

#[command]
pub fn agent_pipeline_get_prompt(
    state: State<'_, AgentPipelineState>,
) -> Result<Option<String>, String> {
    let snapshot = state
        .snapshot
        .lock()
        .map_err(|_| "Agent pipeline lock failure".to_string())?;
    Ok(snapshot.as_ref().map(|s| s.original_prompt.clone()))
}

#[command]
pub fn agent_pipeline_snapshot(
    state: State<'_, AgentPipelineState>,
) -> Result<Option<AgentPipelineSnapshot>, String> {
    let snapshot = state
        .snapshot
        .lock()
        .map_err(|_| "Agent pipeline lock failure".to_string())?;
    Ok(snapshot.clone())
}

// ---------------------------------------------------------------------------
// execute_and_capture_error — lance une commande shell et renvoie stdout/stderr
// separes + duree d'execution au frontend pour l'Auditeur
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecutionCapture {
    pub ok: bool,
    pub exit_code: i32,
    pub stdout: String,
    pub stderr: String,
    pub command: String,
    pub duration_ms: u64,
}

#[command]
pub async fn execute_and_capture_error(
    executable: String,
    args: Vec<String>,
    cwd: String,
    timeout_ms: Option<u64>,
) -> Result<ExecutionCapture, String> {
    let cwd_path = Path::new(&cwd);
    if !cwd_path.exists() {
        return Err(format!("Working directory not found: {}", cwd));
    }

    let start = std::time::Instant::now();

    let mut cmd = Command::new(&executable);
    cmd.current_dir(cwd_path);
    cmd.args(&args);
    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
    cmd.env("CI", "1");
    cmd.env("PYTHONUTF8", "1");
    cmd.env("HF_HUB_DISABLE_PROGRESS_BARS", "1");
    cmd.env("TOKENIZERS_PARALLELISM", "false");

    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to spawn command {}: {}", executable, e))?;

    let stdout_handle = child
        .stdout
        .take()
        .ok_or("Failed to capture stdout")?;
    let stderr_handle = child
        .stderr
        .take()
        .ok_or("Failed to capture stderr")?;

    let stdout_task = tokio::spawn(async move { read_process_output_lossy(stdout_handle).await });
    let stderr_task = tokio::spawn(async move { read_process_output_lossy(stderr_handle).await });

    let effective_timeout = timeout_ms.unwrap_or(120_000);
    let status = match tokio::time::timeout(
        std::time::Duration::from_millis(effective_timeout),
        child.wait(),
    )
    .await
    {
        Ok(wait_result) => wait_result.map_err(|e| format!("Process error: {}", e))?,
        Err(_) => {
            let _ = child.kill().await;
            return Ok(ExecutionCapture {
                ok: false,
                exit_code: -1,
                stdout: String::new(),
                stderr: format!(
                    "TIMEOUT: Command timed out after {}ms: {} {}",
                    effective_timeout,
                    executable,
                    args.join(" ")
                ),
                command: format!("{} {}", executable, args.join(" ")),
                duration_ms: start.elapsed().as_millis() as u64,
            });
        }
    };

    let stdout_output = stdout_task
        .await
        .map_err(|e| format!("Stdout task failed: {}", e))??;
    let stderr_output = stderr_task
        .await
        .map_err(|e| format!("Stderr task failed: {}", e))??;

    let full_command = if args.is_empty() {
        executable.clone()
    } else {
        format!("{} {}", executable, args.join(" "))
    };

    Ok(ExecutionCapture {
        ok: status.success(),
        exit_code: status.code().unwrap_or(-1),
        stdout: stdout_output.trim_end_matches('\n').to_string(),
        stderr: stderr_output.trim_end_matches('\n').to_string(),
        command: full_command,
        duration_ms: start.elapsed().as_millis() as u64,
    })
}
