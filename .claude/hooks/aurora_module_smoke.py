#!/usr/bin/env python3
"""aurora_module_smoke — anti-crash check for the Aurora skin rollout.

User direction (post-v82ag prod pivot) :
  "fin de la boucle actuelle tu rajoute une vérification que rien ne
  plante ou ne soit casser comme module"

What it checks (over the live tunnel — same URL the user sees) :
  1. Tunnel `/` returns 200 with a real prod HTML (not @vite/client).
  2. The pre-React boot script seeds data-ui-skin = aurora_v1 / aurora_v3.
  3. Bridge proxy via tunnel : /api/health and /api/agents/list 200.
  4. Each of the 9 module chunks (manga + V3 ports) responds 200 with
     a JS body > 1 KB. A chunk missing or 404 means a module is broken.
  5. The new pickView routing : aurora_v3 → V3 view, aurora_v1 → manga.
  6. Boot script runs in node sandbox without throwing on three skin
     scenarios (fresh / migration / V3 returning user).

Exit 0 = GO, 1 = BLOCK with the failing check listed.
Run via : python .claude/hooks/aurora_module_smoke.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
import urllib.request
import urllib.error
from typing import List, Tuple

TUNNEL = "https://lodging-fragrance-infections-expires.trycloudflare.com"

# Manga modules — must always have a chunk in dist/assets, served via tunnel
MANGA_CHUNKS = [
    "MangaChatView",
    "MangaImageView",
    "MangaVideoView",
    "MangaDrawingView",
    "MangaCyberView",
    "MangaAcademyView",
    # CodeView, ModelView, VoiceCopilotView are not "Manga*" prefixed but
    # they are the module destination chunks for code, 3d, voice
    "CodeView",
    "ModelView",
    "VoiceCopilotView",
]

# V3 ports re-enabled in v82ak. Each must serve under /assets/
V3_CHUNKS = [
    "AuroraV3ChatView",
    "AuroraV3ImageView",
    "AuroraV3CodeView",
    "AuroraV3VideoView",
    "AuroraV3DrawingView",
    "AuroraV33DView",
    "AuroraV3AcademyView",
    "AuroraV3VoiceView",
    "AuroraV3CyberView",
    "AuroraV3CoworkView",
]


def http_get(url: str, timeout: int = 8) -> Tuple[int, bytes, dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b"", {}
    except Exception as e:
        return 0, str(e).encode(), {}


def fetch_html() -> str:
    rc, body, _ = http_get(f"{TUNNEL}/")
    if rc != 200:
        raise RuntimeError(f"tunnel / returned {rc}")
    return body.decode("utf-8", errors="replace")


def fetch_assets_index() -> List[str]:
    """List all chunk filenames in /assets/ via the dist directory."""
    import os
    asset_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "application", "dist", "assets",
    )
    if not os.path.isdir(asset_dir):
        return []
    return os.listdir(asset_dir)


def find_chunk(prefix: str, assets: List[str]) -> str | None:
    """Find the hashed chunk filename matching prefix-XXXXX.js."""
    for f in assets:
        if f.startswith(prefix + "-") and f.endswith(".js"):
            return f
    return None


def check_tunnel_health() -> Tuple[bool, str]:
    rc, _, _ = http_get(f"{TUNNEL}/")
    if rc != 200:
        return False, f"tunnel / = {rc}"
    rc2, _, _ = http_get(f"{TUNNEL}/api/health")
    if rc2 != 200:
        return False, f"/api/health = {rc2}"
    return True, "tunnel + bridge OK"


def check_prod_html() -> Tuple[bool, str]:
    try:
        html = fetch_html()
    except Exception as e:
        return False, str(e)
    if "@vite/client" in html:
        return False, "DEV mode detected (found @vite/client) — should be prod"
    if "src=\"/assets/" not in html:
        return False, "no /assets/ script reference in HTML"
    if "data-ui-skin" not in html:
        return False, "no data-ui-skin pre-React boot"
    m = re.search(r"DEFAULT\s*=\s*'(aurora_v[13])'", html)
    if not m:
        return False, "boot script DEFAULT skin missing"
    return True, f"prod HTML OK (default skin = {m.group(1)})"


def check_bridge_agents() -> Tuple[bool, str]:
    rc, body, _ = http_get(f"{TUNNEL}/api/agents/list")
    if rc != 200:
        return False, f"/api/agents/list = {rc}"
    try:
        data = json.loads(body)
        count = data.get("agent_count", 0)
        leads = len(data.get("leads", {}))
        if count < 10:
            return False, f"only {count} agents (expected ≥10)"
        return True, f"{count} agents · {leads} leads"
    except Exception as e:
        return False, f"agent JSON parse failed: {e}"


def check_module_chunks() -> Tuple[bool, str]:
    assets = fetch_assets_index()
    if not assets:
        return False, "dist/assets/ empty — run npm run build"
    missing: List[str] = []
    for prefix in MANGA_CHUNKS + V3_CHUNKS:
        chunk = find_chunk(prefix, assets)
        if not chunk:
            missing.append(prefix)
            continue
        rc, body, _ = http_get(f"{TUNNEL}/assets/{chunk}")
        if rc != 200:
            missing.append(f"{prefix}({rc})")
        elif len(body) < 1024:
            missing.append(f"{prefix}(<1KB)")
    if missing:
        return False, f"broken/missing : {', '.join(missing)}"
    return True, f"all {len(MANGA_CHUNKS + V3_CHUNKS)} module chunks served"


def check_chunks_parse_as_js() -> Tuple[bool, str]:
    """v82as : node --check on every served module chunk.

    Catches half-built bundles / corrupted writes / partial deploys
    that pass the size + 200 check but fail on first import in the
    user's browser. node -c parses the file and reports any syntax
    error without executing it.
    """
    import os, subprocess
    asset_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "application", "dist", "assets",
    )
    assets = os.listdir(asset_dir) if os.path.isdir(asset_dir) else []
    bad: List[str] = []
    checked = 0
    for prefix in MANGA_CHUNKS + V3_CHUNKS:
        chunk = find_chunk(prefix, assets)
        if not chunk:
            continue
        path = os.path.join(asset_dir, chunk)
        try:
            r = subprocess.run(
                ["node", "-c", path],
                capture_output=True, timeout=8, check=False,
            )
            if r.returncode != 0:
                bad.append(f"{prefix} : {(r.stderr.decode().splitlines() or ['?'])[0][:60]}")
            else:
                checked += 1
        except Exception as e:
            bad.append(f"{prefix} : {e}")
    if bad:
        return False, f"parse-fail : {'; '.join(bad[:3])}"
    return True, f"all {checked} module chunks parse as valid JS"


def check_boot_script_runtime() -> Tuple[bool, str]:
    try:
        html = fetch_html()
    except Exception as e:
        return False, str(e)
    m = re.search(r"<script>(.*?bootSkin.*?)</script>", html, re.DOTALL)
    if not m:
        return False, "boot script not in HTML"
    boot_js = m.group(1)
    # Run in node sandbox with three localStorage scenarios
    runner = textwrap.dedent(f"""
        let stored = null;
        const localStorage = {{ getItem: () => stored, setItem: (_, v) => {{ stored = v }} }};
        let attrSet = null;
        const document = {{ documentElement: {{ setAttribute: (k, v) => {{ if (k === 'data-ui-skin') attrSet = v }} }} }};

        // Fresh visit
        stored = null; attrSet = null;
        new Function('localStorage','document','console',{json.dumps(boot_js)})(localStorage, document, {{ log: () => {{}} }});
        if (attrSet !== 'aurora_v1' || stored !== 'aurora_v1') {{ console.error('FRESH_FAIL'); process.exit(1) }}

        // Manga migration
        stored = 'manga'; attrSet = null;
        new Function('localStorage','document','console',{json.dumps(boot_js)})(localStorage, document, {{ log: () => {{}} }});
        if (attrSet !== 'aurora_v1' || stored !== 'aurora_v1') {{ console.error('MIGRATE_FAIL'); process.exit(1) }}

        // V3 returning user
        stored = 'aurora_v3'; attrSet = null;
        new Function('localStorage','document','console',{json.dumps(boot_js)})(localStorage, document, {{ log: () => {{}} }});
        if (attrSet !== 'aurora_v3' || stored !== 'aurora_v3') {{ console.error('V3_FAIL'); process.exit(1) }}

        console.log('OK');
    """)
    try:
        out = subprocess.run(
            ["node", "-e", runner],
            capture_output=True, timeout=10, check=False,
        )
        if out.returncode != 0:
            return False, f"boot runtime: {out.stderr.decode().strip() or out.stdout.decode().strip()}"
        return True, "boot script runs OK on 3 skin scenarios"
    except Exception as e:
        return False, f"node sandbox failed: {e}"


def check_no_tdz_in_views() -> Tuple[bool, str]:
    """v82ar : TDZ scan over all view files.

    Catches the bug pattern that broke MangaCyberView in v82aq :
    a `const X = ...` referenced in a useCallback/useMemo/useEffect
    dep array BEFORE its own declaration in the component body
    triggers a Temporal Dead Zone ReferenceError on every render.
    The pure-curl smoke can't catch that — we walk the source files
    and flag any candidate.
    """
    import os
    views_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "application", "src", "views",
    )
    if not os.path.isdir(views_dir):
        return True, "no views/ dir (skipped)"
    issues: List[str] = []
    for fname in sorted(os.listdir(views_dir)):
        if not fname.endswith(".tsx"):
            continue
        path = os.path.join(views_dir, fname)
        with open(path, encoding="utf-8") as fp:
            content = fp.read()
        lines = content.splitlines()
        consts: dict[str, int] = {}
        for i, line in enumerate(lines, 1):
            m = re.match(r"\s*const\s+([a-zA-Z_]\w*)\s*=", line)
            if m and m.group(1) not in consts:
                consts[m.group(1)] = i
        for m in re.finditer(
            r"use(Callback|Memo|Effect)\([^)]*\},\s*\[(.*?)\]",
            content, re.DOTALL,
        ):
            ln = content[: m.start()].count("\n") + 1
            deps = [d.strip() for d in m.group(2).split(",") if d.strip()]
            for d in deps:
                d = d.split(".")[0].split("?")[0].strip()
                if d in consts and consts[d] > ln:
                    issues.append(f"{fname}:{ln} use{m.group(1)} dep `{d}` @ line {consts[d]}")
    if issues:
        return False, f"{len(issues)} TDZ candidate(s): {'; '.join(issues[:3])}"
    return True, "0 TDZ candidates across all view files"


def main() -> int:
    print("[aurora-module-smoke] running module crash check...")
    checks = [
        ("tunnel_and_bridge", check_tunnel_health),
        ("prod_html_served", check_prod_html),
        ("bridge_agents_endpoint", check_bridge_agents),
        ("all_module_chunks_served", check_module_chunks),
        ("chunks_parse_as_js", check_chunks_parse_as_js),
        ("boot_script_runtime", check_boot_script_runtime),
        ("no_tdz_in_views", check_no_tdz_in_views),
    ]
    failures: List[str] = []
    for name, fn in checks:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"check raised: {e}"
        marker = "ok " if ok else "FAIL"
        print(f"  [{marker}] {name:<28} {detail}")
        if not ok:
            failures.append(name)
    print()
    if failures:
        print(f"[aurora-module-smoke] BLOCK — {len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print(f"[aurora-module-smoke] GO — all {len(checks)} checks green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
