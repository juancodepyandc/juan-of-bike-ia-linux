# Aurora Agents — Prompt → Lead Routing Gallery

Sample prompts and which lead they should auto-route to. Use this as a reference when refining `description` fields for better auto-trigger, or when training yourself on the architecture.

The orchestrator picks a lead based on the smallest set of modules a request touches. When a request is ambiguous, it should ask before dispatching.

---

## conversation-lead

> "La conversation se bloque au stage verify quand je parle en vocal."
> "Le fast path classifie pas les questions courtes correctement."
> "Le score fallback retombe à 86 alors qu'il devrait être 94."

→ pipeline issue → `conversation-pipeline-tuner`. Voice path → orchestrator should ALSO dispatch `voice-lead` in parallel.

## image-lead

> "Le prompt FLUX rend des homophones — 'cyclope souris' donne pas le bon sujet."
> "Ajoute un 16e style à ImageView."
> "Le character forge crash au warmup quand l'ordre des layers est inversé."

→ FLUX/forge → `image-flux-stylist`. Reference research → `image-reference-researcher`.

## code-lead

> "Le sandbox Rust ne build plus depuis hier."
> "Brand fidelity gate Rule 6 rate sur Mercedes-Benz à cause du tiret."
> "Ajoute un type de projet 'data_pytorch' avec specs ML."

→ sandbox → `code-sandbox-runner` | fidelity → `code-fidelity-auditor` | new project type → `code-design-architect`. Pour un sujet large, le lead fan-out 2-3 sub-agents en parallèle.

## video-lead

> "Le motion preset 'parallaxe' fige sur les images verticales."
> "MuseTalk crash quand on passe une wav 16kHz."

→ motion → `video-motion-director` | talking-head → `video-talking-head`. Wav format issue concerne aussi `voice-lead` (output PCM 24 kHz).

## drawing-lead

> "Le sketch n'influence plus le rendu, denoise trop bas."
> "Vision analyzer renvoie une description vide quand le canvas est presque vide."

→ `drawing-sketch-interpreter` direct.

## 3d-lead

> "Une nouvelle créature 'cheval ailé' rendue avec 4 pattes au sol au lieu de 2 + ailes."
> "Le routing a choisi photogrammetry sur 5 images, devrait être ai_generation."
> "Le viewer Three.js ne charge plus les .glb avec NLA action."

→ pipeline routing → `3d-pipeline-router` | motion/anatomy → `3d-motion-rigger` (et aussi update fixtures parser parity!) | mesh validation → `3d-mesh-postprocessor`.

## learning-lead

> "Les bonnes réponses du quiz sont parfois fausses, le quiz_verify passe pas."
> "Anki export crash avec un deck imbriqué profondeur 5."
> "LabPhysics simule des collisions instables à dt > 1/60."

→ quiz/flashcard → `learning-quiz-verifier` | bac/anki → `learning-bac-curator`. Lab instability → orchestrator dispatches `simulator-lead` (delegated_to par learning-lead).

## cowork-lead

> "Le planner cowork inclut un finish dans un plan read-only."
> "Ajoute un connecteur pour Notion."
> "SAFETY_LIMITS bloque un upload légitime de 12 MB."

→ planner → `cowork-orchestrator-tuner` | connector → `cowork-connector-keeper` | safety → `cowork-safety-auditor` (justification écrite obligatoire pour relâcher un cap).

## voice-lead

> "Voxtral STT ne charge plus depuis l'update, fallback Whisper actif."
> "Lip sync drift de 80 ms sur les voyelles ouvertes."

→ STT/TTS → `voice-tts-stt-tuner` | lip sync/formants/blob URL → `voice-lipsync`.

## cyber-lead

> "Le ForensicsLab freeze sur un fichier de 200 MB."
> "Hash brute dépasse le timeout sans message."
> "Network scan veut sortir du workspace."

→ UI lab → `cyber-lab-builder` | Python ops + safety → `cyber-pyops-keeper` (vérifier `_safety.py` cap appliqué).

## simulator-lead

> "physicsEngine non-déterministe — même seed, trajectoires différentes."
> "Preset 'pendule double' load casse depuis la migration types."

→ engine → `simulator-physics-engine` | scene IO → `simulator-scene-io`.

---

## Crosscut

> "Le tunnel renvoie 502 depuis 2 min."
→ `bridge-doctor` (diagnose first, run `update-aurora.bat` only with evidence).

> "Avant de commit, vérifie que la 3D génère encore."
→ `tunnel-validator` (curl + 13/13 + 17/17 + UI smoke).

---

## Multi-lead briefs (orchestrator parallel dispatch)

> "Audit complet du pipeline vocal (STT + TTS + lip sync + UI conversation)."
→ orchestrator dispatches `conversation-lead` + `voice-lead` in parallel; voice-lead fans out to both sub-agents.

> "Le drawing module ne génère plus le bon sujet ET le canvas figé."
→ orchestrator dispatches `drawing-lead` + `image-lead` (FLUX prompt build) + possibly `conversation-lead` (taskIntelligence) in parallel.

> "Vérifier toute l'archi avant la release: bridge OK, agents cohérents, tracker propre."
→ orchestrator dispatches `tunnel-validator` + invokes `python .claude/hooks/validate_agents.py` (or `/aurora-validate`).
