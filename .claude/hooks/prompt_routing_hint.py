#!/usr/bin/env python3
"""UserPromptSubmit hook for AuroraIA-v2 multi-agent tracker.

Reads the user's prompt and, if it contains keywords associated with one or
more module leads, returns a one-line hint via additionalContext suggesting
which lead(s) the orchestrator should consider. Non-blocking — does not
modify the prompt or stop processing. Stays silent when no keyword matches.

Strict matching: only triggers on whole-word matches (case-insensitive),
ignoring keywords inside obviously unrelated contexts. Tuned for high
precision over recall — a quiet hint is better than a noisy one.
"""

from __future__ import annotations

import json
import re
import sys


# Keyword → lead mapping. Keep specific. Generic words ("model", "code") would
# trigger too broadly; module names + module-specific tech are the safe bets.
LEAD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "conversation-lead": (
        "conversationorchestrator", "fast path", "voicemode",
        "verify+refine", "skiprelease", "narration",
    ),
    "image-lead": (
        "flux", "comfyui", "characterforge", "forge_layers",
        "generationprompt", "image style", "image styles",
    ),
    "code-lead": (
        "codeorchestrator", "codesandbox", "codeintent", "brand fidelity",
        "productshape", "shader", "starter template", "isllmrefusal",
        "qwen3-coder",
    ),
    "video-lead": (
        "wan2.2", "i2v", "t2v", "motion preset", "musetalk", "sadtalker",
        "talking head", "talkinghead",
    ),
    "drawing-lead": (
        "denoise", "sketch", "drawingview", "analyzesketch",
    ),
    "3d-lead": (
        "hunyuan3d", "dreamgaussian", "meshroom", "rigify", "blender",
        "kinematicslibrary", "motionpipeline", "motion_baker", "motion_parser",
        "subjectanatomy", "pbrprofile", "meshpostprocess", "auto-rig",
        "quadruped", "humanoid", "creature",
    ),
    "learning-lead": (
        "learningview", "quiz_verify", "flashcard", "anki", "bac ",
        "courses", "parcours", "tutorialengine",
    ),
    "cowork-lead": (
        "aurora-connect", "auroraextensionbridge", "coworkplanner",
        "coworkconnectors", "coworkexecutor", "coworksafety",
        "safety_limits", "approveexternalpath",
    ),
    "voice-lead": (
        "voxtral", "kokoro", "rhubarb", "lipsync", "lip sync",
        "formant", "voicelive", "voicecopilot", "vad ",
    ),
    "cyber-lead": (
        "ctflab", "cryptolab", "forensicslab", "hashlab", "networklab",
        "passwordlab", "steganographylab", "threatintel", "websec",
        "_safety.py",
    ),
    "simulator-lead": (
        "physicsengine", "fluidsolver", "particlesystem", "phenomena",
        "chemistryreactions", "sceneio", "scenestore",
    ),
    "tunnel-validator": (
        "tunnel", "trycloudflare", "/api/health", "update-aurora.bat",
    ),
}


def detect_leads(prompt: str) -> list[str]:
    if not prompt:
        return []
    lower = prompt.lower()
    hits: list[str] = []
    for lead, keywords in LEAD_KEYWORDS.items():
        for kw in keywords:
            # Word-boundary check for short/generic-looking keywords.
            if " " in kw or "-" in kw or "/" in kw or "." in kw or "_" in kw:
                if kw in lower:
                    hits.append(lead)
                    break
            else:
                if re.search(rf"\b{re.escape(kw)}\b", lower):
                    hits.append(lead)
                    break
    return hits


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    prompt = (payload.get("prompt") or payload.get("user_prompt") or "").strip()
    if not prompt:
        return 0

    leads = detect_leads(prompt)
    if not leads:
        return 0

    if len(leads) == 1:
        hint = f"[Aurora hint] This prompt looks like work for {leads[0]}."
    else:
        hint = (
            f"[Aurora hint] This prompt touches multiple modules — likely leads: "
            f"{', '.join(leads)}. Consider dispatching aurora-orchestrator."
        )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": hint,
        }
    }
    sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
