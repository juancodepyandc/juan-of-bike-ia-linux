"""Students: the models Aurora really calls, mapped to trainable weights.

Every entry was read from the application code (file and line in ``called_by``)
and checked on the Hugging Face Hub on 2026-11-11. A LoRA adapter is only
deployable on the exact base it was trained on, so a student trained here is
promoted to the Ollama tag of the SAME entry and to no other model.

``four_bit_gb`` is an estimate used only to refuse an obviously impossible run;
admission still relies on memory measured on the machine.

``expert_tensors`` marks the mixture-of-experts models whose expert weights are
grouped tensors in current Transformers (not linear layers): bitsandbytes leaves
them at 16 bits, so the model needs ``full_gb`` of GPU memory instead of
``four_bit_gb``. Observed on 2026-11-12: ``qwen3-coder:30b`` was refused on two
T4s ("modules are dispatched on the CPU") after its 61 GB download.
"""
from __future__ import annotations

STUDENTS = {
    "qwen2.5:7b": {
        "hf": "Qwen/Qwen2.5-7B-Instruct", "revision": "a09a35458c702b33eeacc393d103063234e8bc28",
        "params_b": 7.62, "four_bit_gb": 6.0, "modules": ["business", "media", "conversation"],
        "called_by": ["agi_core/prompt_intelligence.py:415 (directeur de prompts image/3D)",
                      "application/business_intelligence.py:3148 (chat Business, AURORA_MAIN_MODEL)"],
    },
    "qwen2.5-coder:7b": {
        "hf": "Qwen/Qwen2.5-Coder-7B-Instruct", "revision": "c03e6d358207e414f1eca0bb1891e29f1db0e242",
        "params_b": 7.62, "four_bit_gb": 6.0, "modules": ["code", "missions"],
        "called_by": ["agi_core/agi_brain.py:429 (cerveau AGI)"],
    },
    "qwen3-coder:30b": {
        "hf": "Qwen/Qwen3-Coder-30B-A3B-Instruct", "revision": "b2cff646eb4bb1d68355c01b18ae02e7cf42d120",
        "params_b": 30.53, "four_bit_gb": 19.0, "expert_tensors": True, "full_gb": 61.0,
        "modules": ["code", "missions", "cowork"], "attention_only": True,
        "called_by": ["application/src/config/models.ts:50-56 (Code local)", "application/bridge_server.py:811 (missions CLI)"],
    },
    "qwen3-coder-next:q4_K_M": {
        "hf": "Qwen/Qwen3-Coder-Next", "revision": "a7fbcb5c0e12d62a448eaa0e260346bf5dcc0feb",
        "params_b": 79.67, "four_bit_gb": 48.0, "modules": ["code", "missions"], "attention_only": True,
        "called_by": ["agi_core/llm_gateway.py:118 (défaut du gateway)", "application/src/config/models.ts:47"],
    },
    "orcarouter/Qwen3.8-27B-Uncensored": {
        "hf": "orcarouter/Qwen3.8-27B-Uncensored", "revision": "0f639a9bde23fe229a7b064b40a5153c5bec0b48",
        "params_b": 27.78, "four_bit_gb": 18.0, "gated": True, "vision": True,
        "modules": ["conversation", "academy", "cyber", "cowork", "business", "media", "engineering"],
        "called_by": ["application/src/config/models.ts:10 (modèle principal)"],
    },
    "qwen3-vl:8b": {
        "hf": "Qwen/Qwen3-VL-8B-Instruct", "revision": "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b",
        "params_b": 8.77, "four_bit_gb": 7.0, "vision": True, "modules": ["missions"],
        "called_by": ["application/src/config/models.ts:31 (vision temps réel)", "missions inspect_browser / inspect_image"],
    },
    "qwen3-vl:30b": {
        "hf": "Qwen/Qwen3-VL-30B-A3B-Instruct", "revision": "9c4b90e1e4ba969fd3b5378b57d966d725f1b86c",
        "params_b": 31.07, "four_bit_gb": 20.0, "expert_tensors": True, "full_gb": 62.0, "vision": True, "attention_only": True,
        "modules": ["media"],
        "called_by": ["application/src/config/models.ts:12,30 (vision par défaut)"],
    },
    "deepseek-r1:32b": {
        "hf": "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B", "revision": "711ad2ea6aa40cfca18895e8aca02ab92df1a746",
        "params_b": 32.76, "four_bit_gb": 21.0, "thinking": True, "modules": ["cyber", "academy", "code"],
        "called_by": ["application/src/config/models.ts:23,39,58,79 (raisonnement, vérification)"],
    },
}

#: Small public models of the same families, used ONLY to prove the pipeline on
#: a CPU or a small GPU. No Aurora module calls them: they are never promoted.
REHEARSAL = {
    "qwen3:0.6b": {"hf": "Qwen/Qwen3-0.6B", "revision": "c1899de289a04d12100db370d81485cdf75e47ca", "params_b": 0.6, "four_bit_gb": 1.0},
    "qwen2.5:0.5b": {"hf": "Qwen/Qwen2.5-0.5B-Instruct", "revision": "7ae557604adf67be50417f59c2c2f167def9a775", "params_b": 0.49, "four_bit_gb": 1.0},
    "qwen2.5:1.5b": {"hf": "Qwen/Qwen2.5-1.5B-Instruct", "revision": "989aa7980e4cf806f80c7fef2b1adb7bc71aa306", "params_b": 1.54, "four_bit_gb": 1.8},
}


def resolve(name):
    """Look a student up by Ollama tag or Hugging Face id. Unknown ids are refused:
    training an unlisted model would produce an adapter no module can use."""
    for table, production in ((STUDENTS, True), (REHEARSAL, False)):
        for tag, entry in table.items():
            if name in (tag, entry["hf"]):
                return {"tag": tag, "production": production, **entry}
    raise KeyError(f"Unknown student {name!r}; known: {sorted(STUDENTS) + sorted(REHEARSAL)}")


def memory_needed(entry, *, training):
    """GiB of GPU memory a run needs: the 4-bit size, or the 16-bit size where 4 bits cannot be applied."""
    weights = entry["full_gb"] if entry.get("expert_tensors") else entry["four_bit_gb"]
    return weights + (5.0 if training else 2.0)


def fits(entry, gpus, *, training):
    """Coarse feasibility from measured free VRAM (GiB per device); the run still measures for real."""
    if not gpus:
        return entry["params_b"] <= 2.0            # CPU rehearsal only
    usable = sum(max(0.0, free - 1.5) for free in gpus)
    return usable >= memory_needed(entry, training=training)


def choose(module, gpus, *, training=True):
    """Largest production student of a module that fits the measured memory, or ``None``."""
    candidates = [{"tag": tag, "production": True, **entry} for tag, entry in STUDENTS.items()
                  if module in entry["modules"] and not entry.get("vision") and fits(entry, gpus, training=training)]
    return max(candidates, key=lambda entry: entry["params_b"]) if candidates else None
