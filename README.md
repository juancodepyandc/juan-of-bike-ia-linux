# AuroraIA (juan of bike IA)

Studio d'IA **local** : une seule interface pour discuter, coder, générer des images et de la 3D, et utiliser la voix, sur ta propre machine, sans dépendre du cloud. L'application existe en version native (Tauri), en version web (via tunnel) et en terminal (CLI). La documentation est rédigée en français.

> **État du projet : jeune, en beta, maintenu par une seule personne.** Développé et testé surtout sous Linux (scripts Windows fournis). Les moteurs d'image et de 3D demandent une carte NVIDIA ; le développement se fait sur une RTX 5070 Ti de 16 Go, les besoins minimaux n'ont pas été mesurés.

## Les trois dépôts

Le projet est découpé en trois dépôts. C'est un seul et même projet.

| Dépôt | Rôle |
|---|---|
| **juan-of-bike-ia-linux** (celui-ci) | Application, serveur (« bridge »), missions, serveurs MCP |
| [aurora-remote-cli](https://github.com/juancodepyandc/aurora-remote-cli) | Client terminal `jobia` (local ou distant), paquet `jobia-cli` |
| [aurora-live](https://github.com/juancodepyandc/aurora-live) | Publie l'état et l'adresse du tunnel (pas de moteur) |

## Ce que contient ce dépôt

- `application/` : interface React + Vite + Three.js, enveloppe native Tauri, serveur bridge et services Python (reconnaissance vocale `faster-whisper`, synthèse `Kokoro`, génération d'image et de 3D).
- `agi_core/` : système de missions avec journal durable, checkpoints et reprise après arrêt.
- `mcp/` : serveurs MCP par domaine (`3d`, `business`, `cloud`, `code`, `core`, `cowork`, `cyber`, `image`, `learning`, `video`, `voice`).
- `interface/extension/extension_chrome/` : extension de navigateur de connexion.
- `auto_rl/`, `scripts/kaggle_sync/`, `notebooks/` : boucle d'entraînement et d'évaluation.
- `tests_agi/`, `tests_auto_rl/` : tests Python (CI sur Ubuntu, Windows et macOS, Python 3.10 et 3.13).

Les poids de modèles ne sont pas dans le dépôt. Chaque modèle (LLM via Ollama, FLUX.2, TRELLIS.2, etc.) a **sa propre licence**, à vérifier avant tout usage.

## Démarrage rapide

Prérequis : Python 3, Node.js, [Ollama](https://ollama.com), et pour l'image/3D un ComfyUI et une carte NVIDIA.

```bash
# dépendances des services Python
pip install -r application/python-services/requirements.txt

# lancer l'ensemble (Linux)
./start-aurora.sh            # Windows : scripts\ops\start-aurora.bat

# ou, depuis la racine, en développement
npm run dev                  # application native (Tauri)
npm run dev:web              # interface web seule (Vite)
npm run build                # build web
npm run tauri:build          # build natif
```

Ports utilisés par défaut : bridge `3001`, daemon de missions `3002`, Ollama `11434`, ComfyUI `8188`.

## CLI (`jobia`)

Le CLI est dans le dépôt [aurora-remote-cli](https://github.com/juancodepyandc/aurora-remote-cli) (Python ≥ 3.10).

```bash
git clone https://github.com/juancodepyandc/aurora-remote-cli
cd aurora-remote-cli && ./install.sh
jobia                                          # interface plein écran
jobia connect --server https://ADRESSE_DU_SERVEUR
jobia doctor --remote --json
jobia mission "Inspecte ce projet et prépare un plan"
jobia missions list | status ID | watch ID | stop ID | resume ID
```

## Tests

```bash
python -m pytest tests_agi tests_auto_rl -q    # tests Python
npm --prefix application run test:fx           # tests d'interface
npm --prefix application run typecheck         # types TypeScript
```

## Documentation

- [`ARCHITECTURE_MAITRE.md`](ARCHITECTURE_MAITRE.md) : document maître (architecture, routes, missions, CLI, tunnel, priorités d'amélioration).
- [`AGENTS.md`](AGENTS.md) : règles de travail du dépôt.
- Vérifier que le document maître est à jour : `python3 scripts/documentation/doc_master.py --check-code`.

## Sécurité

Le bridge peut exposer des fichiers, des commandes et des moteurs. L'audit complet des routes (authentification, origine, exposition du tunnel) est **en cours** et décrit dans la section « Constats et priorités » du document maître. **N'ouvre pas le tunnel à des tiers** tant que ce chantier n'est pas terminé. Pour signaler un problème, ouvre une issue sans y mettre de secret.

## Branches

- `main` : branche de référence.
- `claude/*` : branches de travail, déjà intégrées à `main`.
- `bolt*`, `perf/aurora-cowork-bubble-memo-*` : essais d'optimisation du rendu du chat (mémoïsation de `ChatBubble` et `ReactMarkdown`), en partie intégrés à `main`, à nettoyer.
- `feature/enforce-think-blocks-*` : test d'obligation de blocs `<think>` pour la génération de code, non fusionné.

## Contribuer

Les issues et les pull requests sont les bienvenues, en français ou en anglais. Lis d'abord `ARCHITECTURE_MAITRE.md` et `AGENTS.md`, et mets à jour le document maître quand une architecture ou un contrat change.

## Licence

Code original : [MIT](LICENSE).

Composants tiers, qui gardent leur propre licence :

- `application/engineering_viewer_assets/` : three.js, MIT.
- `application/python-services/_hy3dpaint/` : Tencent Hunyuan 3D 2.1 Community License (non OSI ; le texte précise qu'elle ne s'applique pas dans l'UE, au Royaume-Uni et en Corée du Sud).
