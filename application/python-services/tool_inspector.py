#!/usr/bin/env python3
"""
tool_inspector.py — Introspection dynamique et découverte de documentation pour les outils.

Permet à l'agent d'inspecter un paquet Python ou un binaire système, d'extraire sa
documentation d'utilisation, ses fonctions exportées et de diagnostiquer les erreurs.
"""

import argparse
import importlib
import inspect
import json
import os
import subprocess
import sys
from typing import Any, Dict, List


def inspect_python_package(package_name: str, pkg_dir: str = "") -> Dict[str, Any]:
    if pkg_dir and os.path.isdir(pkg_dir):
        if pkg_dir not in sys.path:
            sys.path.insert(0, pkg_dir)

    try:
        module = importlib.import_module(package_name)
        doc = inspect.getdoc(module) or ""
        
        exported_symbols = []
        for name, obj in inspect.getmembers(module):
            if name.startswith("_"):
                continue
            try:
                obj_doc = inspect.getdoc(obj) or ""
                summary = obj_doc.split("\n")[0] if obj_doc else ""
                is_callable = callable(obj)
                exported_symbols.append({
                    "name": name,
                    "type": type(obj).__name__,
                    "is_callable": is_callable,
                    "summary": summary[:160]
                })
            except Exception:
                continue

        return {
            "ok": True,
            "name": package_name,
            "doc": doc[:2000],
            "exported_count": len(exported_symbols),
            "symbols": exported_symbols[:40],
        }
    except Exception as e:
        return {
            "ok": False,
            "name": package_name,
            "error": str(e),
            "doc": "",
            "exported_count": 0,
            "symbols": []
        }


def inspect_system_command(command_name: str) -> Dict[str, Any]:
    try:
        which_proc = subprocess.run(
            ["which", command_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        if which_proc.returncode != 0:
            return {
                "ok": False,
                "command": command_name,
                "found": False,
                "error": f"Commande '{command_name}' introuvable sur le système.",
                "help_text": ""
            }

        binary_path = which_proc.stdout.strip()
        help_text = ""
        for flag in ["--help", "-h", "help"]:
            try:
                proc = subprocess.run(
                    [command_name, flag],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                output = proc.stdout if proc.stdout else proc.stderr
                if output and len(output.strip()) > 30:
                    help_text = output.strip()
                    break
            except Exception:
                continue

        return {
            "ok": True,
            "command": command_name,
            "found": True,
            "path": binary_path,
            "help_text": help_text[:3000]
        }
    except Exception as e:
        return {
            "ok": False,
            "command": command_name,
            "found": False,
            "error": str(e),
            "help_text": ""
        }


def main():
    parser = argparse.ArgumentParser(description="Inspection dynamique de modules et commandes.")
    parser.add_argument("--python-pkg", type=str, default=None, help="Nom du module Python à inspecter")
    parser.add_argument("--pkg-dir", type=str, default="", help="Dossier contenant le module")
    parser.add_argument("--sys-cmd", type=str, default=None, help="Nom de la commande système à inspecter")
    args = parser.parse_args()

    if args.python_pkg:
        res = inspect_python_package(args.python_pkg, args.pkg_dir)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.sys_cmd:
        res = inspect_system_command(args.sys_cmd)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"ok": False, "error": "Aucune cible spécifiée"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
