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

extract "Asset serving" "asset_bp"
extract "Ollama model listing" "ollama_list_bp"
extract "Upload — recevoir des fichiers" "upload_bp"
extract "ComfyUI lifecycle endpoints" "comfy_life_bp"
extract "Ollama — enhanced model list" "ollama_enh_bp"
extract "System info — extended" "sysinfo_bp"
extract "Cowork — file ops" "cowork_file_bp"
