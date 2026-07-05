# Rhubarb Lip Sync — installation

Rhubarb Lip Sync génère des cues phonémiques frame-accurate à partir d'un fichier WAV.
AuroraIA l'utilise automatiquement si `rhubarb.exe` est présent dans ce dossier.

## Téléchargement

1. Va sur : https://github.com/DanielSWolf/rhubarb-lip-sync/releases
2. Télécharge la dernière version pour **Windows** : `rhubarb-lip-sync-X.X.X-win32.zip`
3. Décompresse et copie **`rhubarb.exe`** dans ce dossier (`application/bin/rhubarb.exe`)

## Vérification

```bash
application/bin/rhubarb.exe --version
# → Rhubarb Lip Sync 1.13.0
```

## Sans Rhubarb

Si `rhubarb.exe` est absent, AuroraIA utilise automatiquement :
- La timeline phonémique text-based (analyse du texte TTS)
- Les formants RMS temps réel (Web Audio API)

Le lip sync fonctionnera, mais avec moins de précision frame-accurate.
