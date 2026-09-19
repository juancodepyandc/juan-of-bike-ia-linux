#!/usr/bin/env python3
"""
Wrapper unifié pour lancer la CLI Aurora locale.
Ce script redirige vers la même suite CLI (aurora-remote-cli) pour garantir 
l'objectif de parité totale et "zéro duplication" avec le client distant.
"""
import os
import sys

def main():
    remote_cli_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aurora-remote-cli")
    
    if remote_cli_path not in sys.path:
        sys.path.insert(0, remote_cli_path)
        
    try:
        from aurora_cli.cli import main as cli_main
    except ImportError:
        print(f"Erreur: Impossible de charger aurora-remote-cli depuis {remote_cli_path}.")
        print("Vérifiez que le dossier aurora-remote-cli existe bien au même niveau que AuroraIA.")
        sys.exit(1)
        
    # Surcharge la configuration pour pointer par défaut sur le localhost
    os.environ["AURORA_SERVER_URL"] = "http://127.0.0.1:3001"
    
    print("Démarrage de la CLI unifiée (mode local)...")
    cli_main()

if __name__ == "__main__":
    main()
