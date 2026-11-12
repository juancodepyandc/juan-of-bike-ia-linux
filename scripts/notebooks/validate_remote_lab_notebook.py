"""Run the notebook's actual source bootstrap and native tests in a fresh process.

Uses the current Python environment, without dependency installation or cloud calls.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    notebook = args.notebook.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    code = '''import json, pathlib, sys
notebook = json.loads(pathlib.Path(sys.argv[1]).read_text())
bootstrap = [c for c in notebook["cells"] if "source-bootstrap" in c.get("metadata", {}).get("tags", [])]
assert len(bootstrap) == 1, "Exactly one source bootstrap is required"
namespace = {}
exec("".join(bootstrap[0]["source"]), namespace)
import auto_rl.remote_lab as lab
assert pathlib.Path(lab.__file__).resolve().is_relative_to(namespace["REPO"])
report = lab.validate_native(pathlib.Path(sys.argv[2]) / "validation")
print(json.dumps({k: v for k, v in report.items() if k != "test_sources"}, indent=2))
raise SystemExit(0 if report["passed"] else 1)
'''
    result = subprocess.run([sys.executable, "-c", code, str(notebook), str(output)], cwd=output, timeout=180)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
