from __future__ import annotations
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from .config import LABELS, STATE, TEXT_MODULES, defaults, read_config, validate
from .storage import atomic_json, read_json, submit_decision


def doctor(module=None):
    os.environ["HF_HUB_OFFLINE"] = "1"
    import torch
    from .backends import resolve_paths
    from .sandbox import Sandbox
    checks = {"python": sys.executable, "torch": torch.__version__,
              "cuda_available": torch.cuda.is_available(), "modules": {}}
    if torch.cuda.is_available():
        checks["gpu"] = torch.cuda.get_device_name(0)
        checks["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 2 ** 30, 2)
    requirements = {"3d": ["nvdiffrast", "cumesh", "flex_gemm", "trimesh"],
                    "code": ["transformers", "bitsandbytes"],
                    "image": ["diffusers", "transformers"],
                    "audio": ["kokoro", "faster_whisper", "soundfile"],
                    "video": ["gguf", "safetensors", "PIL", "cv2"],
                    "animation": ["torchdiffeq", "transformers", "bitsandbytes"]}
    requirements.update({key: ["transformers", "bitsandbytes"] for key in TEXT_MODULES})
    for key in ([module] if module else LABELS):
        c, errors = defaults(key), []
        try:
            paths = resolve_paths(c)
        except RuntimeError as e:
            paths = {}
            errors.append(str(e))
        for dependency in requirements[key]:
            if not importlib.util.find_spec(dependency):
                errors.append("Dépendance absente : " + dependency)
        if key in TEXT_MODULES - {"conversation", "learning"}:
            try:
                Sandbox(c["python_image"]).check()
            except RuntimeError as e:
                errors.append(str(e))
        checks["modules"][key] = {"preflight_ok": not errors and checks["cuda_available"],
            "model": c["models"][key], "paths": paths, "errors": errors,
            "note": "La pré-vérification ne remplace pas un essai réel d'inférence."}
    atomic_json(STATE / "doctor.json", checks)
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(v["preflight_ok"] for v in checks["modules"].values()) else 1


def main(argv=None):
    p = argparse.ArgumentParser(description="Aurora : cycles locaux et comparaison")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("doctor")
    d.add_argument("--module", choices=LABELS)
    init = sub.add_parser("init")
    init.add_argument("--module", choices=LABELS, default="3d")
    init.add_argument("--output", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config")
    run.add_argument("--module", choices=LABELS)
    run.add_argument("--resume", help="Identifiant du cycle dont les préférences mesurées doivent être réutilisées")
    run.add_argument("--auto", action="store_true")
    run.add_argument("--cycles", type=int)
    decision = sub.add_parser("decide")
    decision.add_argument("run_id")
    decision.add_argument("decision", choices=["ACCEPT", "REJECT"])
    sub.add_parser("stop")
    sub.add_parser("status")
    sub.add_parser("models")
    select = sub.add_parser('select')
    select.add_argument('module', choices=LABELS)
    select.add_argument('version', choices=['base','validated'])
    chat = sub.add_parser("chat")
    chat.add_argument("model")
    chat.add_argument("prompt")
    args = p.parse_args(argv)
    try:
        if args.command == 'select':
            from .versions import select
            print(json.dumps(select(args.module,args.version),ensure_ascii=False,indent=2))
            return 0
        if args.command == "models":
            from .runtime import catalog
            print(json.dumps(catalog(include_base=True),ensure_ascii=False,indent=2))
            return 0
        if args.command == "chat":
            import urllib.request
            request=urllib.request.Request("http://127.0.0.1:11435/api/chat",data=json.dumps({"model":args.model,"messages":[{"role":"user","content":args.prompt}],"stream":False}).encode(),headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(request,timeout=600) as response:
                answer=json.load(response)
            print(answer["message"]["content"])
            return 0
        if args.command == "doctor":
            return doctor(args.module)
        if args.command == "init":
            path = Path(args.output)
            if path.exists():
                raise ValueError("Le profil existe déjà")
            atomic_json(path, defaults(args.module))
            print(path.resolve())
            return 0
        if args.command == "status":
            from .control import snapshot
            print(json.dumps({'controller':snapshot(),'cycle':read_json(STATE / "status.json", {})}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "decide":
            submit_decision(STATE, args.run_id, args.decision)
            return 0
        if args.command == "stop":
            from .control import snapshot, request
            if snapshot().get('active'):
                print(json.dumps(request('stop'),ensure_ascii=False,indent=2))
                return 0
            status = read_json(STATE / "status.json", {})
            if status.get("phase") not in {None, "accepted", "rejected", "cancelled", "error"}:
                (STATE / "runs" / status["run_id"] / "stop_signal.txt").write_text("STOP")
            return 0
        c = read_config(args.config, args.module)
        if args.resume:
            c["resume_run"] = args.resume
        if args.auto:
            c.update(mode="auto", eval_tasks=max(c["eval_tasks"], c["auto_min_tasks"]))
        if args.cycles:
            c["cycles"] = args.cycles
        from .runner import run_cycles
        return run_cycles(validate(c))
    except (ValueError, RuntimeError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
