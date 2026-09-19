import re
import shlex

file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

# Fix 1: The sudo bug where && drops privileges
target_sudo = """                                # We have the pwd. We prepend sudo -S and pass pwd via stdin.
                                cmd = f"sudo -S {cmd}"
"""
replacement_sudo = """                                # We have the pwd. We prepend sudo -S and pass pwd via stdin.
                                # Use bash -c to ensure && chains run entirely as root
                                import shlex
                                cmd = f"sudo -S bash -c {shlex.quote(cmd)}"
"""
code = code.replace(target_sudo, replacement_sudo)

# Fix 2: Prevent the AI from making fake Desktop folders on the Linux server
target_prompt = """            "CRUCIAL: Pour ENVOYER des fichiers générés à l'utilisateur (ex: rapports sur son bureau), place-les UNIQUEMENT dans le dossier caché `.transfer_to_client/`. Ils lui seront transmis magiquement à la fin.\\n\""""

replacement_prompt = """            "CRUCIAL : L'utilisateur est sur un Mac distant, mais toi tu tournes sur un serveur Linux.\\n"
            "NE CRÉE JAMAIS de dossier 'Bureau', 'Desktop' ou 'test_ia' sur ton serveur Linux !\\n"
            "Pour livrer un fichier sur le Mac de l'utilisateur, écris le fichier DIRECTEMENT dans le dossier magique `.transfer_to_client/`. Il sera téléporté sur son vrai Bureau.\\n\""""

code = code.replace(target_prompt, replacement_prompt)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Sudo and Prompt patched")
