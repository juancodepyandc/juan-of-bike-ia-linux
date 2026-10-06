//! Read only the bounded output of the current startup attempt.
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;

const TAIL_BYTES: u64 = 4096;

pub fn log_offset(path: &Path) -> u64 {
    path.metadata().map(|metadata| metadata.len()).unwrap_or(0)
}

fn attempt_tail(path: &Path, offset: u64) -> String {
    let Ok(mut file) = File::open(path) else { return String::new() };
    let length = file.metadata().map(|metadata| metadata.len()).unwrap_or(0);
    // A truncated/replaced log starts a new attempt at zero.
    let offset = if length < offset { 0 } else { offset };
    let start = offset.max(length.saturating_sub(TAIL_BYTES));
    if file.seek(SeekFrom::Start(start)).is_err() { return String::new() }
    let mut bytes = Vec::new();
    if file.take(TAIL_BYTES).read_to_end(&mut bytes).is_err() { return String::new() }
    String::from_utf8_lossy(&bytes).trim().to_string()
}

pub fn comfy_startup_error(directory: &Path, stdout_offset: u64, stderr_offset: u64, reason: &str) -> String {
    let stdout = directory.join("comfyui_stdout.log");
    let stderr = directory.join("comfyui_stderr.log");
    let mut detail = attempt_tail(&stderr, stderr_offset);
    if detail.is_empty() { detail = attempt_tail(&stdout, stdout_offset); }
    let lowered = detail.to_lowercase();
    let hint = if lowered.contains("no cuda gpus") || lowered.contains("found no nvidia driver") {
        " Le runtime CUDA ne voit aucun GPU utilisable. Verifie le pilote NVIDIA avec nvidia-smi sur le serveur."
    } else { "" };
    format!("{reason}{hint}\n{detail}\nJournaux: {}, {}", stdout.display(), stderr.display())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn current_attempt_does_not_reuse_a_previous_cuda_error() {
        let directory = std::env::temp_dir().join(format!("aurora-runtime-log-{}", std::process::id()));
        fs::create_dir_all(&directory).unwrap();
        let stderr = directory.join("comfyui_stderr.log");
        fs::write(&stderr, "RuntimeError: No CUDA GPUs are available\n").unwrap();
        let offset = log_offset(&stderr);
        let message = comfy_startup_error(&directory, 0, offset, "ComfyUI a quitte.");
        assert!(!message.contains("aucun GPU"));
        assert!(!message.contains("RuntimeError"));
        fs::write(&stderr, "fresh: missing node\n").unwrap();
        let message = comfy_startup_error(&directory, 0, offset, "ComfyUI a quitte.");
        assert!(message.contains("fresh: missing node"));
        fs::write(&stderr, format!("{}\nRuntimeError: No CUDA GPUs are available\n", "x".repeat(8000))).unwrap();
        let message = comfy_startup_error(&directory, 0, 0, "ComfyUI a quitte.");
        assert!(message.contains("nvidia-smi"));
        assert!(message.contains("RuntimeError"));
        assert!(message.len() < 5000);
        fs::remove_dir_all(directory).unwrap();
    }
}
