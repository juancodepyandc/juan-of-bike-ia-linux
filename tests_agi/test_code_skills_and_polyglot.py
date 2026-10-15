from __future__ import annotations

import json
import subprocess
from pathlib import Path

from flask import Flask

from application.code_skills_api import (
    auto_acquire_skills_for_mission,
    delete_code_skill,
    ensure_builtin_code_skills,
    inspect_code_agents_and_toolchains,
    install_code_skill,
    register_code_skills_routes,
)


def test_ensure_builtin_code_skills_seeds_master_skills(tmp_path: Path) -> None:
    skills = ensure_builtin_code_skills(tmp_path)
    skill_ids = {s["id"] for s in skills}
    assert "asm-x86_64-arm64-abi" in skill_ids
    assert "swift-modern-systems" in skill_ids
    assert "multi-system-polyglot-architecture" in skill_ids
    assert "rust-c-cpp-systems" in skill_ids
    assert "python-clean-architecture" in skill_ids
    assert "algorithmic-problem-solving" in skill_ids
    assert "compiler-vm-kernel-design" in skill_ids
    assert "self-organization-execution-protocol" in skill_ids

    skills_dir = tmp_path / ".aurora" / "skills"
    assert (skills_dir / "asm-x86_64-arm64-abi.md").is_file()
    assert (skills_dir / "swift-modern-systems.md").is_file()
    assert (skills_dir / "registry.json").is_file()


def test_install_and_delete_custom_code_skill(tmp_path: Path) -> None:
    ensure_builtin_code_skills(tmp_path)
    installed = install_code_skill(
        {
            "title": "SIMD AVX-512 Assembly Intrinsics",
            "category": "low-level-master",
            "languages": ["assembly", "c", "cpp"],
            "projectTypes": ["system_asm", "multi_system"],
            "summary": "Optimisation vectorielle AVX-512 et alignement 64 octets.",
            "rules": [
                "Aligner les tampons mémoire sur 64 octets.",
                "Nettoyer l'état supérieur ZMM avec vzeroupper si transition SSE.",
            ],
            "source": "user-installed",
        },
        workspace=tmp_path,
    )
    assert installed["id"] == "simd-avx-512-assembly-intrinsics"
    md_file = tmp_path / ".aurora" / "skills" / "simd-avx-512-assembly-intrinsics.md"
    assert md_file.is_file()
    assert "AVX-512" in md_file.read_text(encoding="utf-8")

    # Builtin skill cannot be deleted
    assert delete_code_skill("asm-x86_64-arm64-abi", workspace=tmp_path) is False
    # Custom skill can be deleted
    assert delete_code_skill("simd-avx-512-assembly-intrinsics", workspace=tmp_path) is True
    assert not md_file.exists()


def test_auto_acquire_skills_synthesizes_polyglot_and_domain_skills(tmp_path: Path) -> None:
    result = auto_acquire_skills_for_mission(
        prompt=(
            "Conçois une architecture multi-système avec un émulateur CPU 6502 en Assembleur x86_64 "
            "et C, couplé à un débogueur et orchestrateur en Python et Swift."
        ),
        languages=["assembly", "c", "python", "swift"],
        project_type="multi_system",
        workspace=tmp_path,
    )
    assert result["ok"] is True
    active_ids = {s["id"] for s in result["activeSkills"]}
    newly_ids = {s["id"] for s in result["newlyInstalled"]}

    # Builtin master skills matched
    assert "asm-x86_64-arm64-abi" in active_ids
    assert "swift-modern-systems" in active_ids
    assert "multi-system-polyglot-architecture" in active_ids
    assert "compiler-vm-kernel-design" in active_ids

    # Newly synthesized & self-installed skills
    assert "emulator-cpu-architecture" in newly_ids
    assert any(sid.startswith("polyglot-bridge-") for sid in newly_ids)


def test_flask_code_skills_and_agents_routes(tmp_path: Path) -> None:
    app = Flask(__name__)
    register_code_skills_routes(app, workspace=tmp_path)
    client = app.test_client()

    res_list = client.get("/api/code/skills")
    assert res_list.status_code == 200
    data_list = res_list.get_json()
    assert data_list["ok"] is True
    assert data_list["count"] >= 8

    res_install = client.post(
        "/api/code/skills/install",
        json={
            "title": "Swift Metal Compute Shaders",
            "languages": ["swift"],
            "projectTypes": ["cli_swift"],
            "rules": ["Isoler le command buffer GPU dans un acteur dédié."],
        },
    )
    assert res_install.status_code == 200
    installed = res_install.get_json()["skill"]
    assert installed["id"] == "swift-metal-compute-shaders"

    res_acquire = client.post(
        "/api/code/skills/auto-acquire",
        json={
            "prompt": "Système cryptographique SHA-256 constant-time en Assembleur et Rust avec interface Python",
            "languages": ["assembly", "rust", "python"],
            "projectType": "multi_system",
        },
    )
    assert res_acquire.status_code == 200
    acq_data = res_acquire.get_json()
    assert acq_data["ok"] is True
    assert any(s["id"] == "cryptography-security-primitives" for s in acq_data["newlyInstalled"])

    res_status = client.get("/api/code/agents-status")
    assert res_status.status_code == 200
    status_data = res_status.get_json()
    assert status_data["ok"] is True
    assert len(status_data["codeSubAgentRoles"]) == 4
    assert "python3" in status_data["toolchains"]


def test_typescript_polyglot_intent_sandbox_and_skills_pipeline() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = """
import { classifyCodeIntent } from './application/src/services/codeIntentClassification.ts';
import { detectDominantLanguage, detectProjectLanguages, buildCommandsForLanguage } from './application/src/services/codeSandboxCommands.ts';
import { selectAndSynthesizeSkillsSync, buildActiveSkillsPromptBlock, resolveActiveSubAgentRolesForIntent } from './application/src/services/codeSkillsRegistry.ts';
import { buildFallbackArchitecturePlan } from './application/src/services/codeArchitecturePlanFallback.ts';
import { parseArchitecturePlanJson } from './application/src/services/codeArchitecturePlan.ts';

const asmIntent = classifyCodeIntent('Ecris une routine en Assembleur x86_64 NASM avec ABI System V et registres rdi rsi rax');
const swiftIntent = classifyCodeIntent('Cree un outil CLI en Swift 6 avec Package.swift et acteurs async/await');
const multiIntent = classifyCodeIntent('Architecture multi-systeme polyglotte avec noyau Assembleur x86_64 et C couple a un orchestrateur Python via FFI');

const asmFiles = [
  { name: 'src/main.asm', content: 'section .text\\nglobal _start\\n_start:\\n  mov rax, 60\\n  xor rdi, rdi\\n  syscall\\n' },
  { name: 'Makefile', content: 'all:\\n\\tnasm -felf64 src/main.asm\\n' },
];
const multiFiles = [
  { name: 'core_native/fast.asm', content: 'section .text\\nglobal fast_add\\nfast_add:\\n  mov rax, rdi\\n  add rax, rsi\\n  ret\\n' },
  { name: 'core_native/bridge.c', content: '#include <stdint.h>\\nint64_t bridge(int64_t a, int64_t b) { return a + b; }\\n' },
  { name: 'orchestrator/main.py', content: 'def run():\\n    return 42\\nif __name__ == "__main__":\\n    print(run())\\n' },
];

const asmLang = detectDominantLanguage(asmFiles);
const multiLang = detectDominantLanguage(multiFiles);
const multiLangs = detectProjectLanguages(multiFiles);
const asmCmds = buildCommandsForLanguage('assembly', asmFiles);
const swiftCmds = buildCommandsForLanguage('swift', [{ name: 'Package.swift', content: '// swift-tools-version: 5.10' }, { name: 'Sources/App/main.swift', content: 'print("ok")' }]);
const multiCmds = buildCommandsForLanguage('multi-system', multiFiles);

const skillsSel = selectAndSynthesizeSkillsSync('Architecture multi-systeme Assembleur x86_64 + Swift + Python', multiIntent);
const promptBlock = buildActiveSkillsPromptBlock(skillsSel.activeSkills);
const roles = resolveActiveSubAgentRolesForIntent(multiIntent);

const fallbackAsmPlan = buildFallbackArchitecturePlan(asmIntent, 'Routine ASM x86_64');
const fallbackMultiPlan = buildFallbackArchitecturePlan(multiIntent, 'Système polyglotte ASM + C + Python');

console.log(JSON.stringify({
  asmProjectType: asmIntent.projectType,
  asmLanguages: asmIntent.languages,
  swiftProjectType: swiftIntent.projectType,
  swiftLanguages: swiftIntent.languages,
  multiProjectType: multiIntent.projectType,
  multiLanguages: multiIntent.languages,
  asmLang,
  multiLang,
  multiLangs,
  asmCmdCount: asmCmds.length,
  swiftCmdCount: swiftCmds.length,
  multiCmdCount: multiCmds.length,
  activeSkillsCount: skillsSel.activeSkills.length,
  promptBlockHasHeader: promptBlock.includes('SKILLS D INGENIERIE ACTIFS'),
  activeRolesCount: roles.filter(r => r.active).length,
  fallbackAsmValid: parseArchitecturePlanJson(fallbackAsmPlan).ok,
  fallbackMultiValid: parseArchitecturePlanJson(fallbackMultiPlan).ok,
}));
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "-e", script],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["asmProjectType"] == "system_asm"
    assert "assembly" in payload["asmLanguages"]
    assert payload["swiftProjectType"] == "cli_swift"
    assert "swift" in payload["swiftLanguages"]
    assert payload["multiProjectType"] == "multi_system"
    assert len(payload["multiLanguages"]) >= 2
    assert payload["asmLang"] == "assembly"
    assert payload["multiLang"] == "multi-system"
    assert set(payload["multiLangs"]) >= {"assembly", "c", "python"}
    assert payload["asmCmdCount"] >= 1
    assert payload["swiftCmdCount"] >= 1
    assert payload["multiCmdCount"] >= 3
    assert payload["activeSkillsCount"] >= 4
    assert payload["promptBlockHasHeader"] is True
    assert payload["activeRolesCount"] == 4
    assert payload["fallbackAsmValid"] is True
    assert payload["fallbackMultiValid"] is True
