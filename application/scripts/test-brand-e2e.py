"""End-to-end smoke test of the brand_landing pipeline.

Posts a minimal-but-faithful version of the Codeur system prompt to Ollama
via the tunnel bridge and checks the resulting HTML for the markers the
real pipeline expects (subject name, canonical palette, image placeholders,
3D primitives, shader, post-processing — and the absence of off-topic
drift).

Usage:
    python scripts/test-brand-e2e.py [brand_name]

The test prompt is built in lockstep with what `codeOrchestrator.ts` would
inject when `subject.source === 'brand'` and `productShape === 'bottle'`,
so the output is a fair proxy for what the real module would produce on
the same prompt. Mirroring the prompt exactly is the goal — when the real
prompt evolves (e.g. v76 adds a new directive), update this file too.
"""

from __future__ import annotations

import json
import re
import sys
import time
from typing import Iterable

import requests

TUNNEL = "https://fin-isaac-reduce-fingers.trycloudflare.com"
# Default to the production code model. Override with a smaller model only for
# intentionally fast smoke tests when latency matters more than output quality.
import os as _os  # noqa: E402
MODEL = _os.environ.get("AURORA_TEST_MODEL", "qwen3-coder-next:q4_K_M")


def build_system_prompt(brand: str, primary: str, secondary: str, keywords: list[str]) -> str:
    """Compose the same shape of system prompt the TS pipeline injects.

    Mirrors `buildSubjectLockBlock` + `buildDesignContractBlock` (visual)
    + `buildPremiumDesignReferenceBlock(forcedVariant='brand_landing')` +
    `describeProductShapeHint('bottle')` from codeSystemPrompts.ts /
    codeDesignReference.ts. Trimmed for token budget.
    """
    return f"""Tu es un Developpeur Senior du pipeline AuroraIA. Tu generes du CODE SOURCE PUR.
Format: chaque fichier commence par `--- FICHIER: chemin/nom.ext ---` puis le contenu complet.

## VERROUILLAGE SUJET — REGLE INVIOLABLE
- Le sujet de cette page est: {brand}.
- "{brand}" DOIT apparaitre dans <title>, <h1> du hero, et dans au moins 3 sections distinctes.
- INTERDIT de deriver vers restaurant generique, blog culinaire, cafe abstrait.

## PALETTE OBLIGATOIRE
- Couleur primaire: {primary} (utilisee pour hero, CTAs, accents — domine 50-70% du visuel).
- Couleur secondaire: {secondary} (text, backgrounds alternes).
- PAS de violet/cyan/ambre du starter generique.

## PRODUITS / TERMES CLES
- A integrer dans titres / paragraphes: {", ".join(keywords)}.
- Au moins 2 dans les titres de section.

## ASSETS REELS DEJA TELECHARGES
- Markers literaux a placer comme valeur de src= dans les <img>:
  - `PLACEHOLDER_SUBJECT_IMG` ou `PLACEHOLDER_SUBJECT_IMG_1` -> image principale (hero).
  - `PLACEHOLDER_SUBJECT_IMG_2` -> image secondaire (lifestyle).
  - `PLACEHOLDER_SUBJECT_IMG_3` -> image tertiaire (showcase).
- Au minimum: PLACEHOLDER_SUBJECT_IMG dans le hero ET PLACEHOLDER_SUBJECT_IMG_2 dans une section gallery.

## DESIGN CONTRACT (project visuel)
- Hero full-height 100vh, headline clamp(3rem, 7vw, 6.5rem), font-weight 800-900, kerning -0.025em.
- Subheadline 1-2 lignes (max 18 mots), 2 CTAs (primary plein + ghost outline).
- Au moins 7 sections riches: nav fixed, hero, heritage, produits/variantes, gallery, KPI chiffres, citation, CTA final, footer.
- Mode sombre/clair via data-theme + localStorage + prefers-color-scheme.
- Min 7 micro-interactions: scroll reveal IntersectionObserver, nav scroll>40px backdrop-blur, hero parallax, hover cards scale 1.04, counters easeOutCubic, magnetic buttons, mousemove blob.
- Typo Google Fonts (preconnect): "Pacifico" pour wordmark scriptural + "Inter" 400/600/800 body.

## EFFET 3D PROCEDURAL OBLIGATOIRE — BOUTEILLE
- Three.js via CDN ESM `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js`.
- OrbitControls + EffectComposer + RenderPass + UnrealBloomPass + OutputPass via examples/jsm/.
- BOUTEILLE en LatheGeometry: definir 8-12 points (x,y) pour le profil silhouette (base large, retrecit au col, goulot).
- Material: MeshPhysicalMaterial(transmission:0.9, ior:1.45, thickness:0.5, roughness:0.05, attenuationColor: 0xF40009, attenuationDistance:0.5) -> effet verre.
- Label: CylinderGeometry interieur enroule autour du corps avec MeshStandardMaterial map=TextureLoader().load("PLACEHOLDER_SUBJECT_IMG_1").
- Bouchon: CylinderGeometry petite hauteur en {secondary} metallise.
- Eclairage: HemisphereLight(0xffffff, 0x222222, 0.6) + DirectionalLight(0xffffff, 1.6, position(5,8,5)) + PointLight(0x{primary[1:]}, 0.7).
- WebGLRenderer({{antialias:true, alpha:true}}), pixelRatio min(devicePixelRatio,2), outputColorSpace=THREE.SRGBColorSpace, toneMapping=THREE.ACESFilmicToneMapping.
- OrbitControls(enableDamping:true, dampingFactor:0.06, autoRotate:true, autoRotateSpeed:1.2).

## EFFET SHADER GLSL SIGNATURE OBLIGATOIRE
- ShaderMaterial Hologramme Fresnel sur halo scale-up autour de la bouteille:
  - uniforms: {{ uColor: new THREE.Color({primary}), uTime: 0, uIntensity: 1.4 }}.
  - vertexShader: passe vWorldNormal + vViewDir (camera - worldPos).
  - fragmentShader: float fresnel = pow(1.0 - max(dot(vWorldNormal, vViewDir), 0.0), 3.0); vec3 col = uColor * fresnel * uIntensity * (0.7 + 0.3 * sin(uTime * 2.0)); gl_FragColor = vec4(col, fresnel);
  - transparent:true, blending: AdditiveBlending, depthWrite:false.
  - Chaque frame: fresnelMat.uniforms.uTime.value = clock.getElapsedTime().

## POST-PROCESSING OBLIGATOIRE
- EffectComposer + RenderPass + UnrealBloomPass(threshold:0.65, strength:0.85, radius:0.5) + OutputPass.
- composer.render() au lieu de renderer.render().

## PARTICLE SYSTEM ARRIERE-PLAN
- Canvas absolute pointer-events:none plein-ecran derriere la scene 3D.
- Bulles blanches qui montent (bubbles_alpha + sin float) — coherent avec le sujet boisson gazeuse.

## INTERDICTIONS ABSOLUES
- Pas de "TODO" / "// reste du code" / "placeholder" / "implement here".
- Pas de Tauri / Electron / Cargo.toml (project type = static_web).
- Pas de mention de "restaurant", "menu du jour", "blog culinaire", "cafe generique".
- Pas de palette violet/cyan/ambre du starter generique.

## OUTPUT ATTENDU
Genere UN SEUL fichier index.html complet et autonome avec TOUT en inline:
- <style> CSS variables completes + design contract.
- <script type="importmap"> three + addons via CDN ESM.
- <script type="module"> code Three.js + shader + scene complete.
GENERE LE CODE MAINTENANT.
"""


def call_ollama(system_prompt: str, user_prompt: str, *, timeout: int = 480) -> str:
    """POST /api/ollama/chat through the tunnel and return the assistant text.

    Uses streaming so Cloudflare doesn't time out (524) when the first token
    is more than ~90s away (e.g. cold model load). Each NDJSON chunk keeps
    the connection alive. We accumulate `message.content` across chunks.
    """
    # The bridge has `/proxy/ollama/api/chat` which is a transparent proxy to
    # the local Ollama. We use the proxy directly to keep streaming honest.
    url = f"{TUNNEL}/proxy/ollama/api/chat"
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
        "options": {"temperature": 0.05, "num_predict": 6000, "num_ctx": 16384},
    }
    print(f"[1/3] POST {url} (model={MODEL}, system={len(system_prompt)} chars)")
    t0 = time.time()
    chunks: list[str] = []
    try:
        with requests.post(url, json=body, timeout=timeout, stream=True) as resp:
            print(f"[2/3] HTTP {resp.status_code}")
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = obj.get("message", {})
                piece = msg.get("content") or obj.get("response") or ""
                if piece:
                    chunks.append(piece)
                if obj.get("done"):
                    break
    finally:
        elapsed = time.time() - t0
        total = sum(len(c) for c in chunks)
        print(f"[2/3] streamed {total} chars over {elapsed:.1f}s ({len(chunks)} chunks)")
    return "".join(chunks)


def evaluate_brand_fidelity(output: str, brand: str, primary: str, keywords: Iterable[str]) -> dict:
    """Evaluate whether the produced HTML respects the brand contract.

    Mirrors `evaluateBrandFidelity` from codeFidelityGate.ts in spirit:
    name occurrences, palette presence, marker usage, product keyword
    coverage, off-topic drift detection.
    """
    lowered = output.lower()
    primary_low = primary.lower()
    name_re = re.compile(re.escape(brand), re.IGNORECASE)
    name_count = len(name_re.findall(output))
    has_primary = primary_low in lowered or primary_low.lstrip("#") in lowered
    placeholder_count = len(re.findall(r"PLACEHOLDER_SUBJECT_IMG(_\d+)?", output))
    matched_keywords = [k for k in keywords if k.lower() in lowered]
    drift_terms = ["restaurant", "menu du jour", "blog culinaire", "cafe generique"]
    drift_hits = [t for t in drift_terms if re.search(rf"\b{re.escape(t)}\b", lowered)]
    has_threejs = "three.module.js" in lowered or "three@0.160" in lowered
    has_shader = "shadermaterial" in lowered or "fragmentshader" in lowered
    has_bloom = "unrealbloom" in lowered or "bloompass" in lowered
    has_orbit = "orbitcontrols" in lowered

    return {
        "subject_name_count": name_count,
        "primary_color_present": has_primary,
        "placeholder_marker_count": placeholder_count,
        "product_keywords_matched": matched_keywords,
        "drift_terms_detected": drift_hits,
        "threejs_present": has_threejs,
        "shader_present": has_shader,
        "bloom_present": has_bloom,
        "orbitcontrols_present": has_orbit,
        "output_length": len(output),
    }


def score_report(report: dict, brand: str) -> tuple[int, list[str]]:
    """Translate the report into a 0-100 score + list of issues."""
    issues: list[str] = []
    score = 100
    if report["subject_name_count"] == 0:
        issues.append(f'"{brand}" missing entirely (cap to 30)')
        score = min(score, 30)
    elif report["subject_name_count"] < 3:
        issues.append(f'"{brand}" appears only {report["subject_name_count"]}x (-10)')
        score -= 10
    if not report["primary_color_present"]:
        issues.append("primary color absent (-20)")
        score -= 20
    if report["placeholder_marker_count"] == 0:
        issues.append("no PLACEHOLDER_SUBJECT_IMG marker used (-15)")
        score -= 15
    if not report["product_keywords_matched"]:
        issues.append("no product keyword in copy (-10)")
        score -= 10
    if report["drift_terms_detected"]:
        issues.append(f'off-topic drift: {report["drift_terms_detected"]} (-25)')
        score -= 25
    if not report["threejs_present"]:
        issues.append("no Three.js import (-15)")
        score -= 15
    if not report["shader_present"]:
        issues.append("no shader signature (-10)")
        score -= 10
    if not report["bloom_present"]:
        issues.append("no bloom post-processing (-5)")
        score -= 5
    if not report["orbitcontrols_present"]:
        issues.append("no OrbitControls (-5)")
        score -= 5
    return max(0, score), issues


def fetch_brand_enrich(brand: str) -> "dict | None":
    """Call the bridge /api/brand/enrich to fetch a dynamic profile.

    Used for brands not in the small static cache below. Mirrors what the
    real orchestrator does for inferred_brand subjects.
    """
    try:
        r = requests.post(
            f"{TUNNEL}/api/brand/enrich",
            json={"brand": brand},
            timeout=60,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if not data.get("ok"):
            return None
        return data.get("profile")
    except Exception:
        return None


def build_shader_retry_prompt(brand: str, primary: str, original_output: str) -> str:
    """Mirror what buildCorrectionMessages would inject when shader_signature_missing fires.

    The TS pipeline auto-injects a retry hint with the exact shader code when
    the gate (codeFidelityGate Rule 6) detects no ShaderMaterial / fragmentShader
    in the visual output. Here we simulate that behavior: rebuild the prompt
    with a "shader is REQUIRED, here's the verbatim copy-paste" hint AT THE
    TOP, plus a reminder of the original brief.
    """
    return (
        "## REGENERATION FORCEE — SHADER FRESNEL MANQUANT\n"
        f"Ta sortie precedente pour la page {brand} ne contient AUCUN shader signature.\n"
        "La gate de fidelite a rejete cette sortie. Tu DOIS regenerer en incluant\n"
        "le bloc shader Hologramme Fresnel verbatim (copy-paste ci-dessous):\n\n"
        "```js\n"
        "const haloMat = new THREE.ShaderMaterial({\n"
        "  uniforms: {\n"
        f"    uColor: {{ value: new THREE.Color('{primary}') }},\n"
        "    uTime: { value: 0 },\n"
        "  },\n"
        "  vertexShader: `\n"
        "    varying vec3 vNormalW;\n"
        "    varying vec3 vViewDir;\n"
        "    void main() {\n"
        "      vec4 worldPos = modelMatrix * vec4(position, 1.0);\n"
        "      vNormalW = normalize(mat3(modelMatrix) * normal);\n"
        "      vViewDir = normalize(cameraPosition - worldPos.xyz);\n"
        "      gl_Position = projectionMatrix * viewMatrix * worldPos;\n"
        "    }\n"
        "  `,\n"
        "  fragmentShader: `\n"
        "    uniform vec3 uColor;\n"
        "    uniform float uTime;\n"
        "    varying vec3 vNormalW;\n"
        "    varying vec3 vViewDir;\n"
        "    void main() {\n"
        "      float fresnel = pow(1.0 - max(dot(vNormalW, vViewDir), 0.0), 3.0);\n"
        "      float pulse = 0.7 + 0.3 * sin(uTime * 2.0);\n"
        "      gl_FragColor = vec4(uColor * fresnel * 1.4 * pulse, fresnel);\n"
        "    }\n"
        "  `,\n"
        "  transparent: true,\n"
        "  blending: THREE.AdditiveBlending,\n"
        "  depthWrite: false,\n"
        "})\n"
        "// Apres avoir cree le mesh principal du produit:\n"
        "const halo = new THREE.Mesh(productMesh.geometry, haloMat)\n"
        "halo.scale.setScalar(1.08)\n"
        "productMesh.add(halo)\n"
        "// Dans le requestAnimationFrame loop:\n"
        "// haloMat.uniforms.uTime.value = clock.getElapsedTime()\n"
        "```\n\n"
        f"Reecris l index.html complet pour {brand} en incluant ce shader. Garde le reste\n"
        "de la structure (hero, sections, palette canonique, markers PLACEHOLDER_SUBJECT_IMG)\n"
        "comme ta sortie precedente — ajoute juste le shader manquant.\n"
    )


def main() -> int:
    brand = sys.argv[1] if len(sys.argv) > 1 else "Coca-Cola"
    multi_shot = "--multi-shot" in sys.argv or _os.environ.get("AURORA_MULTI_SHOT") == "1"
    # v77 — small static cache for the harness. The orchestrator has 47 of these
    # but for the smoke test we keep just the ones we use as baselines. For any
    # other brand, the harness now calls /api/brand/enrich on the bridge —
    # exactly the same code path the real pipeline uses for inferred_brand.
    if brand == "Coca-Cola":
        primary = "#F40009"
        secondary = "#FFFFFF"
        keywords = ["bouteille en verre", "canette rouge", "logo Spencerian script"]
    elif brand.lower().startswith("tesla"):
        primary = "#E31937"
        secondary = "#000000"
        keywords = ["Model S", "Cybertruck", "tableau de bord minimal"]
    elif brand.lower().startswith("iphone"):
        primary = "#000000"
        secondary = "#A2AAAD"
        keywords = ["titanium", "Dynamic Island", "camera lenses"]
    else:
        # Dynamic enrichment via bridge — same path as the real pipeline.
        print(f"[0/3] Brand '{brand}' not in static cache, calling /api/brand/enrich...")
        enriched = fetch_brand_enrich(brand)
        if enriched:
            primary = enriched.get("primaryColor") or "#0A0A0B"
            secondary = enriched.get("secondaryColor") or "#FFFFFF"
            keywords_raw = enriched.get("productKeywords") or []
            keywords = [k for k in keywords_raw if isinstance(k, str)][:5]
            print(f"[0/3] Enriched: primary={primary} secondary={secondary} keywords={keywords}")
        else:
            print(f"[0/3] Enrichment failed — falling back to generic profile.")
            primary = "#0A0A0B"
            secondary = "#FFFFFF"
            keywords = []

    user_prompt = f"page de presentation ultra stylisee avec graphisme/effet 3D pour l article {brand}"
    system_prompt = build_system_prompt(brand, primary, secondary, keywords)

    try:
        output = call_ollama(system_prompt, user_prompt)
    except Exception as exc:
        print(f"[FAIL] Ollama call failed: {exc}", file=sys.stderr)
        return 2

    print(f"[3/3] Output length: {len(output)} chars")
    if len(output) < 500:
        print(f"[WARN] Output suspiciously short:\n{output}", file=sys.stderr)

    # Persist the raw output to a temp dir (not the repo) so the user can
    # inspect it manually if a score drops unexpectedly between runs. The
    # AURORA_TEST_OUT env var lets the user redirect to a different folder.
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", brand).strip("-").lower() or "subject"
    out_dir = _os.environ.get("AURORA_TEST_OUT") or _os.path.join(
        _os.environ.get("TEMP") or _os.environ.get("TMPDIR") or "/tmp",
        "aurora-test-outputs",
    )
    output_path = _os.path.join(out_dir, f"brand-e2e-{slug}.html")
    try:
        _os.makedirs(out_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[3/3] Saved raw output -> {output_path}")
    except OSError as exc:
        print(f"[WARN] Could not persist output: {exc}", file=sys.stderr)

    report = evaluate_brand_fidelity(output, brand, primary, keywords)
    score, issues = score_report(report, brand)

    print()
    print("=" * 64)
    print(f"BRAND FIDELITY REPORT — {brand} (RUN 1)")
    print("=" * 64)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print()
    print(f"SCORE: {score}/100")
    if issues:
        print("ISSUES:")
        for line in issues:
            print(f"  - {line}")
    else:
        print("ISSUES: none")
    print("=" * 64)

    # Multi-shot mode — simulate the pipeline's retry-on-gate-failure path.
    # Mirrors what buildCorrectionMessages does when codeFidelityGate Rule 6
    # detects shader_signature_missing.
    if multi_shot and not report["shader_present"]:
        print()
        print("=" * 64)
        print(f"MULTI-SHOT RETRY — shader missing detected, regenerating...")
        print("=" * 64)
        retry_prompt = build_shader_retry_prompt(brand, primary, output)
        try:
            retry_output = call_ollama(system_prompt, retry_prompt, timeout=480)
        except Exception as exc:
            print(f"[FAIL] Retry call failed: {exc}", file=sys.stderr)
            return 1 if score < 70 else 0
        retry_report = evaluate_brand_fidelity(retry_output, brand, primary, keywords)
        retry_score, retry_issues = score_report(retry_report, brand)
        print()
        print("=" * 64)
        print(f"BRAND FIDELITY REPORT — {brand} (RUN 2 / RETRY)")
        print("=" * 64)
        print(json.dumps(retry_report, indent=2, ensure_ascii=False))
        print()
        print(f"SCORE: {retry_score}/100  (was {score}/100, delta {retry_score - score:+d})")
        if retry_issues:
            print("ISSUES:")
            for line in retry_issues:
                print(f"  - {line}")
        else:
            print("ISSUES: none")
        print("=" * 64)
        # Use the retry score as the final score for exit code purposes.
        score = retry_score

    return 0 if score >= 70 else 1


if __name__ == "__main__":
    sys.exit(main())
