"""Native JSONL browser driver: keep stdin open to preserve sessions across actions."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agi_core.browser_runtime import BrowserRuntime

def main():
    runtime = BrowserRuntime()
    try:
        for line in sys.stdin:
            try:
                payload = json.loads(line)
                if payload.get("action") in {"navigate", "extract_dom"} and not payload.get("session_id"):
                    payload["action"] = "open"
                result = runtime.call(payload)
            except (TypeError, ValueError, AttributeError) as exc:
                result = {"ok": False, "error": str(exc)}
            print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        runtime.close()

if __name__ == "__main__":
    main()
