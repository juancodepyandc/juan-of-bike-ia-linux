# 🧠 SYSTEM PROMPT & ARCHITECTURE BLUEPRINT: AURORA IA AUTO-RL FRAMEWORK

**TARGET**: Assistant AI (Expert in Reinforcement Learning, PyTorch, and System Architecture)
**OBJECTIVE**: Design and implement the "Automatic Judges" (Reward Functions) and training loops for a fully autonomous Self-Play/RLHF training center (Project AuroraIA) supporting multiple generative modules (3D, Text/Code, Vision, Audio) on local hardware.

---

## 🛑 STRICT RULES (ZERO VIOLATION TOLERATED)
1. **THE UNTOUCHABLE ORIGINAL**: Base pre-trained models (e.g., Trellis, Qwen) MUST remain strictly read-only. Training creates a distinct `Reinforced_Model_vX`. 
2. **THE CONTINUOUS OVERWRITE**: If `Reinforced_Model_v(X+1)` strictly outperforms `vX` according to the Judge, `v(X+1)` replaces `vX`. The original base model remains forever intact as a fallback reference.
3. **ISOCAPABILITY TESTING**: All inferences used to compare models (Base vs Reinforced) MUST be generated using the exact same hardware constraints and generation parameters (batch size, steps, max tokens) representing the user's daily limits on an **RTX 5070 Ti**. Improvement must stem 100% from updated weights, not inflated generation parameters.
4. **ZERO EXTERNAL GROUND TRUTH**: The models must improve via Self-Play and Auto-Reflection. No human datasets are provided for fine-tuning. The AI must learn by maximizing the score given by the Autonomous Judges.
5. **ZERO REGRESSION**: Training loops must include catastrophic forgetting safeguards (e.g., KL divergence penalties against the base model).

---

## 🏗️ THE AUTONOMOUS JUDGES (YOUR TASK TO IMPLEMENT)

You must write the evaluation pipelines (Reward Functions) that will automatically score the outputs of each module during the RL loop (e.g., using PPO, DPO, or REINFORCE).

### 1. MODULE 3D (Trellis / Mesh Generation)
*Problem: Assessing 3D quality without ground-truth meshes.*
**Judge Requirements:**
- **Geometric Sanity Check**: Penalize non-manifold edges, flying disconnected fragments, and self-intersections (via `trimesh` or `open3d`).
- **Multi-View Coherence**: Render the generated `.glb` from 4 to 8 camera angles. Pass renders through a frozen local VLM/CLIP to score prompt alignment and structural logic (e.g., "Does this car have 4 wheels?").

### 2. MODULE CODE / TEXT (Qwen / LLMs)
*Problem: Assessing logic and correctness.*
**Judge Requirements:**
- **Execution Sandbox**: Automatically execute generated Python/C++ code in a secure container. `exit_code == 0` -> Positive reward. Tracebacks -> Negative reward.
- **Unit Test Generation**: The Judge must auto-generate edge-case asserts for the code based on the prompt.
- **Self-Correction Loop**: If code fails, feed the traceback back into the model. Reward the model inversely proportional to the number of attempts needed to fix it.

### 3. MODULE IMAGE (Stable Diffusion / Flux)
**Judge Requirements:**
- **Aesthetic & Artifact Scoring**: Use an Aesthetic Scorer (e.g., LAION Aesthetic Predictor) to penalize blur, bad anatomy, and noise.
- **Prompt Adherence**: Use CLIPScore or BLIP-2 to measure semantic alignment between the output image and the original prompt.

### 4. MODULE AUDIO / VOICE
**Judge Requirements:**
- **SNR (Signal-to-Noise Ratio)**: Penalize static, background noise, or clipping.
- **Transcription (ASR) Check**: Run Whisper on generated speech. If Whisper cannot transcribe it perfectly to match the intended prompt, penalize for lack of clarity.

---

## 🖥️ UI INTEGRATION (`cycle_app.py`)
The system must hook into the existing Tkinter GUI (`/home/juan/AuroraIA/cycle_app.py`). 
- The training loops must output real-time stats to `status.json` (Loss, Progress %, Judge Score).
- The GUI will handle the visualization of the `before.glb` vs `after.glb` (or code vs code) and manage the "Auto-Overwrite" toggle. Your training scripts must wait for a `validation_signal.txt` (ACCEPT/REJECT) if the UI is set to manual mode.

**ACTION REQUIRED FROM THE AI**: Write the optimized PyTorch code for these 4 Judge Modules and the central RL orchestration script that ties them to the base models. Keep the code heavily optimized for an RTX 5070 Ti (use gradient checkpointing, LoRA/QLoRA where applicable).
