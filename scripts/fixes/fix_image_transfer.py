import re

fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

old_logic = """                                r = requests.post("http://127.0.0.1:3001/api/aurora/image/generate", json={"prompt": img_prompt}, timeout=300)
                                if r.status_code == 200:
                                    b64data = r.json().get("image")
                                    if b64data:
                                        img_bytes = base64.b64decode(b64data)
                                        # Si distant, on l'envoie au Mac via un write_file binaire ? Non, via file_transfer !
                                        if is_remote_workspace:
                                            _cli_mission_emit(mission_id, "file_transfer", {"filename": os.path.basename(abs_path), "data": b64data})
                                            result_str = f"Image générée et transférée sur le bureau de l'utilisateur."
                                        else:
                                            with open(abs_path, "wb") as f:
                                                f.write(img_bytes)
                                            result_str = f"Image générée avec succès : {abs_path}"
                                    else:
                                        result_str = "Erreur: Pas de données d'image dans la réponse."
                                else:
                                    result_str = f"Erreur ComfyUI: {r.text}\""""

new_logic = """                                r = requests.post("http://127.0.0.1:3001/api/aurora/image/generate", json={"prompt": img_prompt}, timeout=300)
                                if r.status_code == 200:
                                    img_path_on_linux = r.json().get("path")
                                    if img_path_on_linux and os.path.isfile(img_path_on_linux):
                                        with open(img_path_on_linux, "rb") as img_f:
                                            b64data = base64.b64encode(img_f.read()).decode('utf-8')
                                        if is_remote_workspace:
                                            _cli_mission_emit(mission_id, "file_transfer", {"filename": os.path.basename(abs_path), "data": b64data})
                                            result_str = f"Image générée et transférée dans le dossier de travail du Mac."
                                        else:
                                            import shutil
                                            shutil.copy2(img_path_on_linux, abs_path)
                                            result_str = f"Image générée avec succès : {abs_path}"
                                    else:
                                        result_str = "Erreur: Chemin d'image manquant ou fichier introuvable dans la réponse."
                                else:
                                    result_str = f"Erreur moteur image: {r.text}\""""

if old_logic in code:
    code = code.replace(old_logic, new_logic)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(code)
    print("Fixed bridge_server.py image generation reading logic.")
else:
    print("WARNING: Could not find old_logic in bridge_server.py!")
    # let's find it with grep if needed
