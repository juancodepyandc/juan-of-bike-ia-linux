import argparse
import ast
import collections
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def tracked_files(root):
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True)
    return sorted(Path(os.fsdecode(p)) for p in result.stdout.split(b"\0") if p)


class PythonInventory(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.scope = []
        self.function_depth = 0
        self.units = []
        self.calls = []
        self.imports = []
        self.routes = []
        self.markers = []

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        public = self.function_depth == 0 and not any(part.startswith("_") for part in [*self.scope, node.name])
        self.units.append({"file": self.path, "name": ".".join([*self.scope, node.name]),
                           "line": node.lineno, "end": node.end_lineno, "public": public,
                           "language": "python", "review": "unreviewed"})
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr in {"route", "get", "post", "delete", "put", "patch"} and decorator.args:
                    if isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                        self.routes.append({"file": self.path, "line": node.lineno,
                                            "handler": node.name, "path": decorator.args[0].value,
                                            "decorators": [ast.unparse(d) for d in node.decorator_list]})
        self.scope.append(node.name)
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        if isinstance(node.func, (ast.Name, ast.Attribute)):
            self.calls.append({"file": self.path, "line": node.lineno,
                               "caller": ".".join(self.scope) or "<module>",
                               "callee": ast.unparse(node.func), "resolution": "syntactic"})
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({"file": self.path, "line": node.lineno,
                                 "module": alias.name, "alias": alias.asname})

    def visit_ImportFrom(self, node):
        self.imports.append({"file": self.path, "line": node.lineno,
                             "module": "." * node.level + (node.module or ""),
                             "names": [a.name for a in node.names]})

    def visit_Pass(self, node):
        self.markers.append({"file": self.path, "line": node.lineno, "kind": "pass"})

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            for kind, pattern in [("absolute_path", r"(?:/home/|/Users/|[A-Z]:\\)"),
                                  ("network_literal", r"https?://"),
                                  ("secret_candidate", r"(?:ghp_|github_pat_|sk-[A-Za-z0-9]{20}|AKIA[A-Z0-9]{16})")]:
                if re.search(pattern, node.value):
                    self.markers.append({"file": self.path, "line": node.lineno, "kind": kind})


def inspect_repo(root, label):
    records, units, calls, imports, routes, markers, failures = [], [], [], [], [], [], []
    digests = collections.defaultdict(list)
    for relative in tracked_files(root):
        path = root / relative
        ref = f"{label}/{relative.as_posix()}"
        if not path.is_file():
            failures.append({"file": ref, "error": "missing_or_nonregular"})
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        record = {"file": ref, "bytes": len(data), "sha256": digest, "suffix": path.suffix}
        records.append(record)
        digests[digest].append(ref)
        if path.suffix not in {".py", ".ts", ".tsx", ".js", ".mjs", ".jsx", ".rs", ".sh", ".ps1", ".bat"}:
            continue
        try:
            source = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            failures.append({"file": ref, "error": "non_utf8"})
            continue
        record["lines"] = len(source.splitlines())
        for number, line in enumerate(source.splitlines(), 1):
            if re.search(r"\b(TODO|FIXME|NotImplementedError|placeholder|stub)\b", line, re.I):
                markers.append({"file": ref, "line": number, "kind": "review_marker"})
        if path.suffix == ".py":
            try:
                tree = ast.parse(source, filename=ref)
            except SyntaxError as exc:
                failures.append({"file": ref, "line": exc.lineno, "error": exc.msg})
                continue
            visitor = PythonInventory(ref)
            visitor.visit(tree)
            units.extend(visitor.units)
            calls.extend(visitor.calls)
            imports.extend(visitor.imports)
            routes.extend(visitor.routes)
            markers.extend(visitor.markers)
    return {"files": records, "units": units, "calls": calls, "imports": imports,
            "routes": routes, "markers": markers, "parse_failures": failures,
            "duplicate_files": [paths for paths in digests.values() if len(paths) > 1]}


def physical_tree(root, output):
    counts = collections.Counter()
    with gzip.open(output, "wt", encoding="utf-8") as stream:
        for parent, directories, files in os.walk(root, followlinks=False):
            directories.sort()
            files.sort()
            for name in directories + files:
                path = Path(parent) / name
                relative = path.relative_to(root).as_posix()
                try:
                    info = path.lstat()
                    kind = "symlink" if path.is_symlink() else "directory" if name in directories else "file"
                    record = {"path": relative, "kind": kind, "bytes": info.st_size,
                              "mode": oct(info.st_mode & 0o777)}
                    counts[kind] += 1
                except OSError as exc:
                    record = {"path": relative, "error": type(exc).__name__}
                    counts["errors"] += 1
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return dict(counts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brain", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--remote", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--physical-tree", action="store_true")
    args = parser.parse_args()
    remote = args.remote or args.brain.parent / "aurora-remote-cli"
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {}
    for label, root in [("AuroraIA", args.brain), ("aurora-remote-cli", remote)]:
        inventory = inspect_repo(root, label)
        (args.output / f"{label}.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
        with (args.output / f"{label}-units.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["file", "name", "line", "end", "public", "language", "review"])
            writer.writeheader()
            writer.writerows(inventory["units"])
        summary[label] = {key: len(value) for key, value in inventory.items()}
        summary[label]["head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        summary[label]["source_lines"] = sum(row.get("lines", 0) for row in inventory["files"])
        if args.physical_tree:
            summary[label]["physical_tree"] = physical_tree(root, args.output / f"{label}-tree.jsonl.gz")
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
