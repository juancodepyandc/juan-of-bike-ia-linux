"""forge_write_rig — write a rig JSON string to a workspace-relative path.

Used by the Character Forge orchestrator to persist the rig.json that
forge_layers.py then consumes. Kept as a tiny dedicated script so the
write happens under the bridge's filesystem permissions.
"""
import argparse
import json
import os
import sys
from pathlib import Path

WORKSPACE = str(Path(__file__).resolve().parent.parent)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Workspace-relative path to write (e.g. public/avatars/xxx_rig.json)")
    ap.add_argument("--rig", required=True, help="Rig JSON as a string (one line)")
    args = ap.parse_args()

    out_path = os.path.abspath(os.path.join(WORKSPACE, args.out))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        parsed = json.loads(args.rig)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"bad JSON: {e}"}))
        return 2
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    print(json.dumps({"ok": True, "path": out_path}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
