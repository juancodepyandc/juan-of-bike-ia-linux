"""Aurora code-loop prompt enricher.

Takes a short or long natural-language prompt, infers project_type via
keyword classification, and emits a structured enriched prompt that gives
qwen3-coder the stack hint + quality bar without bloating the original.

Output contract is the system+user message pair to feed into Ollama chat.

Usage:
    python aurora_code_enrich.py "page presenting tesla cybertruck"
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field

PROJECT_TYPES: dict[str, list[str]] = {
    "static_web_3d": [r"\bthree\.?js\b", r"\bwebgl\b", r"\b3d\s+(scene|app|view|model|game)\b",
                       r"\binteractive 3d\b", r"\borbit controls\b", r"\b3d\b"],
    "static_web_game": [r"\bgame\b", r"\bjeu\b", r"\barcade\b", r"\bplatformer\b", r"\bpuzzle\b"],
    "static_web_sim": [r"\bsimulator\b", r"\bsimulateur\b", r"\bphysics\b", r"\bparticle\b",
                        r"\bfluid\b", r"\bcellular automat", r"\bn-?body\b"],
    "static_web_2d": [r"\bcanvas\b", r"\b2d\b", r"\bdraw(ing)?\b", r"\bpaint\b",
                       r"\bsprite\b", r"\bpixel\b"],
    "static_web_dataviz": [r"\bdata\s*viz\b", r"\bchart\b", r"\bgraph\b", r"\bdashboard\b",
                             r"\bd3\.?js\b", r"\bplot"],
    "static_web_edu": [r"\btutorial\b", r"\beducational\b", r"\bcours\b", r"\bquiz\b",
                        r"\bmath(ematics)?\b", r"\blesson\b"],
    "react_vite": [r"\breact\b", r"\bvite\b", r"\bnext\.?js\b", r"\bjsx\b", r"\btsx\b",
                    r"\buse(state|effect)\b"],
    "python_cli": [r"\bcli\b", r"\bcommand[\s-]line\b", r"\bterminal\b", r"\bargparse\b",
                    r"\bpython tool\b", r"\bscript"],
    "node_express": [r"\bexpress\b", r"\brest api\b", r"\bnode\s+server\b", r"\bbackend\b"],
    "native_electron": [r"\belectron\b", r"\bnative desktop\b", r"\bdesktop app\b"],
    "native_python_gui": [r"\btkinter\b", r"\bpyqt\b", r"\bkivy\b", r"\bpython gui\b"],
    "static_web": [r"\bweb\s*page\b", r"\bsite\b", r"\blanding\b", r"\bhtml\b", r"\bcss\b",
                    r"\bportfolio\b"],
}

STACK_HINTS: dict[str, str] = {
    "static_web_3d": "single-file HTML using Three.js (latest, via CDN), no build step; "
                      "WebGLRenderer, PerspectiveCamera, OrbitControls; animation loop with "
                      "requestAnimationFrame; responsive canvas full window",
    "static_web_game": "single-file HTML5 canvas game with requestAnimationFrame loop, keyboard "
                        "and pointer input, score display, restart logic, no external assets",
    "static_web_sim": "single-file HTML5 canvas simulation with deterministic update loop, "
                       "configurable parameters via on-screen sliders, FPS counter, pause toggle",
    "static_web_2d": "single-file HTML5 canvas drawing/2D app, pointer events, tool palette, "
                      "save-to-PNG via toDataURL",
    "static_web_dataviz": "single-file HTML using Chart.js or vanilla SVG, hardcoded demo data, "
                            "responsive container, accessible legend",
    "static_web_edu": "single-file HTML, clean typography, sectioned tutorial with anchors, "
                       "code blocks with syntax-highlight (highlight.js CDN), interactive examples",
    "react_vite": "Vite + React + TypeScript project, FULLY SELF-CONTAINED. MUST include "
                    "ALL of: package.json with scripts {dev,build,preview} + vite/@vitejs/plugin-react "
                    "+ react + react-dom deps; vite.config.ts with import react from "
                    "@vitejs/plugin-react; tsconfig.json with compilerOptions including "
                    "\\\"rootDir\\\": \\\"./src\\\", \\\"isolatedModules\\\": true, "
                    "\\\"jsx\\\": \\\"react-jsx\\\", \\\"strict\\\": false, "
                    "\\\"noUnusedLocals\\\": false, \\\"noUnusedParameters\\\": false, "
                    "\\\"noImplicitAny\\\": false, \\\"skipLibCheck\\\": true; "
                    "tsconfig.node.json for vite.config; "
                    "index.html with <div id=root>; src/main.tsx mounts App; src/App.tsx. "
                    "Do NOT extend any parent tsconfig — the project is its own root. "
                    "Build MUST succeed without TypeScript errors; remove or use any declared variable.",
    "python_cli": "Python 3.11+ single-file CLI using argparse, typer or click; type hints; "
                    "help text; exit codes; graceful errors; no third-party deps unless asked",
    "node_express": "Node 20 Express server with routes, JSON middleware, simple in-memory store, "
                       "package.json with start script",
    "native_electron": "Electron app: main.js, preload.js, index.html, renderer.js, package.json "
                         "with electron start script",
    "native_python_gui": "Python tkinter app, single file, themed widgets, responsive layout, "
                          "no external assets",
    "static_web": "single-file or multi-file static HTML site: index.html, style.css, optional "
                    "app.js; semantic HTML5; CSS Grid or Flex; responsive mobile-first",
}

QUALITY_BAR = (
    "Code must be production-clean, ultra-premium, and visually stunning. ABSOLUTELY NO SIMPLISTIC MVPs. "
    "You MUST implement high-end graphics: glassmorphism, deep shadows, complex micro-interactions, "
    "smooth parallax or scroll-reveals, responsive fluid layouts, and state-of-the-art animations. "
    "This is for personal use, so you are highly encouraged to precisely replicate the complexity and "
    "visual excellence of famous top-tier applications without holding back for plagiarism concerns. "
    "No TODOs, no lorem-ipsum, no broken links. Comments only when the WHY is non-obvious. "
    "Accessible, responsive (works 360px to 1920px). All assets inline or via well-known CDN. "
    "The UI must be breathtaking and structurally flawless."
)

NEGATIVE_HINTS = (
    "Do not output Bootstrap unless explicitly asked. Do not pad with empty sections. "
    "Do not invent fake brand names or testimonials with real-looking faces. "
    "Do not include analytics scripts. Do not write markdown/explanation outside the file tags."
)

OUTPUT_CONTRACT = """\
OUTPUT FORMAT: emit each file wrapped in <FILE path="relative/path"> ... </FILE> tags, one
per file, with the raw file contents inside (no markdown fence). Emit nothing else outside
the FILE tags. The first file must be the entry point (index.html / main.py / etc.).
"""


@dataclass
class EnrichedPrompt:
    original: str
    project_type: str
    stack_hint: str
    enriched: str
    system: str


def detect_project_type(prompt: str) -> str:
    p = prompt.lower()
    for ptype, patterns in PROJECT_TYPES.items():
        if any(re.search(pat, p) for pat in patterns):
            return ptype
    return "static_web"


def enrich(prompt: str, project_type: str | None = None) -> EnrichedPrompt:
    if project_type is None:
        project_type = detect_project_type(prompt)
    stack = STACK_HINTS.get(project_type, STACK_HINTS["static_web"])
    enriched = prompt.strip().rstrip(".").rstrip(",") + ".\n\n" + (
        f"Stack: {stack}.\n\nQuality bar: {QUALITY_BAR}\n\nNegative: {NEGATIVE_HINTS}"
    )
    system = (
        "You are a principal full-stack engineer with 15+ years of shipping production "
        "software across web, native, embedded, and 3D realtime systems. You think before "
        "you write: layout, data flow, edge cases, accessibility, motion, polish, latency, "
        "and the user moment that the code is meant to create. You name variables like a "
        "human who has to maintain them next year. You never paste lorem-ipsum, never "
        "leave TODO comments, never invent fake brands or testimonials, never reference "
        "external assets that don't exist. You write the smallest project that fulfills "
        "the brief at production quality — no boilerplate trees, no scaffolding for "
        "features that weren't asked for. When the brief is ambiguous, you make the "
        "obvious sensible choice and ship; you do not ask questions.\n\n"
        "Specifics that separate you from junior models:\n"
        " - For HTML/CSS: semantic tags (header/nav/main/section/footer), CSS variables, "
        "fluid typography (clamp), advanced motion (glassmorphism, backdrop-filter, smooth transforms), "
        "reduced-motion honored, focus-visible styled, color contrast >= WCAG AA. ABSOLUTELY NO plain "
        "or boring designs. You must add micro-interactions on hover and active states.\n"
        " - For JS/TS: const/let only, async/await over .then, AbortController for cleanup, "
        "Map/Set when appropriate, no jQuery, no moment.js.\n"
        " - For React: function components + hooks, no class components, no defaultProps, "
        "stable keys, proper cleanup in useEffect, controlled inputs.\n"
        " - For three.js / WebGL: scene + camera + renderer cleanly separated, resize handler, "
        "OrbitControls if the user can interact, no useless lighting setups, request-animation-frame "
        "loop disposed on unmount.\n"
        " - For Python CLI: argparse with full --help, type hints, no try/except: pass, exit "
        "codes that mean something, stdout for data + stderr for diagnostics.\n"
        " - For Node/Express: proper error middleware, JSON content-type, CORS only if needed, "
        "no synchronous fs calls, graceful shutdown.\n\n"
        "Production polish is the floor, not the ceiling. The shipping bar is: a senior dev "
        "on the team reviewing your PR would approve it without comments.\n\n"
        + OUTPUT_CONTRACT
    )
    return EnrichedPrompt(
        original=prompt,
        project_type=project_type,
        stack_hint=stack,
        enriched=enriched,
        system=system,
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: aurora_code_enrich.py <prompt>", file=sys.stderr)
        return 2
    e = enrich(argv[1])
    print(json.dumps(asdict(e), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
