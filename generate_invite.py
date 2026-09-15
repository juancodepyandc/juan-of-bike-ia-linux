#!/usr/bin/env python3
import base64
import json
import os
import secrets
import hashlib
from pathlib import Path

# Fonction simple pour générer un code d'invitation sécurisé
def generate():
    print("=========================================")
    print("  Générateur d'Invitation Aurora Remote  ")
    print("=========================================")
    
    # 1. Lire l'URL du tunnel
    tunnel_file = Path("tunnel.txt")
    if not tunnel_file.exists():
        tunnel_file = Path("tunnel_url.txt")
        
    url = ""
    if tunnel_file.exists():
        url = tunnel_file.read_text().strip()
    
    if not url or "trycloudflare" not in url:
        print("⚠️ Impossible de lire l'URL du tunnel cloudflare automatiquement.")
        url = input("Entrez l'URL du tunnel manuellement (ex: https://xxx.trycloudflare.com) : ").strip()

    url = url.rstrip("/")

    # 2. Lire la clé API (le secret admin)
    # Pour faire simple, on va utiliser la première clé Bearer disponible dans la DB 
    # ou demander à l'utilisateur d'en coller une s'il préfère.
    print("\nVeuillez générer une clé Bearer depuis le frontend ou via l'API, ou utilisez la clé maître.")
    key = input("Entrez la clé API Bearer (laissez vide pour générer une clé temporaire) : ").strip()
    
    if not key:
        print("⏳ Génération d'une clé API unique...")
        raw_token = "aurora_" + secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Injection dans la BDD sqlite du bridge
        import sqlite3
        db_path = Path("application/aurora.db")
        if db_path.exists():
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("INSERT INTO api_keys (key_hash, label, expires_at) VALUES (?, ?, ?)", (token_hash, "CLI_INVITE", None))
                conn.commit()
                conn.close()
                key = raw_token
                print("✅ Clé temporaire générée et injectée dans la base.")
            except Exception as e:
                print(f"❌ Impossible d'injecter la clé: {e}")
                return
        else:
            print("❌ Base de données introuvable. Veuillez fournir une clé manuellement.")
            return

    # 3. Construire et Encoder
    data = {"u": url, "k": key}
    invite_code = base64.b64encode(json.dumps(data).encode()).decode('utf-8')
    
    print("\n✅ Code d'invitation généré avec succès !")
    print("Envoyez cette instruction à votre collaborateur :")
    print("\n--------------------------------------------------")
    print("1. Installe le client CLI : https://github.com/juancodepyandc/aurora-remote-cli")
    print("2. Lance la commande : aurora connect")
    print(f"3. Colle ce code : {invite_code}")
    print("--------------------------------------------------\n")

if __name__ == "__main__":
    generate()
