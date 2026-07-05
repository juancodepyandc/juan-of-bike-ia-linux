"""Aurora module uplift loop — walks each module's services, audits prompt
strings, and proposes principal-engineer-grade replacements without
breaking anything.

Strategy:
1. For each module, list its `<module>*.ts` services (or its directory if
   the module has one — cyber/, learning/, simulator/).
2. For each file, scan for long string literals (>= 280 chars) that look
   like LLM system prompts (heuristic: contains "Tu es" or "You are"
   plus a few sentences).
3. For each candidate, ask qwen3-coder to:
     a) audit the prompt vs principal-engineer standards
     b) write an improved version that keeps the same semantics
     c) flag if no change needed (already expert)
4. Write the improved prompt back in-place (string-literal replacement).
5. Run `tsc --noEmit` after each file edit; if it fails, rollback that
   file from .bak.
6. Commit per file with a descriptive message.

Safe by design: every change has a .bak, every change is tsc-validated,
no batch changes — one file at a time.

Usage:
    python aurora_module_uplift.py --module learning      # one module
    python aurora_module_uplift.py --all                  # walk every module
    python aurora_module_uplift.py --module voice --dry-run

Modules covered: conversation, image, voice, video, drawing, threeD,
learning, cyber, simulator, cowork, code. (code/cowork/threeD already
done — flag --force to re-audit.)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AURORA = Path(r"C:\Users\Juan\Desktop\ia\AuroraIA-v2")
SERVICES = AURORA / "application" / "src" / "services"

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3-coder:30b-a3b-q4_K_M"

# How we know which files belong to which module (heuristic).
MODULE_PATTERNS: dict[str, list[str]] = {
    "conversation": ["conversation*.ts"],
    "image": ["codeImageGen.ts", "imageGen*.ts"],
    "voice": ["voice*.ts", "talkingHead*.ts"],
    "video": ["video*.ts"],
    "drawing": ["drawing*.ts", "characterForge.ts"],
    "threeD": ["threeD*.ts", "pbr*.ts", "meshPostprocess.ts", "meshRescue.ts"],
    "learning": ["learning/*.ts", "learning*.ts", "bacResources.ts", "academicContentVerification.ts"],
    "cyber": ["cyber/*.ts"],
    "simulator": ["simulator/*.ts", "kinematicsLibrary.ts"],
    "cowork": ["cowork*.ts"],
    "code": ["codeOrchestrator.ts", "codeReasoning*.ts", "codeIntent.ts", "codeFidelityGate.ts",
              "codeMissionControl.ts", "codeAutoCorrection.ts", "codeSystemPrompts.ts"],
}

# Heuristic markers in a string literal that suggest it IS an LLM prompt.
PROMPT_MARKERS = [
    "Tu es ", "You are ", "tu es ", "you are ",
    "système de", "system prompt", "ROLE:", "RÔLE:", "## Rôle",
    "Tu réponds", "Réponds en", "respond in",
]

# Auto-skip patterns (definitely not LLM prompts).
SKIP_MARKERS = [
    "data:image", "<!DOCTYPE", "<svg", "console.log",
    "import ", "export const",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("uplift")


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def ollama_chat(system: str, user: str, num_predict: int = 3000,
                  num_ctx: int = 16384) -> str:
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        "stream": False,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0.3},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    return obj.get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Prompt extraction + replacement
# ---------------------------------------------------------------------------

PROMPT_RE = re.compile(
    r"(`)((?:[^`\\]|\\.){280,}?)(`)"
    r"|"
    r"(\"|\')((?:[^\"\'\\]|\\.){280,}?)\4",
    re.DOTALL,
)


def find_prompt_literals(source: str) -> list[tuple[int, int, str, str]]:
    """Return [(start, end, quote_char, content), ...] for long string literals
    that look like LLM prompts (contain a marker)."""
    out = []
    for m in PROMPT_RE.finditer(source):
        if m.group(1):
            quote = "`"
            content = m.group(2)
        else:
            quote = m.group(4) or "'"
            content = m.group(5)
        if any(s in content for s in SKIP_MARKERS):
            continue
        if not any(s in content for s in PROMPT_MARKERS):
            continue
        out.append((m.start(), m.end(), quote, content))
    return out


def audit_and_improve(prompt_text: str, module: str) -> tuple[str | None, str]:
    """Strict principal-engineer auditor. Skips only when there is literally
    nothing to add. Improvements are mandatory whenever a concrete weakness
    can be named.
    """
    sys_msg = (
        "You are a STRICT principal-engineer prompt reviewer for Aurora's `"
        + module + "` module. Your bar: would a senior LLM ops engineer "
        "look at this prompt and say it can be improved? If YES, you MUST "
        "propose the rewrite. Never skip on the basis of 'looks fine'.\n\n"
        "Concrete failure signals that require a rewrite:\n"
        " - No numbered quality bar (1) 2) 3) ...) with at least 5 items.\n"
        " - No explicit negative constraints / 'Do NOT ...' section.\n"
        " - No output format specification when an output format applies.\n"
        " - Vague identity ('you are a helpful assistant').\n"
        " - Missing domain-specific best practices (e.g. accessibility for "
        "web, exit codes for CLI, AbortController for fetch, RAF cleanup for "
        "three.js, type hints for Python).\n\n"
        "Decision rule: only return SKIP if the prompt already has BOTH "
        "(a) at least 5 numbered quality bars AND (b) explicit negative "
        "constraints. Otherwise REWRITE.\n\n"
        "When you rewrite, output the improved prompt INSIDE <NEW_PROMPT>...</NEW_PROMPT> tags, "
        "keeping the same language (French/English) and same role, just "
        "higher rigor. Keep the LENGTH within 1x to 2x of the original."
    )
    user_msg = (
        f"Module: {module}\n\nCurrent prompt ({len(prompt_text)} chars):\n"
        f"\"\"\"\n{prompt_text}\n\"\"\"\n\nApply the decision rule strictly."
    )
    response = ollama_chat(sys_msg, user_msg, num_predict=4000)
    if response.strip().startswith("SKIP:") or response.strip().startswith("SKIP "):
        return None, response.strip()[:200]
    m = re.search(r"<NEW_PROMPT>(.*?)</NEW_PROMPT>", response, re.DOTALL)
    if not m:
        return None, f"no <NEW_PROMPT> tag in response (first 300c): {response[:300]}"
    improved = m.group(1).strip()
    if len(improved) < len(prompt_text) * 0.5:
        return None, f"improved version suspiciously shorter ({len(improved)} vs {len(prompt_text)}), skipping"
    return improved, "improved"


# ---------------------------------------------------------------------------
# File operations + tsc rollback
# ---------------------------------------------------------------------------

def tsc_check() -> tuple[bool, str]:
    """Run tsc --noEmit; return (ok, stderr_tail)."""
    res = subprocess.run(
        ["npx", "tsc", "--noEmit"],
        cwd=str(AURORA / "application"),
        capture_output=True, text=True, timeout=180,
        shell=sys.platform.startswith("win"),
    )
    return res.returncode == 0, (res.stderr or res.stdout)[-1500:]


def rewrite_file(path: Path, replacements: list[tuple[int, int, str, str]]) -> int:
    """Apply replacements (start, end, quote, new_content) to file content in
    reverse order so offsets stay valid. Returns count of replacements."""
    source = path.read_text(encoding="utf-8")
    replacements.sort(key=lambda r: r[0], reverse=True)
    for start, end, quote, new_content in replacements:
        escaped = new_content.replace("\\", "\\\\").replace(quote, f"\\{quote}")
        source = source[:start] + quote + escaped + quote + source[end:]
    path.write_text(source, encoding="utf-8")
    return len(replacements)


def uplift_file(path: Path, module: str, dry_run: bool = False) -> dict:
    log.info(f"  scan {path.relative_to(AURORA)}")
    source = path.read_text(encoding="utf-8")
    candidates = find_prompt_literals(source)
    log.info(f"    {len(candidates)} prompt-literal candidates")
    if not candidates:
        return {"file": str(path.relative_to(AURORA)), "candidates": 0, "applied": 0}

    backup = path.with_suffix(path.suffix + ".bak")
    if not dry_run:
        shutil.copy2(path, backup)

    replacements: list[tuple[int, int, str, str]] = []
    notes: list[str] = []
    for (start, end, quote, content) in candidates:
        log.info(f"    audit literal at {start} ({len(content)} chars)")
        improved, reason = audit_and_improve(content, module)
        if improved is None:
            notes.append(f"  - {start}: {reason}")
            continue
        replacements.append((start, end, quote, improved))
        notes.append(f"  - {start}: improved ({len(content)} -> {len(improved)} chars)")

    if not replacements:
        if not dry_run and backup.exists():
            backup.unlink()
        return {"file": str(path.relative_to(AURORA)), "candidates": len(candidates),
                  "applied": 0, "notes": notes}

    # Write proposals to _dev/uplift_proposals/<module>/<basename>.md so a
    # human can review + apply. In-place replacement is high-risk because
    # the LLM-generated prompt content can break the surrounding template
    # literal escape (backticks, ${}, etc.) and we saw 10 tsc rollbacks
    # on the first strict run. Proposals are still useful — the LLM did
    # find real improvements, they just need careful integration.
    proposals_dir = AURORA / "_dev" / "uplift_proposals" / module
    proposals_dir.mkdir(parents=True, exist_ok=True)
    proposal_file = proposals_dir / (path.stem + ".md")
    with proposal_file.open("a", encoding="utf-8") as pf:
        for (start, end, _, new_content) in sorted(replacements, key=lambda r: r[0]):
            pf.write(f"\n## {path.name} @ offset {start} ({len(new_content)} chars)\n\n")
            pf.write("**Proposed improvement** (review + apply manually):\n\n")
            pf.write("```\n" + new_content + "\n```\n\n---\n")
    log.info(f"    wrote {len(replacements)} proposals to {proposal_file.relative_to(AURORA)}")
    notes.append(f"  - proposals written to {proposal_file.relative_to(AURORA)}")

    if dry_run:
        return {"file": str(path.relative_to(AURORA)), "candidates": len(candidates),
                  "applied_dry_run": len(replacements), "notes": notes}

    # In-place edit attempt (still safe via tsc rollback).
    n = rewrite_file(path, replacements)
    log.info(f"    applied {n} replacements, running tsc")
    ok, tsc_out = tsc_check()
    if not ok:
        log.warning(f"    tsc FAIL — rolling back. tail:\n{tsc_out[-600:]}")
        shutil.copy2(backup, path)
        return {"file": str(path.relative_to(AURORA)), "candidates": len(candidates),
                  "applied": 0, "rolled_back": True, "tsc_error": tsc_out[-500:]}
    backup.unlink()
    return {"file": str(path.relative_to(AURORA)), "candidates": len(candidates),
              "applied": n, "notes": notes}


def files_for_module(module: str) -> list[Path]:
    paths: list[Path] = []
    for pat in MODULE_PATTERNS.get(module, []):
        paths.extend(SERVICES.glob(pat))
    # de-dup + filter to .ts
    seen, uniq = set(), []
    for p in paths:
        if p.suffix == ".ts" and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", choices=list(MODULE_PATTERNS), default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-files-per-module", type=int, default=10)
    args = ap.parse_args()

    if args.all:
        modules = list(MODULE_PATTERNS)
    elif args.module:
        modules = [args.module]
    else:
        log.error("provide --module or --all")
        return 2

    grand_total = {"modules": 0, "files_audited": 0, "applied": 0, "rolled_back": 0}
    report: list[dict] = []
    for m in modules:
        log.info(f"=== module: {m} ===")
        grand_total["modules"] += 1
        files = files_for_module(m)[: args.max_files_per_module]
        if not files:
            log.info(f"  (no files matched)")
            continue
        for f in files:
            grand_total["files_audited"] += 1
            r = uplift_file(f, m, dry_run=args.dry_run)
            report.append({"module": m, **r})
            grand_total["applied"] += r.get("applied", 0)
            if r.get("rolled_back"):
                grand_total["rolled_back"] += 1
            time.sleep(0.5)
    log.info(f"=== done: {json.dumps(grand_total)} ===")
    (AURORA / "_dev" / "uplift_report.json").parent.mkdir(parents=True, exist_ok=True)
    (AURORA / "_dev" / "uplift_report.json").write_text(
        json.dumps({"total": grand_total, "files": report}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
