"""Gestionnaire de compétences (skills) auto-installables et statut des agents pour le module Code.

Relie le magasin persistant `.aurora/skills/*.md` (utilisé par `agi_core/mission_agent.py`
et `agi_core/mission_tools.py`) au pipeline de génération de code de l'interface
et du tunnel. Permet au module Code :
1. De charger les compétences d'ingénierie installées (Assembleur x86_64/ARM64,
   Swift moderne, C/C++/Rust système, Python, Architecture Multi-Systèmes polyglotte,
   Résolution algorithmique complexe, Auto-organisation).
2. D'acquérir et d'installer de manière autonome de nouvelles compétences (`.aurora/skills/<id>.md`)
   lorsqu'un problème complexe, un langage spécialisé ou une architecture multi-système
   est détecté.
3. D'exposer l'état réel des agents officiels et sous-agents dynamiques ainsi que
   la disponibilité des chaînes de compilation locales (nasm/as/gcc, swift, cargo, go, python3, node).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import time
from typing import Any

from flask import Blueprint, jsonify, request


BUILTIN_CODE_SKILLS: list[dict[str, Any]] = [
    {
        "id": "asm-x86_64-arm64-abi",
        "title": "Assembleur x86_64 & ARM64 (NASM / GAS / ABI System V / FFI)",
        "category": "low-level",
        "languages": ["assembly", "asm", "nasm", "gas", "c"],
        "projectTypes": ["system_asm", "os_kernel", "system_c", "multi_system"],
        "triggers": ["assembleur", "assembly", "nasm", "gas", "x86_64", "arm64", "aarch64", "syscall", "registre", "simd", "avx", "bootloader", ".asm", ".s"],
        "source": "builtin",
        "summary": "Conventions d'appel System V AMD64 & ARM64, alignement de pile 16 octets, appels système Linux/macOS et interfaçage C/FFI.",
        "content": """# Skill: Assembleur x86_64 & ARM64 (NASM / GAS / ABI System V / FFI)

## Organisation et Architecture
- Séparer clairement les sections `.section .data` / `.section .rodata` / `.section .bss` / `.section .text` (ou `section .text` en NASM).
- Déclarer explicitement les symboles exportés avec `.global main` / `.globl _start` (GAS) ou `global main` / `global _start` (NASM).
- Pour un programme autonome lié avec `gcc -no-pie` ou un sous-module appelé depuis C/Rust/Python, privilégier l'ABI C standard (`main` ou fonctions exportées respectant System V AMD64 ABI) afin de garantir la portabilité et la vérification en sandbox.

## Convention d'appel System V AMD64 (Linux / macOS x86_64)
- Arguments entiers/pointeurs dans l'ordre : `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`.
- Valeur de retour : `rax` (et `rdx` pour 128 bits).
- Registres callee-saved (à préserver par `push`/`pop`) : `rbx`, `rbp`, `r12`, `r13`, `r14`, `r15`.
- Registres caller-saved (volatils) : `rax`, `rcx`, `rdx`, `rsi`, `rdi`, `r8`..`r11`.
- **Règle critique d'alignement** : `rsp` DOIT être aligné sur 16 octets (`rsp % 16 == 0`) juste AVANT toute instruction `call`. Après l'entrée dans une fonction (où `call` a poussé 8 octets d'adresse de retour), un `push rbp` réaligne `rsp` sur 16 octets.
- En fin de fichier GAS (`.s`), toujours inclure `.section .note.GNU-stack,"",@progbits` pour éviter l'avertissement de pile exécutable du linker.

## Appels Système Linux x86_64 (sans libc)
- Numéro de syscall dans `rax`, arguments dans `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9`, instruction `syscall`.
- `sys_write` : `rax = 1`, `rdi = 1` (stdout), `rsi = buffer`, `rdx = length`.
- `sys_exit` : `rax = 60`, `rdi = exit_code`.

## Compilation et Vérification
- Syntaxe GAS (`.s`) : `gcc -no-pie -O2 main.s -o app && ./app` (ou `as main.s -o main.o && ld main.o -o app` si `_start` pur).
- Syntaxe NASM (`.asm`) : `nasm -f elf64 main.asm -o main.o && gcc -no-pie main.o -o app && ./app`.
- Toujours inclure un test d'exécution vérifiant la sortie standard et un code de retour `0`.
""",
    },
    {
        "id": "swift-modern-systems",
        "title": "Swift 5.10/6 Système, Concurrence Structurée & SwiftPM",
        "category": "master-language",
        "languages": ["swift"],
        "projectTypes": ["cli_swift", "mobile_ios", "multi_system", "desktop_app"],
        "triggers": ["swift", "swiftui", "swiftpm", "package.swift", "actor", "sendable", "async/await", "ios", "macos"],
        "source": "builtin",
        "summary": "Architecture Swift Package Manager, typage fort par valeur, concurrence structurée (async/await, actors) et interopérabilité C/système.",
        "content": """# Skill: Swift 5.10/6 Système, Concurrence Structurée & SwiftPM

## Organisation de Projet Swift
- Pour un projet multi-fichiers ou exécutable structuré, fournir un `Package.swift` valide (`// swift-tools-version: 5.9` ou `5.10`) avec `executableTarget` sous `Sources/` et `testTarget` sous `Tests/`.
- Pour un outil système ou algorithmique rapide sans dépendances externes, structurer proprement `main.swift` (ou `Sources/main.swift`) de sorte qu'il compile aussi bien via `swift build` que via `swiftc`.

## Idiomes et Rigueur Swift
- Privilégier les types valeur (`struct`, `enum` à valeurs associées) et les protocoles (`protocol`) avec extensions génériques plutôt que des hiérarchies de classes profondes.
- Utiliser `guard let` / `if let` et un typage d'erreurs explicite (`enum DomainError: Error, CustomStringConvertible`) — bannir le force-unwrap `!` hors invariants prouvés.
- Pour la concurrence : utiliser `actor` pour isoler l'état mutable partagé, `TaskGroup` (`withThrowingTaskGroup`) pour le parallélisme borné, et respecter `Sendable`.
- Pour la compatibilité Linux + macOS : importer `Foundation` uniquement pour les API transversales ; pour les appels bas niveau POSIX (`errno`, sockets, fichiers), utiliser `#if canImport(Darwin) import Darwin #elseif canImport(Glibc) import Glibc #endif`.

## Vérification
- Exécuter une suite d'assertions déterministes au démarrage (mode `--self-test` ou `Tests/`) vérifiant les invariants métier avant de retourner le code de sortie `0`.
""",
    },
    {
        "id": "multi-system-polyglot-architecture",
        "title": "Architecture Multi-Systèmes Polyglotte & Contrats IPC / FFI",
        "category": "architecture",
        "languages": ["multi-system", "c", "cpp", "rust", "assembly", "swift", "python", "go", "typescript"],
        "projectTypes": ["multi_system", "distributed_system", "os_kernel", "compiler", "desktop_tauri"],
        "triggers": ["multi-système", "multi systeme", "multi-system", "polyglotte", "polyglot", "ffi", "ipc", "ctypes", "cffi", " Pont ", "bridge", "hybride", "orchestrateur", "microservice", "noyau et interface"],
        "source": "builtin",
        "summary": "Découpage topologique de systèmes hybrides (moteur bas niveau ASM/C/Rust + orchestrateur Python/Go/Swift + interface/API), contrats FFI/IPC et validation bout-en-bout.",
        "content": """# Skill: Architecture Multi-Systèmes Polyglotte & Contrats IPC / FFI

## Principes d'Ingénierie Multi-Systèmes
1. **Séparation stricte des responsabilités par couche** :
   - **Couche Noyau / Calcul Bas Niveau** (`core/`, `native/`, `asm/`, `rust-core/`) : Assembleur, C, C++ ou Rust pour le traitement critique (SIMD, mémoire, bas niveau, ABI C stable).
   - **Couche Pont / Protocole (FFI ou IPC)** (`bridge/`, `protocol/`, `include/`) : En-têtes C (`*.h`), ABI `extern "C"`, bibliothèque partagée (`.so`/`.dylib`) chargée via `ctypes`/`cffi`/Swift C-interop, ou protocole JSON-RPC / binaire encadré sur `stdin`/`stdout` ou socket local.
   - **Couche Orchestration / Haut Niveau** (`orchestrator/`, `api/`, `cli/`, `web/`) : Python, Swift, Go ou TypeScript gérant la logique applicative, l'orchestration des tâches, la télémétrie et l'interface.
2. **Ordre de construction topologique** :
   - Définir d'abord le contrat d'interface (schéma JSON, header `.h`, format binaire ou contrat CLI).
   - Implémenter et compiler le sous-système bas niveau avec un binaire ou point d'entrée auto-testable.
   - Implémenter l'orchestrateur haut niveau avec détection propre du binaire/lib natif et repli explicite documenté si un compilateur optionnel manque.
   - Fournir un script ou point d'entrée d'intégration (`verify_system.py`, `Makefile`, ou `run_all.sh`) qui compile et teste chaque sous-système puis vérifie le flux inter-systèmes de bout en bout.
3. **Zéro couplage implicite** :
   - Tous les chemins entre sous-systèmes doivent être résolus relativement à la racine du projet (`Path(__file__).resolve().parent`), jamais en supposant un répertoire courant fixe.
""",
    },
    {
        "id": "rust-c-cpp-systems",
        "title": "Ingénierie Système C / C++20 / Rust & Sûreté Mémoire",
        "category": "low-level",
        "languages": ["c", "cpp", "rust", "zig"],
        "projectTypes": ["system_c", "system_cpp", "system_rust", "cli_rust", "cli_cpp", "compiler", "os_kernel"],
        "triggers": ["rust", "cargo", "c++", "cpp", "cmake", "pointeur", "allocateur", "zero-copy", "raii", "concurrence", "thread", "mutex", "mmap"],
        "source": "builtin",
        "summary": "Gestion mémoire déterministe, zéro comportement indéfini (UB), ABI C propre, construction Cargo/CMake/GCC reproductible.",
        "content": """# Skill: Ingénierie Système C / C++20 / Rust & Sûreté Mémoire

## Règles C / C++20
- Compiler sans avertissement sous `-Wall -Wextra` (`-std=c11` ou `-std=c++20`).
- Vérifier systématiquement les retours d'allocation (`malloc`/`calloc`/`mmap`) et d'entrées-sorties.
- En C++, privilégier RAII (`std::unique_ptr`, `std::vector`, `std::span`, `std::optional`) et interdire les `new`/`delete` nus.
- Séparer les déclarations (`.h`/`.hpp` avec `#pragma once` ou include guards) des définitions (`.c`/`.cpp`), tout en s'assurant que chaque unité de traduction compile proprement.

## Règles Rust
- Structurer avec `Cargo.toml` valide (`edition = "2021"`), `src/lib.rs` + `src/main.rs` pour permettre à la fois l'exécution et les tests unitaires (`#[cfg(test)] mod tests`).
- Modéliser les invariants par le système de types (`Result<T, E>`, `Option<T>`, `enum` exhaustifs) sans `.unwrap()` sur les entrées externes.
- Si FFI est demandé : exposer `#[no_mangle] pub extern "C" fn ...` avec types `#[repr(C)]`.
""",
    },
    {
        "id": "python-clean-architecture",
        "title": "Python Modulaire, Typage Strict, Interfaçage Natif & Pytest",
        "category": "application",
        "languages": ["python"],
        "projectTypes": ["cli_python", "api_fastapi", "api_flask", "api_django", "data_python", "multi_system"],
        "triggers": ["python", "fastapi", "pytest", "asyncio", "ctypes", "numpy", "pandas", "pipeline", "orchestrateur"],
        "source": "builtin",
        "summary": "Architecture hexagonale/modulaire en Python, dataclasses immuables, typage complet, ctypes/subprocess et auto-validation pytest/unittest.",
        "content": """# Skill: Python Modulaire, Typage Strict, Interfaçage Natif & Pytest

## Organisation et Qualité
- Séparer le domaine pur (modèles `dataclass(frozen=True)`, algorithmes déterministes sans effets de bord) des adaptateurs E/S (CLI `argparse`, API HTTP, persistance SQLite/JSON, ponts natifs `ctypes`/`subprocess`).
- Annoter toutes les signatures publiques (`from __future__ import annotations`, types de retour explicites).
- Ne jamais capturer `Exception` silencieusement (`pass`) : journaliser et remonter des erreurs structurées contenant la cause et l'action corrective.
- Inclure systématiquement un fichier de test exécutable (`test_main.py` ou `tests/test_core.py`) compatible à la fois avec `pytest` et `python3 -m unittest` afin que la validation sandbox passe même dans un environnement minimal sans paquet tiers.
""",
    },
    {
        "id": "algorithmic-problem-solving",
        "title": "Résolution Algorithmique Complexe & Preuve par Invariants",
        "category": "algorithms",
        "languages": ["python", "rust", "cpp", "c", "swift", "go", "typescript", "assembly"],
        "projectTypes": ["compiler", "system_rust", "system_cpp", "system_c", "cli_python", "multi_system"],
        "triggers": ["algorithme", "algorithm", "graphe", "graph", "programmation dynamique", "optimisation", "arbre", "concurrence", "lock-free", "cryptographie", "solveur", "solver", "simulation", "complexité"],
        "source": "builtin",
        "summary": "Méthode formelle de décomposition par invariants, bornes de complexité O(T)/O(S), cas dégénérés et oracle d'auto-test.",
        "content": """# Skill: Résolution Algorithmique Complexe & Preuve par Invariants

## Méthodologie de Résolution
1. **Spécification des invariants** : Définir explicitement les préconditions, postconditions et l'invariant de boucle ou de structure de données avant d'écrire l'algorithme.
2. **Maîtrise de la complexité** :
   - Éviter toute récursion profonde non bornée susceptible de provoquer un dépassement de pile (`StackOverflow` / `RecursionError`) — convertir en parcours itératif avec pile explicite lorsque la profondeur peut dépasser 500.
   - Choisir les structures de données garantissant les bornes optimales (table de hachage, tas binaire / file de priorité, Union-Find avec compression de chemin, segment tree, ring buffer).
3. **Gestion exhaustive des cas limites** :
   - Entrées vides (`n = 0`), élément unique (`n = 1`), doublons, graphes déconnectés ou cycliques, dépassement d'entiers 64 bits.
4. **Auto-Vérification par Oracle** :
   - Intégrer un vérificateur de certificat (ex: vérifier qu'un chemin trouvé est valide et de coût minimal, qu'un tri est ordonné et conserve le multi-ensemble, qu'un AST évalué correspond à la valeur attendue).
""",
    },
    {
        "id": "compiler-vm-kernel-design",
        "title": "Compilateurs, Machines Virtuelles Bytecode & Noyaux Bas Niveau",
        "category": "low-level",
        "languages": ["rust", "c", "cpp", "assembly", "python", "swift", "go"],
        "projectTypes": ["compiler", "os_kernel", "system_asm", "system_c", "system_rust", "multi_system"],
        "triggers": ["compilateur", "compiler", "lexer", "parser", "ast", "bytecode", "machine virtuelle", "vm", "jit", "assembleur", "kernel", "noyau", "interpreteur"],
        "source": "builtin",
        "summary": "Pipeline complet Lexer -> Parser Pratt -> AST -> Vérificateur de types -> Bytecode/IR -> VM ou émission Assembleur avec tests de bout en bout.",
        "content": """# Skill: Compilateurs, Machines Virtuelles Bytecode & Noyaux Bas Niveau

## Architecture d'un Compilateur / VM
1. **Lexer (`lexer`)** : Tokenisation sans perte avec suivi précis `(line, column, span)` pour des diagnostics d'erreur lisibles.
2. **Parser (`parser`)** : Descente récursive + Pratt parsing pour les tables de précédence d'opérateurs ; construction d'un AST immuable et typé.
3. **Analyse sémantique / Résolution de portée (`sema` / `env`)** : Table des symboles lexicalement scopée, détection des variables non déclarées et des erreurs d'arité/type avant l'exécution.
4. **Backend (`bytecode` / `vm` / `codegen`)** :
   - Soit compilation vers un jeu d'instructions Bytecode exécuté par une machine virtuelle à pile/registres déterministe.
   - Soit génération d'assembleur x86_64/ARM64 ou C avec exécution vérifiée.
5. **Tests de conformité du langage** : Inclure une suite de programmes sources couvrant arithmétique, conditions, boucles, fonctions récursives, fermetures et erreurs de syntaxe/exécution.
""",
    },
    {
        "id": "self-organization-execution-protocol",
        "title": "Protocole d'Auto-Organisation Multi-Agents & Auto-Correction",
        "category": "meta-agent",
        "languages": ["all"],
        "projectTypes": [],
        "triggers": ["organisation", "architecture", "complexe", "complet", "multi", "agent", "système"],
        "source": "builtin",
        "summary": "Coordination entre Architecte Système, Ingénieurs Spécialisés (Bas Niveau / Applicatif) et Auditeur Sandbox pour livrer sans dette technique.",
        "content": """# Skill: Protocole d'Auto-Organisation Multi-Agents & Auto-Correction

## Règles d'Auto-Organisation du Module Code
1. **Décomposition par graphe de dépendances** :
   - Générer les fichiers de contrat, types partagés et manifestes (`Package.swift`, `Cargo.toml`, `CMakeLists.txt`, `Makefile`, `package.json`, headers `.h`) en premier.
   - Générer ensuite les moteurs bas niveau et modules métiers sans dépendances circulaires.
   - Générer enfin les points d'entrée, ponts d'intégration et suites de tests.
2. **Continuité inter-fichiers** :
   - Chaque symbole importé par un fichier `B` depuis un fichier `A` DOIT exister avec la signature exacte dans `A`.
   - Aucun fichier ne doit contenir de `TODO`, `FIXME`, `pass` vide ou implémentation tronquée.
3. **Boucle d'Auto-Correction Disciplinée** :
   - En cas d'échec de compilation ou de test dans le sandbox, identifier le fichier et la ligne exacts de la cause racine.
   - Corriger le contrat ou l'implémentation défectueuse sans jamais supprimer les tests ni dégrader les fonctionnalités demandées.
""",
    },
]


def _skills_dir(workspace: str) -> pathlib.Path:
    ws = pathlib.Path(workspace).resolve()
    repo_root = ws.parent if ws.name == "application" else ws
    d = repo_root / ".aurora" / "skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _agents_dir(workspace: str) -> pathlib.Path:
    ws = pathlib.Path(workspace).resolve()
    repo_root = ws.parent if ws.name == "application" else ws
    d = repo_root / ".aurora" / "agents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _registry_path(workspace: str) -> pathlib.Path:
    return _skills_dir(workspace) / "registry.json"


def _slugify_skill_id(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (raw or "").strip().lower()).strip("-")
    return slug[:64] or f"skill-{int(time.time())}"


def _load_registry(workspace: str) -> dict[str, dict[str, Any]]:
    reg_file = _registry_path(workspace)
    if reg_file.is_file():
        try:
            data = json.loads(reg_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_registry(workspace: str, registry: dict[str, dict[str, Any]]) -> None:
    reg_file = _registry_path(workspace)
    tmp = reg_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(reg_file)


def ensure_builtin_code_skills(workspace: str) -> list[dict[str, Any]]:
    """Garantit que les compétences maîtresses sont installées dans `.aurora/skills/`
    et synchronisées avec les éventuels fichiers `.md` créés par `agi_core`."""
    sdir = _skills_dir(workspace)
    registry = _load_registry(workspace)
    changed = False

    for builtin in BUILTIN_CODE_SKILLS:
        sid = builtin["id"]
        md_path = sdir / f"{sid}.md"
        if not md_path.is_file():
            md_path.write_text(builtin["content"].strip() + "\n", encoding="utf-8")
            changed = True
        if sid not in registry:
            registry[sid] = {
                "id": sid,
                "title": builtin["title"],
                "category": builtin["category"],
                "languages": builtin["languages"],
                "projectTypes": builtin["projectTypes"],
                "triggers": builtin["triggers"],
                "source": "builtin",
                "summary": builtin["summary"],
                "installedAt": int(time.time()),
                "usageCount": 0,
            }
            changed = True

    # Synchroniser aussi tout fichier `.aurora/skills/*.md` créé par `agi_core` (mission_tools.create_skill)
    for md_file in sorted(sdir.glob("*.md")):
        sid = md_file.stem
        if sid not in registry:
            try:
                raw_text = md_file.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            first_heading = next(
                (line.lstrip("# ").strip() for line in raw_text.splitlines() if line.strip().startswith("#")),
                sid.replace("-", " ").title(),
            )
            registry[sid] = {
                "id": sid,
                "title": first_heading[:120],
                "category": "self-installed",
                "languages": _infer_languages_from_text(raw_text),
                "projectTypes": [],
                "triggers": [w for w in re.split(r"[-_\s]+", sid.lower()) if len(w) >= 3],
                "source": "self_installed",
                "summary": _extract_summary(raw_text),
                "installedAt": int(md_file.stat().st_mtime),
                "usageCount": 1,
            }
            changed = True

    if changed:
        _save_registry(workspace, registry)

    skills_out: list[dict[str, Any]] = []
    for sid, meta in registry.items():
        md_path = sdir / f"{sid}.md"
        if not md_path.is_file():
            continue
        try:
            content = md_file_content(md_path)
        except OSError:
            continue
        skills_out.append({
            **meta,
            "id": sid,
            "content": content,
            "path": f".aurora/skills/{sid}.md",
        })

    skills_out.sort(key=lambda item: (0 if item.get("source") == "self_installed" else 1, item.get("id", "")))
    return skills_out


def md_file_content(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_summary(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        s = s.lstrip("-*0123456789. ").strip()
        if len(s) >= 20:
            return s[:200]
    return "Compétence spécialisée installée dans .aurora/skills."


def _infer_languages_from_text(text: str) -> list[str]:
    lower = text.lower()
    detected: list[str] = []
    mapping = {
        "assembly": ["assembleur", "assembly", "nasm", "x86_64", "arm64", "syscall"],
        "swift": ["swift", "swiftui", "package.swift", "swiftc"],
        "rust": ["rust", "cargo", "borrow", " crate "],
        "c": [" gcc ", "clang", "#include <stdio.h>", "stdlib.h"],
        "cpp": ["c++", "cmake", "std::", "iostream"],
        "python": ["python", "pytest", "asyncio", "dataclass"],
        "go": ["golang", "go.mod", "goroutine"],
        "typescript": ["typescript", "tsx", "react", "vite"],
        "zig": ["zig "],
        "kotlin": ["kotlin", "gradle"],
    }
    for lang, keywords in mapping.items():
        if any(k in lower for k in keywords):
            detected.append(lang)
    return detected or ["multi-system"]


def install_code_skill(
    workspace_or_payload: str | pathlib.Path | dict[str, Any] = ".",
    *,
    workspace: str | pathlib.Path | None = None,
    skill_id: str = "",
    title: str = "",
    content: str = "",
    rules: list[str] | None = None,
    category: str = "self-installed",
    languages: list[str] | None = None,
    project_types: list[str] | None = None,
    triggers: list[str] | None = None,
    source: str = "self_installed",
    summary: str | None = None,
) -> dict[str, Any]:
    """Installe ou met à jour une compétence sur disque dans `.aurora/skills/<id>.md`."""
    if isinstance(workspace_or_payload, dict):
        payload = workspace_or_payload
        ws = str(workspace or ".")
        title = str(payload.get("title") or payload.get("name") or title).strip()
        skill_id = str(payload.get("id") or payload.get("skill_id") or skill_id or title).strip()
        rules_in = payload.get("rules") if isinstance(payload.get("rules"), list) else rules
        content = str(payload.get("content") or content or "").strip()
        if not content and rules_in:
            content = "\n".join(f"- {r}" for r in rules_in if str(r).strip())
        category = str(payload.get("category") or category or "self-installed")
        languages = payload.get("languages") if isinstance(payload.get("languages"), list) else languages
        project_types = (
            payload.get("projectTypes")
            if isinstance(payload.get("projectTypes"), list)
            else (payload.get("project_types") if isinstance(payload.get("project_types"), list) else project_types)
        )
        triggers = payload.get("triggers") if isinstance(payload.get("triggers"), list) else triggers
        source = str(payload.get("source") or source or "self_installed")
        summary = str(payload.get("summary") or summary or "") or None
    else:
        ws = str(workspace or workspace_or_payload or ".")
        if not content and rules:
            content = "\n".join(f"- {r}" for r in rules if str(r).strip())

    ensure_builtin_code_skills(ws)
    sid = _slugify_skill_id(skill_id or title)
    sdir = _skills_dir(ws)
    registry = _load_registry(ws)

    clean_content = (content or "").strip()
    if not clean_content.startswith("#"):
        clean_content = f"# Skill: {title or sid}\n\n{clean_content}"

    md_path = sdir / f"{sid}.md"
    md_path.write_text(clean_content + "\n", encoding="utf-8")

    inferred_langs = languages if isinstance(languages, list) and languages else _infer_languages_from_text(clean_content)
    inferred_triggers = (
        [str(t).strip().lower() for t in triggers if str(t).strip()]
        if isinstance(triggers, list) and triggers
        else [w for w in re.split(r"[-_\s]+", f"{sid} {(title or '').lower()}") if len(w) >= 3]
    )

    existing = registry.get(sid, {})
    extracted_rules = [
        line.strip().lstrip("-* ").strip()
        for line in clean_content.splitlines()
        if line.strip().startswith(("- ", "* "))
    ]
    meta = {
        "id": sid,
        "title": (title or existing.get("title") or sid.replace("-", " ").title())[:120],
        "category": category or existing.get("category") or "self-installed",
        "languages": list(dict.fromkeys(inferred_langs)),
        "projectTypes": list(dict.fromkeys(project_types or existing.get("projectTypes") or [])),
        "triggers": list(dict.fromkeys(inferred_triggers))[:20],
        "source": source or existing.get("source") or "self_installed",
        "summary": (summary or _extract_summary(clean_content))[:220],
        "rules": extracted_rules,
        "installedAt": int(time.time()),
        "usageCount": int(existing.get("usageCount", 0)) + 1,
    }
    registry[sid] = meta
    _save_registry(ws, registry)
    return {
        **meta,
        "content": clean_content,
        "path": f".aurora/skills/{sid}.md",
    }


def delete_code_skill(skill_id: str, workspace: str | pathlib.Path = ".") -> bool:
    """Supprime une compétence personnalisée/auto-installée (protège les compétences maîtresses builtin)."""
    ws = str(workspace)
    ensure_builtin_code_skills(ws)
    sid = _slugify_skill_id(skill_id)
    builtin_ids = {b["id"] for b in BUILTIN_CODE_SKILLS}
    if sid in builtin_ids:
        return False
    sdir = _skills_dir(ws)
    registry = _load_registry(ws)
    md_path = sdir / f"{sid}.md"
    removed = False
    if md_path.is_file():
        md_path.unlink()
        removed = True
    if sid in registry:
        registry.pop(sid, None)
        _save_registry(ws, registry)
        removed = True
    return removed


def auto_acquire_skills_for_mission(
    workspace: str | pathlib.Path = ".",
    *,
    prompt: str = "",
    project_type: str = "unknown",
    languages: list[str] | None = None,
    frameworks: list[str] | None = None,
    learned_pattern: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sélectionne les compétences pertinentes pour une mission de code et, si la mission
    combine plusieurs systèmes ou un domaine spécialisé non encore couvert, synthétise
    et installe automatiquement une compétence dédiée dans `.aurora/skills/`."""
    ws = str(workspace)
    all_skills = ensure_builtin_code_skills(ws)
    registry = _load_registry(ws)
    lower_prompt = (prompt or "").lower()
    req_langs = [str(l).lower() for l in (languages or []) if str(l).strip()]
    req_fws = [str(f).lower() for f in (frameworks or []) if str(f).strip()]

    matched: list[tuple[int, dict[str, Any]]] = []
    for skill in all_skills:
        score = 0
        skill_langs = [str(l).lower() for l in (skill.get("languages") or [])]
        skill_types = [str(t).lower() for t in (skill.get("projectTypes") or [])]
        skill_triggers = [str(tr).lower() for tr in (skill.get("triggers") or [])]

        if project_type and project_type.lower() in skill_types:
            score += 4
        for lang in req_langs:
            if lang in skill_langs:
                score += 3
        for fw in req_fws:
            if fw in skill_triggers or fw in skill_langs:
                score += 2
        for trig in skill_triggers:
            if trig and trig in lower_prompt:
                score += 2
        if skill["id"] == "self-organization-execution-protocol":
            score += 2

        if score >= 2:
            matched.append((score, skill))

    matched.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    selected = [pair[1] for pair in matched[:6]]

    newly_installed: list[dict[str, Any]] = []
    existing_ids = set(registry.keys())

    # 1. Synthèse automatique d'un pont polyglotte si >= 2 langages distincts
    core_langs = [l for l in req_langs if l not in ("html", "css", "yaml", "json", "markdown")]
    if len(core_langs) >= 2:
        combo_key = "-".join(sorted(dict.fromkeys(core_langs))[:3])
        sid = f"polyglot-bridge-{combo_key}"
        if sid not in existing_ids:
            langs_label = " + ".join(l.upper() for l in dict.fromkeys(core_langs[:3]))
            installed_poly = install_code_skill(
                ws,
                skill_id=sid,
                title=f"Pont Multi-Systèmes {langs_label} (Auto-Installé)",
                category="auto-learned",
                languages=core_langs,
                project_types=[project_type, "multi_system"],
                triggers=core_langs + ["multi-system", "ffi", "ipc"],
                source="self_installed",
                summary=f"Protocole d'interfaçage, d'organisation des répertoires et de validation croisée pour les systèmes combinant {langs_label}.",
                content=(
                    f"# Skill: Pont Multi-Systèmes {langs_label} (Auto-Installé)\n\n"
                    f"## Organisation Structurée ({langs_label})\n"
                    "- Isoler chaque langage dans un sous-dossier explicite ou par préfixe clair avec son manifeste/compilateur propre.\n"
                    f"- Définir un contrat d'échange de données strict entre {langs_label} (ABI C `extern \"C\"` ou IPC JSON versionné).\n"
                    "- Ordonner la validation sandbox : compiler et tester le composant bas niveau en premier, puis exécuter l'orchestrateur haut niveau.\n"
                ),
            )
            newly_installed.append(installed_poly)
            selected.insert(0, installed_poly)
            existing_ids.add(sid)

    # 2. Synthèse de skill de domaine complexe
    synthesized = _synthesize_domain_skill_if_needed(
        prompt=prompt,
        project_type=project_type,
        languages=req_langs,
        frameworks=req_fws,
        existing_ids=existing_ids,
    )
    if synthesized is not None:
        installed = install_code_skill(ws, **synthesized)
        newly_installed.append(installed)
        selected.insert(0, installed)
        existing_ids.add(installed["id"])

    # 3. Pattern appris en fin de génération/correction
    if isinstance(learned_pattern, dict) and learned_pattern.get("content"):
        installed = install_code_skill(
            ws,
            skill_id=str(learned_pattern.get("id") or learned_pattern.get("title") or "learned-pattern"),
            title=str(learned_pattern.get("title") or "Compétence auto-apprise"),
            content=str(learned_pattern.get("content")),
            category=str(learned_pattern.get("category") or "auto-learned"),
            languages=req_langs,
            project_types=[project_type] if project_type else [],
            triggers=learned_pattern.get("triggers") if isinstance(learned_pattern.get("triggers"), list) else None,
            source="self_installed",
            summary=str(learned_pattern.get("summary") or ""),
        )
        newly_installed.append(installed)
        selected.insert(0, installed)

    # Incrémenter le compteur d'usage des skills activés
    registry = _load_registry(ws)
    for s in selected:
        sid = s["id"]
        if sid in registry:
            registry[sid]["usageCount"] = int(registry[sid].get("usageCount", 0)) + 1
    _save_registry(ws, registry)

    return {
        "ok": True,
        "activeSkills": selected,
        "newlyInstalled": newly_installed,
        "totalInstalled": len(registry),
    }


def _synthesize_domain_skill_if_needed(
    *,
    prompt: str,
    project_type: str,
    languages: list[str],
    frameworks: list[str],
    existing_ids: set[str],
) -> dict[str, Any] | None:
    """Détecte les demandes d'ingénierie spécialisées (émulateurs, cryptographie,
    moteurs physiques/audio) et synthétise automatiquement une compétence réutilisable."""
    lower = (prompt or "").lower()
    if len(lower) < 12:
        return None

    domain_Blueprints = [
        (
            "emulator-cpu-architecture",
            ["émulateur", "emulateur", "emulator", "chip-8", "chip8", "risc-v", "riscv", "6502", "z80", "gameboy", "opcode"],
            "Architecture d'Émulateur CPU & Cycle Fetch-Decode-Execute",
            ["c", "cpp", "rust", "assembly", "python", "swift"],
            """# Skill: Architecture d'Émulateur CPU & Cycle Fetch-Decode-Execute

## Invariants d'Ingénierie
- Modéliser l'état matériel dans une structure déterministe : banque de registres, compteur ordinal (`PC`), pointeur de pile (`SP`), registre d'état/flags (`Z, N, C, V`), et bus mémoire adressable avec contrôle de bornes.
- Implémenter une boucle `step()` pure : `fetch(PC)` -> `decode(opcode)` -> `execute(instr)` -> mise à jour des cycles et timers.
- Fournir une ROM ou un programme binaire de test intégré et un désassembleur lisible pour valider chaque classe d'instructions en sandbox.
""",
        ),
        (
            "cryptography-security-primitives",
            ["cryptographie", "cryptographique", "chiffrement", "aes", "sha-256", "sha256", "chacha20", "ed25519", "rsa", "hmac", "zero-knowledge", "merkle"],
            "Primitives Cryptographiques, Constant-Time & Vecteurs de Test",
            ["rust", "c", "cpp", "assembly", "python", "swift", "go"],
            """# Skill: Primitives Cryptographiques, Constant-Time & Vecteurs de Test

## Invariants d'Ingénierie
- Comparer les secrets et condensats en temps constant (XOR accumulateur sans branchement conditionnel dépendant des secrets).
- Gérer explicitement l'endianness (Big-Endian pour SHA-256, Little-Endian pour ChaCha20/Poly1305) avec rotations bit-à-bit exactes (`rotl`/`rotr` sur mots de 32 ou 64 bits).
- Valider systématiquement l'implémentation contre les vecteurs de test officiels (NIST / RFC) dans la suite d'auto-test avant toute livraison.
""",
        ),
        (
            "realtime-dsp-audio-physics-engine",
            ["dsp", "synthétiseur", "synthetiseur", "fft", "filtre biquad", "moteur physique", "physics engine", "verlet", "rk4", "runge-kutta", "raytracer", "raytracing"],
            "Moteur Temps Réel (DSP / Physique / Raytracing) & Stabilité Numérique",
            ["cpp", "rust", "c", "swift", "python", "typescript", "assembly"],
            """# Skill: Moteur Temps Réel (DSP / Physique / Raytracing) & Stabilité Numérique

## Invariants d'Ingénierie
- Utiliser un pas de temps fixe (`dt` déterministe, intégration Semi-Implicit Euler, Verlet ou RK4) pour garantir la stabilité numérique et la conservation d'énergie.
- Éviter toute allocation dynamique (`malloc`/`new`) dans la boucle critique par échantillon ou par frame.
- Protéger les calculs flottants contre `NaN` / `Inf` (dénormaux, divisions par zéro avec `epsilon = 1e-9`) et vérifier les bornes en sortie.
""",
        ),
    ]

    for sid, keywords, title, langs, content in domain_Blueprints:
        if sid not in existing_ids and any(k in lower for k in keywords):
            return {
                "skill_id": sid,
                "title": f"{title} (Auto-Installé)",
                "category": "auto-learned",
                "languages": langs,
                "project_types": [project_type],
                "triggers": keywords[:8],
                "source": "self_installed",
                "summary": _extract_summary(content),
                "content": content,
            }

    return None


def inspect_code_agents_and_toolchains(workspace: str | pathlib.Path = ".") -> dict[str, Any]:
    """Retourne un diagnostic factuel de l'état des agents AuroraIA et des compilateurs/runtimes."""
    ws = str(workspace)
    skills = ensure_builtin_code_skills(ws)
    adir = _agents_dir(ws)

    # 1. Agents officiels et sous-agents dynamiques (.aurora/agents/*.json)
    official_agents: list[dict[str, Any]] = []
    try:
        from agi_core.mission_protocol import OFFICIAL_AGENTS
        for name, spec in OFFICIAL_AGENTS.items():
            official_agents.append({
                "id": name,
                "module": spec.get("module", "general"),
                "description": spec.get("description", ""),
                "canCreateSubagents": bool(spec.get("can_create_subagents", False)),
                "source": "official",
            })
    except Exception:
        pass

    dynamic_agents: list[dict[str, Any]] = []
    if adir.is_dir():
        for fpath in sorted(adir.glob("*.json")):
            try:
                spec = json.loads(fpath.read_text(encoding="utf-8"))
                if isinstance(spec, dict):
                    dynamic_agents.append({
                        "id": spec.get("name") or fpath.stem,
                        "module": spec.get("module", "code"),
                        "description": spec.get("description", ""),
                        "canCreateSubagents": bool(spec.get("can_create_subagents", True)),
                        "source": "dynamic",
                    })
            except Exception:
                continue

    # 2. Rôles spécialisés du pipeline Code (Orchestrateur Multi-Systèmes)
    code_pipeline_roles = [
        {
            "id": "code-architect",
            "name": "Architecte Système & Topologie",
            "title": "Architecte Système",
            "role": "Décomposition atomique, sélection Best-of-N du plan JSON, contrats inter-systèmes (FFI/IPC/API) et acquisition de skills.",
            "specialty": "Planification multi-systèmes, contrats FFI/IPC & acquisition de skills",
            "active": True,
            "status": "ready",
        },
        {
            "id": "code-lowlevel-engineer",
            "name": "Ingénieur Bas Niveau (ASM / C / C++ / Rust / Swift)",
            "title": "Ingénieur Bas Niveau",
            "role": "Génération de code natif, ABI System V x86_64/ARM64, gestion mémoire déterministe, compilation native sans stub.",
            "specialty": "Assembleur x86_64/ARM64, Swift, Rust, C/C++, ABI System V",
            "active": True,
            "status": "ready",
        },
        {
            "id": "code-app-engineer",
            "name": "Ingénieur Applicatif & Polyglotte (Python / TS / Go)",
            "title": "Ingénieur Applicatif",
            "role": "Orchestration haut niveau, interfaces graphiques/web, APIs, ponts ctypes/subprocess/IPC et cohérence des imports.",
            "specialty": "Orchestration Python/TS/Go, ponts FFI/IPC & interfaces",
            "active": True,
            "status": "ready",
        },
        {
            "id": "code-auditor-verifier",
            "name": "Auditeur Impitoyable & Juge Sandbox",
            "title": "Auditeur Sandbox",
            "role": "Exécution réelle par sous-système dans le sandbox isolé, garde anti-régression et boucle d'auto-correction ciblée.",
            "specialty": "Validation sandbox multi-système & auto-correction",
            "active": True,
            "status": "ready",
        },
    ]

    # 3. Chaînes de compilation et runtimes réellement présents sur l'hôte
    toolchains = {
        "assembly_nasm": shutil.which("nasm") is not None,
        "assembly_gas": shutil.which("as") is not None,
        "c_gcc_clang": (shutil.which("gcc") or shutil.which("clang")) is not None,
        "cpp_gpp_clangpp": (shutil.which("g++") or shutil.which("clang++")) is not None,
        "rust_cargo": (shutil.which("cargo") or shutil.which("rustc")) is not None,
        "swift": (shutil.which("swift") or shutil.which("swiftc")) is not None,
        "go": shutil.which("go") is not None,
        "python3": (shutil.which("python3") or shutil.which("python")) is not None,
        "node": shutil.which("node") is not None,
        "make_cmake": (shutil.which("make") or shutil.which("cmake")) is not None,
    }

    return {
        "ok": True,
        "skillsCount": len(skills),
        "builtinSkillsCount": sum(1 for s in skills if s.get("source") == "builtin"),
        "selfInstalledSkillsCount": sum(1 for s in skills if s.get("source") != "builtin"),
        "officialAgents": official_agents,
        "dynamicAgents": dynamic_agents,
        "codePipelineRoles": code_pipeline_roles,
        "codeSubAgentRoles": code_pipeline_roles,
        "toolchains": toolchains,
    }


def register_code_skills_routes(bp: Blueprint, workspace: str | pathlib.Path = ".", *, allowed=None) -> None:
    """Enregistre les routes `/api/code/skills*` et `/api/code/agents-status`."""
    ws = str(workspace)

    def _check_write_allowed() -> bool:
        if allowed is None:
            return True
        try:
            return bool(allowed())
        except Exception:
            return False

    @bp.route("/api/code/skills", methods=["GET"])
    def list_code_skills_route():
        skills = ensure_builtin_code_skills(ws)
        return jsonify({
            "ok": True,
            "skills": skills,
            "total": len(skills),
            "count": len(skills),
        })

    @bp.route("/api/code/skills/install", methods=["POST"])
    def install_code_skill_route():
        if not _check_write_allowed():
            return jsonify({"ok": False, "error": "forbidden_public"}), 403
        body = request.get_json(silent=True) or {}
        title = str(body.get("title") or body.get("name") or "").strip()
        rules = body.get("rules") if isinstance(body.get("rules"), list) else None
        content = str(body.get("content") or "").strip()
        if not content and rules:
            content = "\n".join(f"- {r}" for r in rules if str(r).strip())
        if not title or not content:
            return jsonify({"ok": False, "error": "Les champs 'title' et 'content' (ou 'rules') sont requis."}), 400
        skill = install_code_skill(
            ws,
            skill_id=str(body.get("id") or body.get("name") or title),
            title=title,
            content=content,
            rules=rules,
            category=str(body.get("category") or "self-installed"),
            languages=body.get("languages") if isinstance(body.get("languages"), list) else None,
            project_types=body.get("projectTypes") if isinstance(body.get("projectTypes"), list) else None,
            triggers=body.get("triggers") if isinstance(body.get("triggers"), list) else None,
            source=str(body.get("source") or "self_installed"),
            summary=str(body.get("summary") or "") or None,
        )
        return jsonify({"ok": True, "skill": skill})

    @bp.route("/api/code/skills/auto-acquire", methods=["POST"])
    def auto_acquire_code_skills_route():
        if not _check_write_allowed():
            return jsonify({"ok": False, "error": "forbidden_public"}), 403
        body = request.get_json(silent=True) or {}
        result = auto_acquire_skills_for_mission(
            ws,
            prompt=str(body.get("prompt") or ""),
            project_type=str(body.get("projectType") or "unknown"),
            languages=body.get("languages") if isinstance(body.get("languages"), list) else None,
            frameworks=body.get("frameworks") if isinstance(body.get("frameworks"), list) else None,
            learned_pattern=body.get("learnedPattern") if isinstance(body.get("learnedPattern"), dict) else None,
        )
        return jsonify(result)

    @bp.route("/api/code/skills/<skill_id>", methods=["DELETE"])
    def delete_code_skill_route(skill_id: str):
        if not _check_write_allowed():
            return jsonify({"ok": False, "error": "forbidden_public"}), 403
        removed = delete_code_skill(skill_id, workspace=ws)
        skills = ensure_builtin_code_skills(ws)
        return jsonify({"ok": True, "removed": removed, "skills": skills})

    @bp.route("/api/code/agents-status", methods=["GET"])
    def code_agents_status_route():
        report = inspect_code_agents_and_toolchains(ws)
        return jsonify(report)

