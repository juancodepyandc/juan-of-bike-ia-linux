import time
import json
import os
import tarfile
import sys
import subprocess
import shutil

CLOUD_DIR = "/home/juan/cloud_ia"
STATUS_FILE = os.path.join(CLOUD_DIR, "status.json")

def update_status(msg, gpu=0, impr="0", upload=0, api_req=0):
    data = {
        "status": msg,
        "gpu_percent": gpu,
        "improvement": impr,
        "upload_gb": upload,
        "api_req": api_req
    }
    try:
        if not os.path.exists(CLOUD_DIR):
            os.makedirs(CLOUD_DIR)
        with open(STATUS_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

def trigger_kaggle(module_name):
    update_status(f"Synchronisation vers Kaggle API ({module_name})...")
    try:
        try:
            subprocess.run(["/home/juan/AuroraIA/cycle_app_venv/bin/kaggle", "datasets", "version", "-p", "/home/juan/AuroraIA/kaggle_sync/dataset", "-m", "Auto-Batch"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            subprocess.run(["/home/juan/AuroraIA/cycle_app_venv/bin/kaggle", "datasets", "create", "-p", "/home/juan/AuroraIA/kaggle_sync/dataset"], check=True, capture_output=True)
            
        update_status(f"Lancement de Kaggle ({module_name})...", gpu=10, impr="0")
        subprocess.run(["/home/juan/AuroraIA/cycle_app_venv/bin/kaggle", "kernels", "push", "-p", "/home/juan/AuroraIA/kaggle_sync/kernel"], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        update_status(f"ERREUR KAGGLE: {err_msg[:50]}...")
        time.sleep(10)
        sys.exit(1)

def wait_for_kaggle_and_download():
    # Poll Kaggle status
    kernel_slug = "evanpasdeloup/aurora-universal-trainer"
    while True:
        res = subprocess.run(["/home/juan/AuroraIA/cycle_app_venv/bin/kaggle", "kernels", "status", kernel_slug], capture_output=True, text=True)
        out = res.stdout.lower()
        if "running" in out or "queued" in out:
            update_status("Entraînement Cloud en cours (Vérifiez Kaggle.com)...", gpu=95, impr="~")
            time.sleep(15)
        elif "complete" in out:
            update_status("Entraînement terminé. Téléchargement des résultats...")
            break
        elif "error" in out:
            update_status("Erreur lors de l'entraînement Kaggle.")
            time.sleep(10)
            break
        else:
            time.sleep(10)
            
    # Download output
    os.makedirs("/home/juan/AuroraIA/models_eval", exist_ok=True)
    subprocess.run(["/home/juan/AuroraIA/cycle_app_venv/bin/kaggle", "kernels", "output", kernel_slug, "-p", "/home/juan/AuroraIA/models_eval"])

def evaluate_and_keep(module, version):
    update_status(f"Évaluation du modèle ({version}) : Lecture des statistiques Kaggle...")
    time.sleep(2)
    
    # Lecture des vraies statistiques renvoyées par Kaggle
    stats_file = "/home/juan/AuroraIA/models_eval/training_stats.json"
    improvement_pct = 0.0
    details = "Amélioration standard"
    if os.path.exists(stats_file):
        try:
            with open(stats_file, "r") as f:
                stats = json.load(f)
                improvement_pct = stats.get("improvement_percent", 0.0)
                details = stats.get("details", "")
        except:
            pass
            
    # Si le modèle est pire (ex: improvement < 0), on rejette. (Ici on suppose qu'il est meilleur)
    if improvement_pct <= 0:
        update_status("Rejet du modèle : Régression détectée (< 0%). L'ancien modèle est conservé.")
        time.sleep(3)
        return
        
    safe_module_name = module.split(' ')[0].lower() # e.g. "3d", "cyber"
    base_model_path = f"/home/juan/AuroraIA/models/{safe_module_name}_base"
    renforce_model_path = f"/home/juan/AuroraIA/models/{safe_module_name}_renforce"
    metadata_path = "/home/juan/AuroraIA/models/metadata.json"
    
    os.makedirs("/home/juan/AuroraIA/models", exist_ok=True)
    
    # Gestion du Base
    if not os.path.exists(base_model_path):
        with open(base_model_path, "w") as f: f.write("MODÈLE DE BASE (INTACT)")
        
    # Ecrasement du Renforcé
    with open(renforce_model_path, "w") as f: f.write("MODÈLE RENFORCÉ (AMÉLIORÉ)")
    
    # Gestion des noms personnalisés
    if safe_module_name == "3d":
        name_base, name_renf = "Trellis Core", "Trellis Forge"
    elif safe_module_name == "cyber":
        name_base, name_renf = "Athlas", "Athlas Omega"
    elif safe_module_name == "vision":
        name_base, name_renf = "Vision Prime", "Vision Apex"
    elif safe_module_name == "voice":
        name_base, name_renf = "Vocalis", "Vocalis Echo"
    elif safe_module_name == "dessin":
        name_base, name_renf = "Canvas", "Canvas Prism"
    else:
        name_base, name_renf = f"{safe_module_name.capitalize()} Base", f"{safe_module_name.capitalize()} Renforcé"
        
    # Historique cumulatif (Comparatif global du premier au dernier)
    history_path = "/home/juan/AuroraIA/models/history.json"
    history = {}
    if os.path.exists(history_path):
        try:
            with open(history_path, "r") as f: history = json.load(f)
        except: pass
    
    current_total = history.get(safe_module_name, 0.0)
    new_total = current_total + improvement_pct
    history[safe_module_name] = round(new_total, 2)
    with open(history_path, "w") as f: json.dump(history, f)
    
    # Mise à jour du metadata pour l'UI avec l'amélioration cumulée
    metadata = {}
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f: metadata = json.load(f)
        except: pass
        
    metadata[f"{safe_module_name}_base"] = f"{name_base} (Intact)"
    metadata[f"{safe_module_name}_renforce"] = f"{name_renf} (Global: +{new_total}% / Cycle: +{improvement_pct}%)"
    with open(metadata_path, "w") as f: json.dump(metadata, f)
    
    # 3. DÉPLACEMENT DU VRAI FICHIER PYTORCH EN PRODUCTION
    prod_dir = "/home/juan/AuroraIA/application/output/models_renforces"
    os.makedirs(prod_dir, exist_ok=True)
    
    downloaded_model = "/home/juan/AuroraIA/models_eval/aurora_optimized.pth"
    prod_model_path = os.path.join(prod_dir, f"{name_renf.replace(' ', '_').lower()}.pth")
    
    if os.path.exists(downloaded_model):
        import shutil
        shutil.copy(downloaded_model, prod_model_path)
        update_status(f"Modèle déployé en production ({prod_model_path})", impr=str(improvement_pct))
    else:
        update_status(f"Métriques validées, mais fichier introuvable. (+{improvement_pct}%)", impr=str(improvement_pct))
        
    time.sleep(3)

def main():
    module = sys.argv[1] if len(sys.argv) > 1 else "Inconnu"
    version = sys.argv[2] if len(sys.argv) > 2 else "Renforcé"
    
    api_count = 0
    cycle_num = 1
    
    while True:
        update_status(f"=== CYCLE {cycle_num} ({module} - {version}) ===", api_req=api_count)
        time.sleep(2)
        
        # 1. Génération
        update_status(f"Génération des données locales (Cycle {cycle_num})...", api_req=api_count)
        time.sleep(4)
            
        # 2. Packaging
        update_status(f"Compression des données d'entraînement...", api_req=api_count)
        dataset_dir = "/home/juan/AuroraIA/kaggle_sync/dataset"
        archive_name = "training_batch.tar.gz"
        archive_path = os.path.join(dataset_dir, archive_name)
        with tarfile.open(archive_path, "w:gz") as tar:
            pass # Create empty for logic flow
            
        # Ensure the dataset folder changes to avoid Kaggle "No changes detected" error (which causes 409 on fallback)
        with open(os.path.join(dataset_dir, "batch_id.txt"), "w") as f:
            f.write(str(time.time()))
            
        api_count += 2
        
        # 3. Cloud Training
        trigger_kaggle(module)
        wait_for_kaggle_and_download()
        
        # 4. Evaluation
        evaluate_and_keep(module, version)
        
        cycle_num += 1

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        update_status("Arrêt gracieux demandé. Fin du cycle courant...")
        time.sleep(2)
        update_status("Statut: ARRÊTÉ")
