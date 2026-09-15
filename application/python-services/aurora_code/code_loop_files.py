"""Parsing et contrôles de fichiers pour la boucle autonome Code."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

# Add python-services directory to path to import aurora_output_paths
SERVICES_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICES_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICES_ROOT))

try:
    from aurora_output_paths import get_code_project_dir, get_output_root
except ImportError:
    def get_code_project_dir(name: str) -> Path:
        p = Path(__file__).resolve().parents[2] / "output" / "code" / name
        p.mkdir(parents=True, exist_ok=True)
        return p
_FILE_TAG = re.compile(r'<FILE\s+path="([^"]+)"\s*>(.*?)</FILE>', re.DOTALL)


def _guess_filename(lang: str, body: str, idx: int) -> str:
    content = body.strip()
    lower_head = content[:300].lower()
    if lang == "json" or content.startswith("{"):
        if '"name"' in lower_head and '"scripts"' in lower_head and '"dependencies"' in lower_head:
            return "package.json"
        if '"compileroptions"' in lower_head.replace(" ", ""):
            return "tsconfig.json" if "tsconfig.node" not in lower_head else "tsconfig.node.json"
        return f"file_{idx}.json"
    if lang == "tsx" or "react" in lower_head and ("export default" in content or "function" in content):
        return "src/main.tsx" if "ReactDOM" in content or "createRoot" in content else "src/App.tsx"
    if lang == "ts":
        return f"src/file_{idx}.ts"
    if lang in ("js", "javascript", "mjs"):
        if "require('express')" in content or 'require("express")' in content or "import express" in content:
            return "server.js" if "app.listen" in content else "index.js"
        return f"file_{idx}.js"
    if lang == "html" or "<!doctype html" in lower_head or "<html" in lower_head:
        return "index.html"
    if lang == "css" or "{" in content and ":" in content and ";" in content and "function" not in content[:200]:
        return "style.css" if idx == 0 else "src/index.css"
    if lang in ("py", "python"):
        return "main.py" if "if __name__" in content or "argparse" in content else f"file_{idx}.py"
    if lang in ("bash", "sh"):
        return "run.sh"
    if lang in ("md", "markdown") or content.lstrip().startswith("#"):
        return "README.md"
    return f"file_{idx}.{lang or 'txt'}"


def extract_files(text: str) -> list[tuple[str, str]]:
    files = [
        (match.group(1).strip().strip("/"), match.group(2).strip("\n"))
        for match in _FILE_TAG.finditer(text)
        if match.group(1).strip().strip("/")
    ]
    if files:
        return files

    labeled = re.compile(
        r"```(\w+)?\s*(?:title=|filename=|file=|path=)\"?([^\"\n]+\.[a-z]+)\"?\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    files = [(match.group(2).strip().strip("/"), match.group(3)) for match in labeled.finditer(text)]
    if files:
        return files

    bare = re.compile(r"```([A-Za-z0-9_+-]*)\s*\n(.*?)```", re.DOTALL)
    used: set[str] = set()
    for idx, match in enumerate(bare.finditer(text)):
        language, body = (match.group(1) or "").lower(), match.group(2)
        if len(body.strip()) < 4:
            continue
        path = _guess_filename(language, body, idx)
        if path in used:
            stem, _, extension = path.rpartition(".")
            path = f"{stem}_{idx}.{extension}" if stem else f"{path}_{idx}"
        used.add(path)
        files.append((path, body))
    return files


def write_project(files: list[tuple[str, str]], project_dir: Path) -> int:
    project_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for relative_path, content in files:
        safe_path = Path(relative_path).as_posix().replace("..", "_").lstrip("/")
        if not safe_path:
            continue
        output = project_dir / safe_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        written += 1
    return written


def syntax_check_files(project_dir: Path, files: list[tuple[str, str]]) -> dict:
    flags: list[str] = []
    for relative_path, _ in files:
        path = project_dir / relative_path
        if not path.exists():
            continue
        extension = path.suffix.lower()
        try:
            text = path.read_text(encoding="utf-8")
            if extension == ".html":
                if "<html" not in text.lower():
                    flags.append(f"{relative_path}: no <html> tag")
                if text.count("<") < 5:
                    flags.append(f"{relative_path}: too few tags")
            elif extension == ".css" and text.count("{") != text.count("}"):
                flags.append(f"{relative_path}: brace mismatch {text.count('{')}/{text.count('}')}")
            elif extension in (".js", ".mjs", ".ts", ".tsx") and text.count("{") != text.count("}"):
                flags.append(f"{relative_path}: brace mismatch")
            elif extension == ".py":
                try:
                    compile(text, str(path), "exec")
                except SyntaxError as error:
                    flags.append(f"{relative_path}: py syntax line {error.lineno}: {error.msg}")
        except OSError:
            continue
    return {"flags": flags, "passed": not flags}


def slugify(text: str, maxlen: int = 48) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:maxlen] or "scene"


def make_pack_dir(prompt: str, name: str | None) -> Path:
    proj_name = name or slugify(prompt)
    target = get_code_project_dir(proj_name)
    target.mkdir(parents=True, exist_ok=True)
    return target
