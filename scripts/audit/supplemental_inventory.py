"""Inventory ignored runtime code without importing nodes or executing labs."""

import argparse
import ast
import collections
import hashlib
import json
import os
from pathlib import Path


EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__"}


def inspect(root):
    records = []
    for parent, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(d for d in directories if d not in EXCLUDED)
        for name in sorted(files):
            path = Path(parent) / name
            if path.suffix != ".py" or path.is_symlink():
                continue
            record = {"file": str(path.relative_to(root))}
            try:
                data = path.read_bytes()
                tree = ast.parse(data, filename=record["file"])
                record.update(sha256=hashlib.sha256(data).hexdigest(), lines=len(data.splitlines()),
                              functions=sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                            for node in ast.walk(tree)))
            except (OSError, SyntaxError, ValueError) as exc:
                record["error"] = str(exc)
            records.append(record)
    return {"files": records, "python_files": len(records),
            "lines": sum(row.get("lines", 0) for row in records),
            "parse_failures": sum("error" in row for row in records)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    brain = Path(__file__).resolve().parents[2]
    remote = brain.parent / "aurora-remote-cli"
    result = {name: inspect(root) for name, root in {
        "comfyui": brain / "modele/comfyui",
        "lab_div_zero": remote / "lab_div_zero",
        "transfer_to_client": remote / "transfer_to_client",
    }.items()}
    counts = collections.Counter()
    for entry in result["comfyui"]["files"]:
        parts = Path(entry["file"]).parts
        if len(parts) > 2 and parts[0] == "custom_nodes":
            counts[parts[1]] += 1
    result["custom_node_packages"] = dict(sorted(counts.items()))
    # Keep user prompts and training content out of the report.
    failure_dir = brain / "Outputs/auto_rl/failure_memory"
    failures = {}
    for path in sorted(failure_dir.glob("*.json")):
        try:
            entries = json.loads(path.read_text())
            failures[path.name] = {"records": len(entries),
                                   "training_records": sum(e.get("task", {}).get("split") == "train"
                                                           for e in entries if isinstance(e, dict))}
        except (OSError, TypeError, ValueError) as exc:
            failures[path.name] = {"error": type(exc).__name__}
    result["failure_memory_counts"] = failures
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({name: {k: v for k, v in value.items() if k != "files"}
                      for name, value in result.items()}, indent=2))


if __name__ == "__main__":
    main()
