# Inventaire des poids vidéo Aurora

_Généré le 2026-07-26 18:17:07._

- Support froid monté : **non**
- Point configuré : `/mnt/aurora_models`
- Plancher de sécurité : **20.0 Go** par étage
- Sorties : **hot** (`/home/juan/AuroraIA/application/output/videos`)

| ID | Type | Taille déclarée | Étage | Disponible | Chemin actif |
|---|---:|---:|---:|---:|---|
| ollama-library | llm | 107.0 Go | hot | oui | `/usr/share/ollama/.ollama/models` |
| wan2.2-ti2v-5b | video | 32.0 Go | hot | oui | `/home/juan/.cache/huggingface/hub/models--Wan-AI--Wan2.2-TI2V-5B-Diffusers` |
| ltx-video | video | 33.0 Go | hot | oui | `/home/juan/.cache/huggingface/hub/models--Lightricks--LTX-Video` |
| chatterbox-candidate | orphan | 13.0 Go | hot | oui | `/home/juan/.cache/huggingface/hub/models--ResembleAI--chatterbox` |
| video-outputs | output | 0.0 Go | hot | non | `/home/juan/AuroraIA/application/output/videos` |

## État du setup

```json
{
  "ok": false,
  "reason": "cold_storage_offline",
  "mount_path": "/mnt/aurora_models",
  "action": "monter un support distinct avant tout déplacement; aucun formatage automatique"
}
```

Les licences sont documentées séparément et n'influencent pas la sélection
qualitative pour un usage personnel ; elles restent utiles si le déploiement
devient un jour public ou commercial.
