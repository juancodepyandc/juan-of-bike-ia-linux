mod commands;
use reqwest;
use tauri::Manager;

fn encode_query(query: &str) -> String {
    let mut encoded = String::new();
    for byte in query.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'.' | b'_' | b'~' => {
                encoded.push(byte as char)
            }
            b' ' => encoded.push('+'),
            _ => encoded.push_str(&format!("%{:02X}", byte)),
        }
    }
    encoded
}

fn decode_html_entities(value: &str) -> String {
    value
        .replace("&amp;", "&")
        .replace("&quot;", "\"")
        .replace("&#x27;", "'")
        .replace("&#39;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
}

fn strip_html_tags(fragment: &str) -> String {
    let mut text = String::new();
    let mut in_tag = false;

    for character in fragment.chars() {
        match character {
            '<' => in_tag = true,
            '>' => in_tag = false,
            _ if !in_tag => text.push(character),
            _ => {}
        }
    }

    decode_html_entities(&text)
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn nearest_closing_tag(fragment: &str) -> Option<usize> {
    ["</a>", "</div>", "</span>", "</h2>"]
        .iter()
        .filter_map(|tag| fragment.find(tag))
        .min()
}

fn extract_class_texts(html: &str, class_name: &str, limit: usize) -> Vec<String> {
    let mut results = Vec::new();
    let mut remaining = html;

    while results.len() < limit {
        let Some(class_index) = remaining.find(class_name) else {
            break;
        };
        let after_class = &remaining[class_index..];
        let Some(tag_end) = after_class.find('>') else {
            break;
        };
        let content = &after_class[tag_end + 1..];
        let Some(close_index) = nearest_closing_tag(content) else {
            break;
        };
        let clean_text = strip_html_tags(&content[..close_index]);

        if !clean_text.is_empty() && !results.iter().any(|entry| entry == &clean_text) {
            results.push(clean_text);
        }

        remaining = &content[close_index..];
    }

    results
}

#[tauri::command]
async fn search_duckduckgo(query: String) -> Result<String, String> {
    let url = format!("https://html.duckduckgo.com/html/?q={}", encode_query(&query));
    let client = reqwest::Client::new();

    let res = client
        .get(url)
        .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        .send()
        .await
        .map_err(|e| e.to_string())?
        .text()
        .await
        .map_err(|e| e.to_string())?;

    let mut extracted = extract_class_texts(&res, "result__title", 8);
    extracted.extend(extract_class_texts(&res, "result__snippet", 8));

    let mut results = String::new();
    for clean_text in extracted.into_iter().take(15) {
        results.push_str("- ");
        results.push_str(&clean_text);
        results.push('\n');
    }

    if results.is_empty() {
        return Err("Le moteur de recherche n'a retourne aucun texte lisible.".into());
    }

    Ok(results)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(commands::RuntimeManagerState::default())
        .manage(commands::AgentPipelineState::default())
        .invoke_handler(tauri::generate_handler![
            search_duckduckgo,
            commands::ollama_chat,
            commands::ollama_generate,
            commands::ollama_list_models,
            commands::ollama_pull_model,
            commands::comfyui_request,
            commands::comfyui_queue_prompt,
            commands::comfyui_get_history,
            commands::comfyui_get_image,
            commands::detect_hardware,
            commands::inspect_host_resources,
            commands::get_host_privilege_status,
            commands::linux_runtime_check,
            commands::linux_runtime_install_missing,
            commands::restart_application_as_admin,
            commands::run_python_script,
            commands::run_workspace_command,
            commands::spawn_workspace_command_detached,
            commands::check_service_status,
            commands::get_workspace_path,
            commands::fs_exists,
            commands::fs_mkdir,
            commands::fs_read_text,
            commands::fs_write_text,
            commands::fs_write_binary,
            commands::fs_read_binary,
            commands::fs_remove_dir_all,
            commands::fs_list_dir,
            commands::runtime_inspect_services,
            commands::runtime_ensure_service,
            commands::runtime_ensure_ollama_model_available,
            commands::runtime_prepare_ollama_model,
            commands::runtime_release_service,
            commands::agent_pipeline_init,
            commands::agent_pipeline_update,
            commands::agent_pipeline_get_prompt,
            commands::agent_pipeline_snapshot,
            commands::execute_and_capture_error,
        ])
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();
            let _ = window.set_title("juan of bike IA");
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running juan of bike IA");
}
