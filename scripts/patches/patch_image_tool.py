import re

fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add generate_image to the prompt
old_prompt = """            "6. finish : Termine la mission.\\n"
            "   Args: { \\"message\\": \\"str\\" }\\n\\n\""""

new_prompt = """            "6. finish : Termine la mission.\\n"
            "   Args: { \\"message\\": \\"str\\" }\\n"
            "7. generate_image : Génère une image via l'API interne Aurora (ComfyUI) et la sauvegarde.\\n"
            "   Args: { \\"prompt\\": \\"str\\", \\"output_path\\": \\"str\\" }\\n\\n\""""

if old_prompt in code:
    code = code.replace(old_prompt, new_prompt)

# 2. Add generate_image logic in the loop
old_tool_logic = """                        elif t_name == "finish":
                            msg = t_args.get("message", "")
                            _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[MISSION TERMINÉE]: {msg}\\n"})
                            break"""

new_tool_logic = """                        elif t_name == "generate_image":
                            img_prompt = t_args.get("prompt", "")
                            out_path = t_args.get("output_path", "image.png")
                            abs_workspace = os.path.abspath(workspace)
                            abs_path = os.path.abspath(os.path.join(abs_workspace, out_path))
                            
                            _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[GÉNÉRATION IMAGE]: {img_prompt} -> {abs_path}\\n"})
                            
                            try:
                                import requests
                                import base64
                                # Appel local au backend ComfyUI
                                r = requests.post("http://127.0.0.1:3001/api/comfyui/image", json={"prompt": img_prompt}, timeout=300)
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
                                    result_str = f"Erreur ComfyUI: {r.text}"
                            except Exception as e:
                                result_str = f"Erreur de génération: {e}"

                        elif t_name == "finish":
                            msg = t_args.get("message", "")
                            _cli_mission_emit(mission_id, "token", {"content": f"\\n\\n[MISSION TERMINÉE]: {msg}\\n"})
                            break"""

if old_tool_logic in code:
    code = code.replace(old_tool_logic, new_tool_logic)
else:
    print("WARNING: Could not find old_tool_logic!")

with open(fp, "w", encoding="utf-8") as f:
    f.write(code)

print("Image tool patched!")
