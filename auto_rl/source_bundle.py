"""Reproducible Python source bundles for private, isolated native experiments."""
from __future__ import annotations

import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile


def collect_sources(root, modules):
    """Follow static in-repository imports; include no weights, environment or credentials."""
    root = Path(root).resolve()
    pending = list(modules)
    visited = set()
    sources = {}
    while pending:
        module = pending.pop()
        if not module or module in visited:
            continue
        visited.add(module)
        relative = Path(*module.split("."))
        path = root / relative.with_suffix(".py")
        is_package = False
        if not path.is_file():
            path = root / relative / "__init__.py"
            is_package = True
        if not path.is_file() or not path.resolve().is_relative_to(root):
            continue
        name = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        sources[name] = raw
        parts = module.split(".")
        for depth in range(1, len(parts)):
            pending.append(".".join(parts[:depth]))
        package = parts if is_package else parts[:-1]
        for node in ast.walk(ast.parse(raw, filename=name)):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = package[:len(package) - node.level + 1]
                    if node.module:
                        base += node.module.split(".")
                    imported = ".".join(base)
                else:
                    imported = node.module or ""
                pending.append(imported)
                pending.extend(f"{imported}.{alias.name}" for alias in node.names if alias.name != "*")
        if module.startswith(("tests_agi.", "tests_auto_rl.")):
            for fixture in path.parent.joinpath("fixtures").rglob("*.py"):
                if fixture.resolve().is_relative_to(root):
                    sources[fixture.relative_to(root).as_posix()] = fixture.read_bytes()
    return sources


def build_bundle(root, modules):
    sources = collect_sources(root, modules)
    if not sources:
        raise ValueError("No native sources found")
    manifest = {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(sources.items())}
    sources["source_manifest.json"] = json.dumps(manifest, sort_keys=True).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(sources.items()):
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100600 << 16
            archive.writestr(info, raw)
    return output.getvalue(), manifest


def extract_bundle(raw, destination, expected_sha256, max_bytes=100 * 1024 * 1024):
    """Validate all paths and hashes before writing; preserve any different existing file."""
    if len(raw) > max_bytes or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Source bundle hash or size mismatch")
    destination = Path(destination).resolve()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or sum(i.file_size for i in archive.infolist()) > max_bytes:
            raise ValueError("Invalid or oversized source bundle")
        manifest = json.loads(archive.read("source_manifest.json"))
        if not isinstance(manifest, dict) or set(names) != set(manifest) | {"source_manifest.json"}:
            raise ValueError("Source manifest does not match archive")
        pending = []
        for info in archive.infolist():
            relative = PurePosixPath(info.filename)
            if (str(relative) != info.filename or relative.is_absolute() or ".." in relative.parts or "\\" in info.filename
                    or stat.S_ISLNK(info.external_attr >> 16)
                    or (info.filename != "source_manifest.json" and relative.suffix != ".py")):
                raise ValueError("Unsafe source bundle member")
            target = destination.joinpath(*relative.parts)
            if not target.resolve().is_relative_to(destination):
                raise ValueError("Source bundle escapes destination")
            content = archive.read(info)
            if info.filename in manifest and hashlib.sha256(content).hexdigest() != manifest[info.filename]:
                raise ValueError("Source file hash mismatch")
            if target.exists() and target.read_bytes() != content:
                raise ValueError("Existing different source preserved")
            pending.append((target, content))
        for target, content in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                with target.open("xb") as stream:
                    stream.write(content)
    return destination
