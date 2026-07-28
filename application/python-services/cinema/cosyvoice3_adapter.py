"""
Adaptateur AuroraIA pour Fun-CosyVoice3.

Ce fichier est volontairement execute par le Python d'un environnement isole
(`AURORA_COSYVOICE3_PYTHON`). Il n'installe rien et ne modifie jamais le venv
partage d'AuroraIA.

Variables d'environnement:
  AURORA_COSYVOICE3_REPO   clone local officiel QwenAudio/CosyVoice
  AURORA_COSYVOICE3_MODEL  dossier local Fun-CosyVoice3-0.5B-2512

Usage:
  python cosyvoice3_adapter.py --check
  python cosyvoice3_adapter.py --synthesize --text ... --reference ref.wav \
      --prompt-text "Transcription exacte de la reference" --output out.wav
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from pathlib import Path


MODEL_NAME = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"


def _configured_path(env_name: str) -> Path | None:
    configured = os.environ.get(env_name, "").strip()
    return Path(configured).expanduser() if configured else None


def _cold_storage_root() -> Path:
    return Path(os.environ.get("AURORA_COLD_STORAGE", "/mnt/aurora_models")).expanduser()


def _cold_storage_mounted(root: Path) -> bool:
    try:
        return root.is_dir() and os.path.ismount(str(root))
    except OSError:
        return False


def resolve_repo() -> Path:
    configured = _configured_path("AURORA_COSYVOICE3_REPO")
    if configured is not None:
        return configured
    internal = Path.home() / ".local/share/auroraia/engines/CosyVoice"
    cold_root = _cold_storage_root()
    candidates = [internal]
    if _cold_storage_mounted(cold_root):
        candidates.append(cold_root / "engines" / "CosyVoice")
    return next((path for path in candidates if (path / "cosyvoice").is_dir()), candidates[0])


def resolve_model() -> Path:
    configured = _configured_path("AURORA_COSYVOICE3_MODEL")
    if configured is not None:
        return configured
    internal = Path.home() / ".local/share/auroraia/models/Fun-CosyVoice3-0.5B-2512"
    cold_root = _cold_storage_root()
    candidates = [internal]
    if _cold_storage_mounted(cold_root):
        candidates.insert(0, cold_root / "models" / "Fun-CosyVoice3-0.5B-2512")
    markers = ("cosyvoice3.yaml", "config.json", "cosyvoice.yaml")
    return next(
        (path for path in candidates if path.is_dir() and any((path / marker).exists() for marker in markers)),
        candidates[0],
    )


def check_runtime(import_modules: bool = True) -> dict:
    repo = resolve_repo()
    model = resolve_model()
    result = {
        "ok": False,
        "engine": "cosyvoice3",
        "model": MODEL_NAME,
        "repo": str(repo),
        "model_path": str(model),
        "repo_ready": (repo / "cosyvoice").is_dir(),
        "model_ready": model.is_dir() and any(
            (model / marker).exists()
            for marker in ("cosyvoice3.yaml", "config.json", "cosyvoice.yaml")
        ),
        "python": sys.executable,
    }
    missing = []
    if not result["repo_ready"]:
        missing.append("repo")
    if not result["model_ready"]:
        missing.append("model")
    if import_modules and not missing:
        sys.path.insert(0, str(repo))
        matcha = repo / "third_party" / "Matcha-TTS"
        if matcha.is_dir():
            sys.path.insert(0, str(matcha))
        # v91 : appliquer le shim AVANT d'importer CosyVoice.
        # torchaudio >= 2.9 delegue la lecture audio a torchcodec, dont la
        # bibliotheque native refuse de se charger ici (aucune build ne matche
        # ffmpeg 6 + torch 2.11). cinema/_compat.py remplace torchaudio.load
        # par un loader soundfile : avec lui, CosyVoice s'importe et tourne.
        # Mesure : sans le shim -> ModuleNotFoundError torchcodec ; avec le
        # shim et torchcodec desinstalle -> import OK.
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import _compat  # noqa: F401
        except Exception:
            pass
        try:
            from cosyvoice.cli.cosyvoice import AutoModel  # noqa: F401
            from cosyvoice.flow.flow_matching import CausalConditionalCFM  # noqa: F401
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            # HyperPyYAML résout ces symboles seulement lors du vrai chargement.
            # Les importer sans instancier les poids rend --check prédictif tout
            # en gardant son coût mémoire faible.
            config_path = next(
                (
                    model / filename
                    for filename in ("cosyvoice3.yaml", "cosyvoice.yaml")
                    if (model / filename).is_file()
                ),
                None,
            )
            if config_path is not None:
                config_text = config_path.read_text(encoding="utf-8")
                symbols = re.findall(
                    r"!(?:name|new|apply):([A-Za-z0-9_.]+)",
                    config_text,
                )
                for symbol in symbols:
                    module_name, _, _attribute = symbol.rpartition(".")
                    if module_name:
                        importlib.import_module(module_name)
        except Exception as exc:
            missing.append("python_dependencies")
            result["dependency_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    result["missing"] = missing
    result["ok"] = not missing
    return result


def _transcribe_reference(reference: str, language: str) -> tuple[str, str | None]:
    """Optional convenience only; never invent a prompt transcript.

    CosyVoice zero-shot fidelity depends on the exact reference transcript.
    If faster-whisper is present in the isolated environment, use it.
    Otherwise return an actionable error and let AuroraIA choose a fallback.
    """
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return "", (
            "transcription_reference_absente: fournir --prompt-text ou installer "
            "faster-whisper dans le venv CosyVoice3 isole"
        )

    model_name = os.environ.get("AURORA_WHISPER_MODEL", "large-v3").strip() or "large-v3"
    device = os.environ.get("AURORA_WHISPER_DEVICE", "cuda").strip() or "cuda"
    compute_type = os.environ.get("AURORA_WHISPER_COMPUTE_TYPE", "float16").strip() or "float16"
    try:
        whisper = WhisperModel(model_name, device=device, compute_type=compute_type)
        segments, _ = whisper.transcribe(
            reference,
            language=(language[:2] if language and language != "auto" else None),
            beam_size=5,
            vad_filter=True,
        )
        transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        if not transcript:
            return "", "transcription_reference_vide"
        return transcript, None
    except Exception as exc:
        return "", f"transcription_reference_echouee: {type(exc).__name__}: {str(exc)[:240]}"


def synthesize(
    text: str,
    reference: str,
    output: str,
    prompt_text: str = "",
    language: str = "fr",
    instruction: str = "",
) -> dict:
    status = check_runtime(import_modules=True)
    if not status["ok"]:
        return {**status, "error": "cosyvoice3_runtime_incomplet"}

    reference_path = Path(reference)
    if not reference_path.is_file():
        return {"ok": False, "engine": "cosyvoice3", "error": f"reference_absente: {reference}"}
    if not text.strip():
        return {"ok": False, "engine": "cosyvoice3", "error": "texte_vide"}

    resolved_prompt = prompt_text.strip()
    transcript_source = "provided"
    if not resolved_prompt:
        resolved_prompt, transcript_error = _transcribe_reference(str(reference_path), language)
        transcript_source = "faster-whisper"
        if transcript_error:
            return {
                "ok": False,
                "engine": "cosyvoice3",
                "error": transcript_error,
                "requires_prompt_text": True,
            }

    repo = Path(status["repo"])
    sys.path.insert(0, str(repo))
    matcha = repo / "third_party" / "Matcha-TTS"
    if matcha.is_dir():
        sys.path.insert(0, str(matcha))

    try:
        import torch
        import torchaudio
        from cosyvoice.cli.cosyvoice import AutoModel

        model = AutoModel(
            model_dir=status["model_path"],
            load_trt=False,
            load_vllm=False,
            fp16=True,
        )
        assistant_prefix = "You are a helpful assistant."
        if instruction.strip():
            assistant_prefix = f"{assistant_prefix} {instruction.strip()}"
        prompt = f"{assistant_prefix}<|endofprompt|>{resolved_prompt}"
        chunks = []
        for item in model.inference_zero_shot(
            text.strip(),
            prompt,
            str(reference_path),
            stream=False,
        ):
            speech = item.get("tts_speech") if isinstance(item, dict) else None
            if speech is not None and speech.numel() > 0:
                chunks.append(speech.detach().cpu())
        if not chunks:
            return {"ok": False, "engine": "cosyvoice3", "error": "aucun_audio_genere"}
        waveform = torch.cat(chunks, dim=-1)
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        torchaudio.save(str(output_path), waveform, int(model.sample_rate))
        duration = float(waveform.shape[-1]) / float(model.sample_rate)
        return {
            "ok": True,
            "wav": str(output_path),
            "duration_s": duration,
            "engine": "cosyvoice3",
            "model": MODEL_NAME,
            "prompt_transcript_source": transcript_source,
            "sample_rate": int(model.sample_rate),
        }
    except Exception as exc:
        return {
            "ok": False,
            "engine": "cosyvoice3",
            "model": MODEL_NAME,
            "error": f"{type(exc).__name__}: {str(exc)[:400]}",
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--synthesize", action="store_true")
    parser.add_argument("--text", default="")
    parser.add_argument("--reference", default="")
    parser.add_argument("--prompt-text", default="")
    parser.add_argument("--lang", default="fr")
    parser.add_argument("--instruction", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    if args.check:
        result = check_runtime(import_modules=True)
    elif args.synthesize:
        if not args.output:
            result = {"ok": False, "engine": "cosyvoice3", "error": "--output requis"}
        else:
            result = synthesize(
                args.text,
                args.reference,
                args.output,
                prompt_text=args.prompt_text,
                language=args.lang,
                instruction=args.instruction,
            )
    else:
        parser.print_help()
        raise SystemExit(1)

    print(json.dumps(result, ensure_ascii=False), flush=True)
    raise SystemExit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
