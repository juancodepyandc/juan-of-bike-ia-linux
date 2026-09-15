"""Compatibility entry point for real local cycles."""
import sys
from auto_rl.cli import main

if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0].startswith("Module "):
        mapping = {"3d": "3d", "cyber": "code", "code": "code", "dessin": "image", "voice": "audio"}
        module = next((v for k, v in mapping.items() if k in args[0].lower()), None)
        if module is None:
            raise SystemExit("Ce module n'a pas de moteur de correction des poids configuré.")
        args = ["run", "--module", module]
    raise SystemExit(main(args or ["run"]))
