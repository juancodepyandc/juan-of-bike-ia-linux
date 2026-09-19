#!/bin/bash
extract() {
    echo "Extracting $1 to $2..."
    python3 scripts/admin/extract_blueprint.py "$1" "$2" "application/routes/${2}_routes.py"
    cd application && .venv/bin/python -c "import bridge_server"
    if [ $? -ne 0 ]; then
        echo "Extraction failed for $1!"
        exit 1
    fi
    cd ..
}

extract "/api/code/repo/*" "repo_bp"
extract "/api/ext/*" "ext_bp"
extract "ComfyUI Proxy" "comfy_proxy_bp"
extract "Hardware / Runtime / Privilege" "hardware_bp"
extract "Services status" "status_bp"
extract "Web Action" "web_action_bp"
extract "Web search" "web_search_bp"
extract "Python progress" "python_prog_bp"
extract "Asset serving" "asset_bp"
extract "Ollama model listing" "ollama_list_bp"
extract "Upload — recevoir des fichiers" "upload_bp"
extract "ComfyUI lifecycle endpoints" "comfy_life_bp"
extract "Ollama — enhanced model list" "ollama_enh_bp"
extract "System info — extended" "sysinfo_bp"
extract "Cowork — file ops" "cowork_file_bp"
