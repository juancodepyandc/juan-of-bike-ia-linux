"""Agentic planner-executor used by the bridge Code NDJSON route."""

from __future__ import annotations

import ast
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable


SCHEMA = "aurora.code.stream/1"
PLAN_SCHEMA = "aurora.code.architecture-plan.v1"
APPLICATION_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = APPLICATION_ROOT / "output" / "code-bridge"
MAX_FILES = 120


class EventEmitter:
    def __init__(self, run_id: int, sink: Callable[[dict[str, Any]], None]) -> None:
        self.run_id = run_id
        self.sequence = 0
        self.sink = sink

    def emit(self, kind: str, **payload: Any) -> None:
        self.sequence += 1
        self.sink({
            "schema": SCHEMA,
            "kind": kind,
            "runId": self.run_id,
            "sequence": self.sequence,
            "timestamp": int(time.time() * 1000),
            **payload,
        })


def _post_chat(
    ollama_url: str,
    model: str,
    messages: list[dict[str, str]],
    json_mode: bool = True,
    timeout: int = 900,
) -> str:
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.15, "num_ctx": 24576},
    }
    if json_mode:
        body["format"] = "json"
    request = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
    return str((payload.get("message") or {}).get("content") or payload.get("response") or "")


def _first_json_object(raw: str) -> dict[str, Any] | None:
    text = re.sub(r"<think>[\s\S]*?</think>", "", raw or "", flags=re.I).strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.I)
    candidates = [fenced.group(1), text] if fenced else [text]
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        for start, char in enumerate(candidate):
            if char != "{":
                continue
            depth = 0
            in_string = False
            escaped = False
            for index in range(start, len(candidate)):
                current = candidate[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif current == "\\":
                        escaped = True
                    elif current == '"':
                        in_string = False
                    continue
                if current == '"':
                    in_string = True
                elif current == "{":
                    depth += 1
                elif current == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            value = json.loads(candidate[start:index + 1])
                            if isinstance(value, dict):
                                return value
                        except json.JSONDecodeError:
                            break
    return None


def _safe_path(value: Any) -> str | None:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    parts = path.split("/")
    if not path or len(path) > 240 or path.startswith("/"):
        return None
    if re.match(r"^[A-Za-z]:", path) or any(part in ("", ".", "..") for part in parts):
        return None
    return path


def normalize_plan(candidate: Any) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(candidate, dict):
        return None, ["plan_not_object"]
    if candidate.get("schemaVersion") != PLAN_SCHEMA:
        errors.append("schemaVersion_invalid")
    summary = str(candidate.get("summary") or "").strip()
    if len(summary) < 20:
        errors.append("summary_too_short")
    raw_files = candidate.get("files")
    if not isinstance(raw_files, list) or len(raw_files) < 2:
        errors.append("files_missing")
        raw_files = []
    if len(raw_files) > MAX_FILES:
        errors.append("files_limit_exceeded")

    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_file in raw_files[:MAX_FILES]:
        if not isinstance(raw_file, dict):
            errors.append("file_not_object")
            continue
        path = _safe_path(raw_file.get("path"))
        if not path or path.lower() in seen:
            errors.append("file_path_invalid_or_duplicate")
            continue
        seen.add(path.lower())
        files.append({
            "path": path,
            "role": str(raw_file.get("role") or "source")[:120],
            "language": str(raw_file.get("language") or "text")[:40],
            "required": raw_file.get("required") is not False,
            "imports": [str(item)[:160] for item in raw_file.get("imports", []) if isinstance(item, str)][:20],
            "notes": [str(item)[:240] for item in raw_file.get("notes", []) if isinstance(item, str)][:20],
        })
    if len(files) < 2:
        errors.append("usable_files_below_minimum")
    if errors:
        return None, sorted(set(errors))

    order = [_safe_path(item) for item in candidate.get("generationOrder", [])]
    order = [item for item in order if item and item.lower() in seen]
    by_path = {item["path"].lower(): item for item in files}
    ordered = [by_path[path.lower()] for path in order]
    ordered.extend(item for item in files if item not in ordered)
    return {**candidate, "summary": summary, "files": ordered}, []


def _planning_messages(prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Tu es l architecte du Module Code AuroraIA. Retourne uniquement un JSON valide. "
                "Le plan est un contrat dur pour un executor fichier par fichier."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Demande:\n{prompt}\n\nSchema requis:\n"
                "{\"schemaVersion\":\"aurora.code.architecture-plan.v1\","
                "\"projectType\":\"type\",\"summary\":\"description detaillee\","
                "\"stack\":{\"runtime\":\"\",\"packageManager\":\"\",\"languages\":[],"
                "\"frameworks\":[],\"dependencies\":[],\"scripts\":[]},"
                "\"files\":[{\"path\":\"...\",\"role\":\"...\",\"language\":\"...\","
                "\"required\":true,\"imports\":[],\"exports\":[],\"notes\":[]}],"
                "\"dataFlow\":[\"...\"],\"execution\":{\"install\":[],\"dev\":[],"
                "\"build\":[],\"test\":[],\"preview\":\"\"},\"generationOrder\":[],"
                "\"validation\":[\"...\",\"...\"],\"risks\":[{\"risk\":\"...\","
                "\"mitigation\":\"...\"}],\"design\":{\"palette\":[],\"typography\":[],"
                "\"ux\":[],\"responsive\":[]}}\n"
                "Liste tous les fichiers necessaires, au moins deux, sans chemin absolu ni '..'."
            ),
        },
    ]


def build_plan(prompt: str, model: str, chat: Callable[..., str]) -> dict[str, Any]:
    failures: list[str] = []
    valid: list[dict[str, Any]] = []
    for candidate_index in range(2):
        messages = _planning_messages(prompt)
        if candidate_index:
            messages[-1]["content"] += "\nProduis une variante plus robuste que la premiere."
        raw = chat(model, messages, True, 900)
        plan, errors = normalize_plan(_first_json_object(raw))
        if plan:
            valid.append(plan)
        else:
            failures.extend(errors)
    if not valid:
        raise ValueError(f"architecture_plan_invalid:{','.join(sorted(set(failures))) or 'empty'}")
    return max(valid, key=lambda plan: len(plan["files"]))


def _language(path: str, declared: str) -> str:
    if declared and declared != "text":
        return declared
    return {
        ".js": "javascript", ".jsx": "jsx", ".ts": "typescript", ".tsx": "tsx",
        ".py": "python", ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
    }.get(Path(path).suffix.lower(), Path(path).suffix.lstrip(".") or "text")


def _file_messages(prompt: str, plan: dict[str, Any], target: dict[str, Any], context: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Tu es l executor WS3 du Module Code AuroraIA. Tu traites un seul fichier. "
                "Retourne uniquement {\"kind\":\"write_file\",\"path\":\"...\","
                "\"language\":\"...\",\"content\":\"fichier complet\"}. Aucun markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Demande globale:\n{prompt}\n\nResume plan:\n{plan['summary']}\n\n"
                f"Fichier cible:\n{json.dumps(target, ensure_ascii=False)}\n\n"
                f"Contexte des fichiers deja ecrits:\n{context or 'aucun'}\n\n"
                "Ecris exactement le fichier cible, complet, runnable et coherent avec ses imports."
            ),
        },
    ]


def _generate_file(
    prompt: str,
    plan: dict[str, Any],
    target: dict[str, Any],
    files: dict[str, str],
    model: str,
    chat: Callable[..., str],
    correction: str = "",
) -> str:
    context_items = list(files.items())[-5:]
    context = "\n\n".join(f"--- {path} ---\n{content[:4000]}" for path, content in context_items)
    messages = _file_messages(prompt, plan, target, context[:14000])
    if correction:
        messages[-1]["content"] += f"\n\nCorrection obligatoire:\n{correction}"
    raw = chat(model, messages, True, 900)
    action = _first_json_object(raw)
    expected = target["path"]
    if not action or action.get("kind") != "write_file" or _safe_path(action.get("path")) != expected:
        raise ValueError(f"action_protocol_invalid:{expected}")
    content = action.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"empty_required_file:{expected}")
    return content


def _balanced(text: str) -> bool:
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    quote = ""
    escaped = False
    for char in text:
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in ("'", '"', "`"):
            quote = char
        elif char in pairs:
            stack.append(pairs[char])
        elif char in pairs.values() and (not stack or stack.pop() != char):
            return False
    return not stack and not quote


def validate_files(files: dict[str, str], required_paths: list[str]) -> list[str]:
    failures = [f"missing:{path}" for path in required_paths if not files.get(path, "").strip()]
    for path, content in files.items():
        suffix = Path(path).suffix.lower()
        try:
            if suffix == ".py":
                ast.parse(content, filename=path)
            elif suffix == ".json":
                json.loads(content)
            elif suffix in (".js", ".jsx", ".ts", ".tsx", ".css") and not _balanced(content):
                failures.append(f"delimiters:{path}")
            elif suffix in (".html", ".htm") and "<html" not in content.lower():
                failures.append(f"html_root:{path}")
        except (SyntaxError, json.JSONDecodeError) as error:
            failures.append(f"syntax:{path}:{error}")
    return failures


def run_agentic_stream(
    payload: dict[str, Any],
    sink: Callable[[dict[str, Any]], None],
    chat_client: Callable[..., str] | None = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> bool:
    prompt = str(payload.get("prompt") or "").strip()
    model = str(payload.get("model") or "qwen3-coder:30b").strip()
    run_id = int(payload.get("runId") or time.time() * 1000)
    emitter = EventEmitter(run_id, sink)
    if not prompt:
        emitter.emit("error", message="prompt requis", recoverable=False)
        return False
    chat = chat_client or (lambda selected, messages, json_mode, timeout: _post_chat(
        str(payload.get("ollamaUrl") or "http://127.0.0.1:11434"),
        selected, messages, json_mode, timeout,
    ))

    try:
        emitter.emit("phase", phase="planning", message="Plan JSON best-of-2 en cours.", progress=8)
        plan = build_plan(prompt, str(payload.get("planningModel") or model), chat)
        emitter.emit("phase", phase="generation", message=f"Executor WS3: {len(plan['files'])} fichier(s).", progress=30)
        files: dict[str, str] = {}
        run_dir = output_root / str(run_id)
        project_dir = run_dir / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "architecture-plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8",
        )

        for index, target in enumerate(plan["files"]):
            content = _generate_file(prompt, plan, target, files, model, chat)
            path = target["path"]
            files[path] = content
            destination = project_dir / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
            emitter.emit(
                "file.written", path=path, language=_language(path, target["language"]),
                bytes=len(content.encode("utf-8")), content=content,
            )
            progress = 30 + round(((index + 1) / len(plan["files"])) * 50)
            emitter.emit("phase", phase="generation", message=f"Fichier {index + 1}/{len(plan['files'])}: {path}", progress=progress)

        required = [item["path"] for item in plan["files"] if item["required"]]
        failures = validate_files(files, required)
        emitter.emit(
            "test.result", ok=not failures, score=100 if not failures else 0,
            summary="Validation structurelle verte." if not failures else "Validation structurelle echouee.",
            detectedLanguage="multi", stepsPassed=0 if failures else len(required),
            stepsTotal=len(required), failedLabels=failures[:12],
        )
        if failures:
            emitter.emit("error", message="; ".join(failures[:12]), recoverable=True)
            return False
        emitter.emit(
            "done", filesCount=len(files), finalScore=100, totalAttempts=1,
            notes=f"Planner-executor WS3 termine: {len(files)} fichiers, plan JSON valide, validation verte.",
        )
        return True
    except Exception as error:
        emitter.emit("error", message=str(error)[:2000], recoverable=True)
        return False


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as error:
        payload = {"prompt": "", "runId": int(time.time() * 1000)}
        payload["parseError"] = str(error)

    def print_event(event: dict[str, Any]) -> None:
        print(json.dumps(event, ensure_ascii=False), flush=True)

    return 0 if run_agentic_stream(payload, print_event) else 1


if __name__ == "__main__":
    raise SystemExit(main())
