import re

fp = "/home/juan/AuroraIA/application/bridge_server.py"
with open(fp, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Remove the forced fallback to /home/juan, we WANT the remote workspace string!
old_fallback = """        # Safe fallback if workspace is an invalid Mac path on Linux
        if not workspace.startswith("/") or not os.path.exists(os.path.dirname(workspace)):
            workspace = "/home/juan"
            mission["workspace"] = workspace"""

code = code.replace(old_fallback, """        # We preserve the workspace exactly as given by the Mac client
        is_remote_workspace = (not workspace.startswith("/home/") and not workspace.startswith("/tmp/"))""")

# 2. Update the system prompt
old_prompt = """            "CRUCIAL : L'utilisateur est sur un Mac distant, mais toi tu tournes sur un serveur Linux.\\n"
            "NE CRÉE JAMAIS de dossier 'Bureau', 'Desktop' ou 'test_ia' sur ton serveur Linux !\\n"
            "Pour livrer un fichier sur le Mac de l'utilisateur, écris le fichier DIRECTEMENT dans le dossier magique `.transfer_to_client/`. Il sera téléporté sur son vrai Bureau.\\n\""""

new_prompt = """            "CRUCIAL : L'utilisateur est sur un Mac distant.\\n"
            "MAGIE : Grâce au nouveau pont bidirectionnel, tes outils 'run_command', 'read_file' et 'write_file' s'exécutent MAINTENANT DIRECTEMENT SUR LE MAC DE L'UTILISATEUR si le dossier de travail est distant (ex: /Users/...).\\n"
            "Tu n'as plus besoin du dossier .transfer_to_client. Écris, lis et lance tes commandes directement, elles auront lieu sur la machine de l'utilisateur.\\n\""""

code = code.replace(old_prompt, new_prompt)

# 3. Modify the tool execution block
# We need to find the tool execution loop. Let's see how it's structured.
