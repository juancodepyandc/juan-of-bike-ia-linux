import os

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

target = """                        elif t_name == "write_file":
                            path = os.path.join(workspace, t_args.get("path", ""))
                            os.makedirs(os.path.dirname(path), exist_ok=True)
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(t_args.get("content", ""))
                            result_str = f"Fichier {path} écrit avec succès."
                            _cli_mission_emit(mission_id, "file_diff", {"filename": path, "diff": [f"+ {path} écrit."]})
                            
                        elif t_name == "read_file":
                            path = os.path.join(workspace, t_args.get("path", ""))
                            if os.path.exists(path):
                                with open(path, "r", encoding="utf-8") as f:
                                    result_str = f.read()[:5000]
                            else:
                                result_str = f"Erreur : Fichier non trouvé {path}" """

replacement = """                        elif t_name == "write_file":
                            raw_path = t_args.get("path", "")
                            # Sécurisation : résolution du chemin absolu
                            abs_workspace = os.path.abspath(workspace)
                            abs_path = os.path.abspath(os.path.join(abs_workspace, raw_path))
                            
                            # Vérification que le chemin reste dans le workspace (anti-path traversal)
                            if not abs_path.startswith(abs_workspace):
                                result_str = "Erreur de sécurité : L'accès en dehors du dossier de travail (workspace) est interdit."
                            else:
                                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                                with open(abs_path, "w", encoding="utf-8") as f:
                                    f.write(t_args.get("content", ""))
                                result_str = f"Fichier {abs_path} écrit avec succès."
                                _cli_mission_emit(mission_id, "file_diff", {"filename": abs_path, "diff": [f"+ {abs_path} écrit."]})
                            
                        elif t_name == "read_file":
                            raw_path = t_args.get("path", "")
                            abs_workspace = os.path.abspath(workspace)
                            abs_path = os.path.abspath(os.path.join(abs_workspace, raw_path))
                            
                            if not abs_path.startswith(abs_workspace):
                                result_str = "Erreur de sécurité : L'accès en dehors du dossier de travail (workspace) est interdit."
                            elif os.path.exists(abs_path):
                                with open(abs_path, "r", encoding="utf-8") as f:
                                    result_str = f.read()[:5000]
                            else:
                                result_str = f"Erreur : Fichier non trouvé {abs_path}" """

code = code.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Workspace security patched")
