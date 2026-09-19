from flask import Blueprint, request, jsonify, Response, send_file, current_app, abort, g, stream_with_context
import os, subprocess, threading, time, datetime, json, sys, platform, pathlib, shutil, requests, uuid, re, psutil
import urllib.request as _urllib_req
from bridge_server import WORKSPACE, sortie_module, _proxy, _clean_headers, COMFYUI_PORT, OLLAMA_URL, COMFYUI_URL

web_search_bp = Blueprint('web_search_bp', __name__)

# =====================================================================
#  Web search (pour le telephone — remplace invoke("search_duckduckgo"))
# =====================================================================

@web_search_bp.route("/api/web/search", methods=["POST"])
def web_search():
    """Recherche via Crawl4AI (Playwright) avec fallback DuckDuckGo."""
    data = request.get_json()
    query = data.get("query", "")
    limit = data.get("limit", 8)
    if not query.strip():
        return jsonify({"results": ""})

    try:
        # Crawl4AI search (avec Playwright)
        crawl_script = os.path.join(WORKSPACE, "python-services", "crawl4ai_search.py")
        result = subprocess.run(
            [sys.executable, crawl_script, "--mode", "search", "--query", query, "--limit", str(limit)],
            capture_output=True, timeout=30, cwd=WORKSPACE,
        )
        if result.returncode == 0:
            out = json.loads(result.stdout.decode("utf-8", errors="replace"))
            if out.get("ok") and out.get("results"):
                # Format: snippets lisibles pour le LLM
                lines = []
                for r in out["results"]:
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")
                    url = r.get("url", "")
                    if url and snippet:
                        lines.append(f"{title}: {snippet} ({url})")
                    elif url:
                        lines.append(f"{title} ({url})")
                    else:
                        lines.append(f"{title}: {snippet}" if snippet else title)
                return jsonify({
                    "results": "\n".join(lines),
                    "resultsList": out.get("results", []),
                    "engine": out.get("engine", "crawl4ai"),
                })

        # Fallback intégré dans crawl4ai_search.py gère déjà le DuckDuckGo
        return jsonify({"results": result.stdout.decode("utf-8", errors="replace")})
    except Exception as e:
        return jsonify({"results": f"Erreur recherche: {e}"})


def _safe_web_filename(name: str, fallback: str = "resource") -> str:
    import re as _re
    name = (name or fallback).strip().replace("\\", "_").replace("/", "_")
    name = _re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" ._")
    return (name or fallback)[:120]


@web_search_bp.route("/api/web/download", methods=["POST"])
def web_download():
    """Telecharge une ressource web dans output/web_downloads."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    category = _safe_web_filename(data.get("category") or "academic", "academic")
    wanted_name = _safe_web_filename(data.get("filename") or "", "")
    if not url:
        return jsonify({"ok": False, "error": "url manquante"}), 400
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "seules les URL http/https sont supportees"}), 400
    try:
        import mimetypes as _mimetypes
        import pathlib as _pathlib
        import re as _re
        from urllib.parse import urlparse as _urlparse, unquote as _unquote

        with requests.get(url, stream=True, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AuroraIA/2.0; academic-resource-fetcher)",
            "Accept": "application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/html,*/*",
        }) as r:
            if r.status_code >= 400:
                return jsonify({"ok": False, "error": f"HTTP {r.status_code}"}), 502
            content_type = (r.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
            dispo = r.headers.get("Content-Disposition") or ""
            dispo_name = ""
            m = _re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', dispo, _re.I)
            if m:
                dispo_name = _unquote(m.group(1)).strip()
            parsed_name = _unquote(_pathlib.PurePosixPath(_urlparse(url).path).name or "")
            filename = _safe_web_filename(wanted_name or dispo_name or parsed_name or "resource")
            if "." not in filename:
                ext = _mimetypes.guess_extension(content_type) or ""
                if ext:
                    filename += ext
            out_dir = _pathlib.Path(WORKSPACE) / "output" / "web_downloads" / category
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / filename
            if out_path.exists():
                stem, suffix = out_path.stem, out_path.suffix
                i = 2
                while out_path.exists() and i < 1000:
                    out_path = out_dir / f"{stem}-{i}{suffix}"
                    i += 1
            max_bytes = int(data.get("maxBytes") or 80 * 1024 * 1024)
            written = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > max_bytes:
                        try:
                            out_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                        return jsonify({"ok": False, "error": f"fichier trop gros (> {max_bytes} octets)"}), 413
                    f.write(chunk)
        rel = out_path.relative_to(pathlib.Path(WORKSPACE)).as_posix()
        return jsonify({
            "ok": True,
            "url": url,
            "path": rel,
            "filename": out_path.name,
            "bytes": written,
            "contentType": content_type,
            "downloadUrl": f"/api/download/{rel}",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}), 500


@web_search_bp.route("/api/web/extract", methods=["POST"])
def web_extract():
    """Extraire le contenu d'une URL via Crawl4AI."""
    data = request.get_json()
    url = data.get("url", "")
    prompt = data.get("prompt", "")
    if not url.strip():
        return jsonify({"ok": False, "error": "URL manquante"})

    try:
        crawl_script = os.path.join(WORKSPACE, "python-services", "crawl4ai_search.py")
        result = subprocess.run(
            [sys.executable, crawl_script, "--mode", "extract", "--url", url, "--prompt", prompt],
            capture_output=True, timeout=30, cwd=WORKSPACE,
        )
        if result.returncode == 0:
            return Response(result.stdout, mimetype="application/json")
        return jsonify({"ok": False, "error": "Extraction failed"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@web_search_bp.route("/api/web/images", methods=["POST"])
def web_images():
    """Recherche d'images via Crawl4AI."""
    data = request.get_json()
    query = data.get("query", "")
    limit = data.get("limit", 6)
    if not query.strip():
        return jsonify({"ok": False, "images": []})

    try:
        crawl_script = os.path.join(WORKSPACE, "python-services", "crawl4ai_search.py")
        result = subprocess.run(
            [sys.executable, crawl_script, "--mode", "images", "--query", query, "--limit", str(limit)],
            capture_output=True, timeout=30, cwd=WORKSPACE,
        )
        if result.returncode == 0:
            return Response(result.stdout, mimetype="application/json")
        return jsonify({"ok": False, "images": []})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _wikipedia_thumbnail(query: str) -> "tuple[str, bytes, str] | None":
    """Try Wikipedia REST API to grab the page thumbnail for a topic.

    Wikipedia thumbs are the most brand-faithful free source: searching
    "Coca-Cola" returns the real Coca-Cola bottle/logo image used on the
    Wikipedia page, not a random Picsum photo. Tries fr first, then en.

    v73b — query fallback chain: when the exact phrasing doesn't resolve to a
    Wikipedia page (e.g. "Coca-Cola bouteille" or "Spotify logo"), we retry
    with progressively simpler titles:
      1. The query as typed.
      2. The first 3 words.
      3. The first 2 words.
      4. The first word only.
    The first variant that returns a thumbnail wins. This catches "<brand>
    <product>" / "<brand> logo" / "<brand> <variant>" patterns that the
    Code module routinely produces for brand pages.

    Returns (image_url, image_bytes, content_type) or None.
    """
    candidates: list[str] = []
    base = query.strip()
    if not base:
        return None
    candidates.append(base)
    words = [w for w in base.split() if w]
    # Drop trailing words one by one to broaden the search.
    for cut in (3, 2, 1):
        if len(words) > cut:
            shortened = " ".join(words[:cut])
            if shortened and shortened not in candidates:
                candidates.append(shortened)
    # Also try the first word alone (handles "Spotify logo" -> "Spotify").
    if words and words[0] not in candidates:
        candidates.append(words[0])

    for variant in candidates:
        result = _wikipedia_thumbnail_single(variant)
        if result is not None:
            return result
    return None


def _wikipedia_thumbnail_single(query: str) -> "tuple[str, bytes, str] | None":
    """Single-shot Wikipedia thumbnail lookup for an exact title."""
    try:
        from urllib.parse import quote as _q
        normalized_title = query.strip().replace(" ", "_")
        for lang_code in ("fr", "en"):
            url = f"https://{lang_code}.wikipedia.org/api/rest_v1/page/summary/{_q(normalized_title)}"
            try:
                r = requests.get(url, timeout=6, headers={"User-Agent": "AuroraIA-Bridge/1.0 (https://github.com/juancodepyandc/juan-of-bike-ia)"})
            except Exception:
                continue
            if r.status_code != 200:
                continue
            try:
                data = r.json()
            except Exception:
                continue
            # v72b: prefer the API thumbnail (typically 320-640px, 60-300 KB)
            # over originalimage (often 4-6 MB, blows the LLM prompt budget).
            # The pipeline caps inline data URLs at ~350 KB so a HD image
            # gets skipped silently — tu finis avec ZERO image au lieu d une
            # bonne thumbnail.
            thumb = (data.get("thumbnail") or {}).get("source")
            orig = (data.get("originalimage") or {}).get("source")
            candidates = [u for u in (thumb, orig) if u]
            for img_url in candidates:
                try:
                    r2 = requests.get(img_url, timeout=8, headers={"User-Agent": "AuroraIA-Bridge/1.0"})
                    if r2.status_code != 200:
                        continue
                    ctype = (r2.headers.get("Content-Type") or "").split(";")[0].strip() or "image/jpeg"
                    if not ctype.startswith("image/"):
                        continue
                    size = len(r2.content)
                    if size < 2000:
                        continue
                    # Skip ultra-large originals (> 800 KB) — the inline data
                    # URL would be > 1 MB and the TS pipeline rejects it.
                    if size > 800_000 and img_url == orig and thumb:
                        continue
                    return img_url, r2.content, ctype
                except Exception:
                    continue
        return None
    except Exception:
        return None


def _duckduckgo_image(query: str) -> "tuple[str, bytes, str] | None":
    """Scrape DuckDuckGo's image search via the undocumented i.js endpoint.

    Better than Picsum for brand queries — returns real product/brand images
    indexed by DDG. Two-step protocol: first request the HTML page to grab
    the vqd token, then call i.js with that token. Tries the first ~5 image
    URLs returned and downloads the first one that's >= 2KB.

    Returns (image_url, image_bytes, content_type) or None.
    """
    try:
        from urllib.parse import quote as _q
        import re as _re
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        # Step 1 — fetch HTML page to extract vqd token.
        page = requests.get(
            f"https://duckduckgo.com/?q={_q(query)}&iax=images&ia=images",
            timeout=8,
            headers={"User-Agent": ua},
        )
        if page.status_code != 200:
            return None
        m = _re.search(r'vqd=["\']?([\d-]+)["\']?', page.text)
        if not m:
            # Some responses embed it as `vqd:"..."` instead.
            m = _re.search(r'vqd:[\s]*["\']([\d-]+)["\']', page.text)
        if not m:
            return None
        vqd = m.group(1)

        # Step 2 — call the i.js endpoint with the token.
        api_url = f"https://duckduckgo.com/i.js?q={_q(query)}&vqd={vqd}&p=1&o=json"
        api = requests.get(
            api_url,
            timeout=8,
            headers={"User-Agent": ua, "Referer": "https://duckduckgo.com/", "Accept": "application/json"},
        )
        if api.status_code != 200:
            return None
        try:
            data = api.json()
        except Exception:
            return None
        results = data.get("results") or []
        # Try up to 6 candidates to be resilient to dead URLs.
        for entry in results[:6]:
            img_url = entry.get("image") or entry.get("thumbnail")
            if not img_url:
                continue
            try:
                r2 = requests.get(img_url, timeout=7, headers={"User-Agent": ua})
                if r2.status_code != 200:
                    continue
                ctype = (r2.headers.get("Content-Type") or "").split(";")[0].strip() or "image/jpeg"
                if not ctype.startswith("image/"):
                    continue
                if len(r2.content) < 2000:
                    continue
                return img_url, r2.content, ctype
            except Exception:
                continue
        return None
    except Exception:
        return None


def _extract_dominant_color(image_bytes: bytes) -> "str | None":
    """Pull the dominant non-neutral color from an image. Returns hex like '#F40009' or None.

    Used to recover the canonical brand color from the logo Wikipedia returned —
    far more accurate than asking a 7B model to recall the hex from memory
    (the 7B hallucinated #003F5C blue for Heineken, real value is #00A651 green).

    Strategy:
      1. Quantize the image to 8 colors (drops aliasing).
      2. Sort by frequency.
      3. Skip near-white (>240,>240,>240) and near-black (<25,<25,<25) — logos
         frequently have those as background or strokes, they aren't the brand.
      4. Skip very low-saturation grays (max-min < 25 across RGB channels).
      5. Return the first remaining color in hex.
    """
    try:
        from PIL import Image
        from io import BytesIO
        img = Image.open(BytesIO(image_bytes))
        # Convert to RGB (drop alpha — alpha edges look like brand color sometimes).
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Cap size for speed.
        img.thumbnail((200, 200))
        # Quantize to 8 representative colors.
        quantized = img.quantize(colors=8)
        palette = quantized.getpalette() or []
        color_counts = quantized.getcolors() or []
        # Sort by count descending.
        color_counts.sort(key=lambda c: c[0], reverse=True)
        for _count, idx in color_counts:
            base = idx * 3
            if base + 2 >= len(palette):
                continue
            r, g, b = palette[base], palette[base + 1], palette[base + 2]
            # Skip near-white background.
            if r > 240 and g > 240 and b > 240:
                continue
            # Skip near-black strokes.
            if r < 25 and g < 25 and b < 25:
                continue
            # Skip low-saturation grays — branding is rarely gray.
            channels = (r, g, b)
            if max(channels) - min(channels) < 25:
                continue
            return f"#{r:02X}{g:02X}{b:02X}"
        return None
    except Exception:
        return None


def _wikipedia_summary_text(query: str) -> str:
    """Best-effort Wikipedia summary text for a brand/topic. Empty string if not found.

    Tries fr first then en, falls back through the same query-fallback chain
    as `_wikipedia_thumbnail` so "Coca-Cola bouteille" resolves to the
    "Coca-Cola" page when the exact phrasing 404s.
    """
    candidates: list[str] = []
    base = query.strip()
    if not base:
        return ""
    candidates.append(base)
    words = [w for w in base.split() if w]
    for cut in (3, 2, 1):
        if len(words) > cut:
            shortened = " ".join(words[:cut])
            if shortened and shortened not in candidates:
                candidates.append(shortened)
    if words and words[0] not in candidates:
        candidates.append(words[0])

    from urllib.parse import quote as _q
    for variant in candidates:
        normalized_title = variant.replace(" ", "_")
        for lang_code in ("fr", "en"):
            url = f"https://{lang_code}.wikipedia.org/api/rest_v1/page/summary/{_q(normalized_title)}"
            try:
                r = requests.get(url, timeout=6, headers={"User-Agent": "AuroraIA-Bridge/1.0"})
                if r.status_code != 200:
                    continue
                data = r.json()
                extract = (data.get("extract") or "").strip()
                if extract and len(extract) >= 80:
                    return extract
            except Exception:
                continue
    return ""


def _ollama_extract_brand_profile(brand: str, wiki_extract: str) -> "dict | None":
    """Ask the local Ollama to synthesise a BrandProfile JSON for `brand`.

    Uses a fast 7B model (qwen2.5:7b) so the call returns in under 10s on a
    warm runtime — this is the live-enrich path, not a planning step.
    Returns None if the response can't be parsed; the caller then falls back
    to a generic profile.
    """
    schema_lines = [
        "Tu es un expert design des marques. Retourne UNIQUEMENT un JSON strict (pas de markdown,",
        "pas d explication) avec EXACTEMENT ces cles pour la marque demandee:",
        '{',
        '  "primaryColor": "#RRGGBB - couleur officielle de la marque",',
        '  "secondaryColor": "#RRGGBB - couleur secondaire (souvent blanc, noir, ou couleur complementaire)",',
        '  "productKeywords": ["3-5 produits ou termes emblematiques de la marque"],',
        '  "designVibe": "1 phrase courte sur le vibe visuel (ex: rouge eclatant + blanc, vintage americain pop)",',
        '  "typoVibe": "1 phrase sur la typo (ex: serif scriptural elegant + sans bold)",',
        '  "imageQueries": ["3-4 queries Wikipedia/Google pour images officielles"],',
        '  "productShape": "one of: can / bottle / phone / tablet / laptop / shoe / car / watch / bag / headphones / controller / console / card / cup / logo / building"',
        "}",
        "",
        f"Marque: {brand}",
    ]
    if wiki_extract:
        schema_lines.append("")
        schema_lines.append(f"Extrait Wikipedia: {wiki_extract[:1500]}")
    prompt = "\n".join(schema_lines)
    try:
        r = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "qwen2.5:7b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 600, "num_ctx": 4096},
                "format": "json",
            },
            timeout=45,
        )
        if r.status_code != 200:
            return None
        body = r.json()
        raw = (body.get("response") or "").strip()
        if not raw:
            return None
        # The format=json mode constrains the output to be valid JSON; just parse.
        try:
            parsed = json.loads(raw)
        except Exception:
            # Fallback — extract first JSON object substring.
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                return None
            parsed = json.loads(m.group(0))
        # Sanity: required fields must be present and not empty.
        required = ["primaryColor", "productKeywords", "designVibe", "imageQueries", "productShape"]
        for key in required:
            if not parsed.get(key):
                return None
        # Coerce types.
        if not isinstance(parsed.get("productKeywords"), list):
            return None
        if not isinstance(parsed.get("imageQueries"), list):
            return None
        # v77 — sanitise hex colors. The 7B model often appends prose to the
        # value ("#F40009 - couleur officielle de la marque"). Strip
        # everything after the hex and reject if no valid hex was found.
        for color_key in ("primaryColor", "secondaryColor", "tertiaryColor"):
            raw_color = parsed.get(color_key)
            if not raw_color or not isinstance(raw_color, str):
                continue
            m = re.search(r"#([0-9a-fA-F]{6})\b", raw_color)
            if m:
                parsed[color_key] = "#" + m.group(1).upper()
            else:
                # No valid hex — drop the field rather than passing junk.
                if color_key == "primaryColor":
                    return None  # primary is required
                parsed.pop(color_key, None)
        # productShape must be one of the 16 allowed values.
        valid_shapes = {
            "can", "bottle", "phone", "tablet", "laptop",
            "shoe", "car", "watch", "bag", "headphones",
            "controller", "console", "card", "cup", "logo", "building",
        }
        if parsed.get("productShape") not in valid_shapes:
            parsed["productShape"] = "logo"
        return parsed
    except Exception:
        return None


# v77g — file-based LRU cache for brand enrichment.
# The 7B + Wikipedia round-trip costs 5-10s per call; the same brand is
# routinely re-asked across user sessions (every "Coca-Cola" prompt).
# A simple JSON cache cuts the latency to ~2ms on hit, and 7 days TTL is
# plenty since brand colors / product shapes don't change often.
_BRAND_CACHE_FILE = pathlib.Path(WORKSPACE) / "bridge_state" / "brand_enrich_cache.json"
_BRAND_CACHE_TTL_S = 7 * 24 * 3600  # 7 days
_BRAND_CACHE_MAX_ENTRIES = 200
_BRAND_CACHE_LOCK = threading.Lock()


def _brand_cache_load() -> dict:
    try:
        if not _BRAND_CACHE_FILE.exists():
            return {}
        with open(_BRAND_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _brand_cache_save(cache: dict) -> None:
    try:
        _BRAND_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write — temp + rename. Avoids corruption on crash mid-write.
        tmp = _BRAND_CACHE_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        tmp.replace(_BRAND_CACHE_FILE)
    except Exception as exc:
        print(f"[brand cache] save failed: {exc}", flush=True)


def _brand_cache_get(brand: str) -> "dict | None":
    """Return cached profile + metadata if hit and fresh; None otherwise."""
    key = brand.lower().strip()
    if not key:
        return None
    with _BRAND_CACHE_LOCK:
        cache = _brand_cache_load()
        entry = cache.get(key)
        if not entry:
            return None
        ts = entry.get("ts", 0)
        if not isinstance(ts, (int, float)):
            return None
        if (_time.time() - ts) > _BRAND_CACHE_TTL_S:
            return None
        return entry


def _brand_cache_put(brand: str, payload: dict) -> None:
    """Store the enriched payload + timestamp. Evicts oldest entries past max."""
    key = brand.lower().strip()
    if not key:
        return
    with _BRAND_CACHE_LOCK:
        cache = _brand_cache_load()
        cache[key] = {**payload, "ts": _time.time()}
        # Evict oldest if past the cap. Sort by ts ascending and drop the head.
        if len(cache) > _BRAND_CACHE_MAX_ENTRIES:
            sorted_items = sorted(
                cache.items(),
                key=lambda kv: kv[1].get("ts", 0) if isinstance(kv[1], dict) else 0,
            )
            keep = sorted_items[-_BRAND_CACHE_MAX_ENTRIES:]
            cache = dict(keep)
        _brand_cache_save(cache)


@web_search_bp.route("/api/brand/enrich", methods=["POST"])
def brand_enrich():
    """Dynamically build a BrandProfile for an arbitrary brand name.

    The TS pipeline has a fast in-memory dictionary of ~47 well-known brands
    (Coca-Cola, Tesla, iPhone, etc.) but the user can prompt about any brand.
    This endpoint covers the long tail: it asks Wikipedia for the summary
    text, then asks Ollama (fast 7B) to extract a structured profile.

    v77d — override the LLM-guessed primary color with the dominant color
    extracted from the Wikipedia logo when available.
    v77g — file-based LRU cache (7 days TTL, 200 entries max) — turns the
    second call to the same brand into a ~2ms lookup instead of a 5-10s
    round-trip.

    Request: {"brand": "Lipton", "noCache": false}
      noCache: optional boolean. When true, bypass the cache and force a
      fresh enrichment (useful when the user wants to refresh stale data).

    Response on success:
      {
        "ok": true,
        "brand": "Lipton",
        "cached": false,
        "wikiAvailable": true,
        "colorSource": "wikipedia_logo_dominant",
        "profile": { primaryColor, secondaryColor, productKeywords[], ... }
      }
    """
    data = request.get_json(silent=True) or {}
    brand = (data.get("brand") or "").strip()
    no_cache = bool(data.get("noCache"))
    if not brand:
        return jsonify({"ok": False, "error": "brand required"}), 400
    if len(brand) > 80:
        return jsonify({"ok": False, "error": "brand too long"}), 400

    # Cache hit fast path.
    if not no_cache:
        cached = _brand_cache_get(brand)
        if cached and cached.get("profile"):
            return jsonify({
                "ok": True,
                "brand": brand,
                "cached": True,
                "cachedAtTs": cached.get("ts"),
                "wikiAvailable": cached.get("wikiAvailable", False),
                "colorSource": cached.get("colorSource", "unknown"),
                "profile": cached["profile"],
            })

    wiki_extract = _wikipedia_summary_text(brand)
    profile = _ollama_extract_brand_profile(brand, wiki_extract)
    if not profile:
        return jsonify({
            "ok": False,
            "error": "could not synthesise profile (ollama parse failed)",
            "wikiAvailable": bool(wiki_extract),
        }), 502

    # v77d — override the LLM-guessed primary color with the dominant color
    # extracted from the Wikipedia logo when available. This catches cases
    # where the 7B model hallucinates a wrong hex (Heineken -> bleu #003F5C
    # instead of the real green #00A651). The dominant-color extraction
    # operates on actual pixels so it's canonical by construction.
    color_source = "ollama_guess"
    logo_attempt = _wikipedia_thumbnail(brand)
    if logo_attempt:
        _logo_url, logo_bytes, _logo_ctype = logo_attempt
        dominant = _extract_dominant_color(logo_bytes)
        if dominant:
            profile["primaryColor"] = dominant
            color_source = "wikipedia_logo_dominant"

    response_payload = {
        "wikiAvailable": bool(wiki_extract),
        "colorSource": color_source,
        "profile": profile,
    }

    # Persist to cache for the next call.
    _brand_cache_put(brand, response_payload)

    return jsonify({
        "ok": True,
        "brand": brand,
        "cached": False,
        **response_payload,
    })


@web_search_bp.route("/api/web/image", methods=["POST"])
def web_image_single():
    """Telecharge UNE image pertinente pour un sujet et retourne un data URL.

    Used by the Code module so the generated HTML references a
    <img src="data:..."> that never 404s after the project is saved anywhere
    on disk.

    Sources probed in order (v72 — brand fidelity, WS15 sans Unsplash mort):
      1. Wikipedia REST API thumbnail (best for brands / named products / people)
      2. DuckDuckGo Images i.js (real image search, brand-aware)
      3. LoremFlickr (generic tagged photo)
      4. Picsum (truly random — last resort)

    The first three sources return ACTUAL brand images when the query mentions
    one. Picsum-only output was the root cause of "Coca-Cola → random photo"
    drift in the Code module landing pages.

    Each candidate has its own short timeout so we never block more than ~45 s.
    """
    import base64 as _b64
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    width = int(data.get("width") or 1600)
    height = int(data.get("height") or 900)
    if not query:
        return jsonify({"ok": False, "error": "query required"}), 400

    last_error = ""

    # 1) Wikipedia thumbnail — most brand-faithful free source.
    wiki = _wikipedia_thumbnail(query)
    if wiki:
        url, content, ctype = wiki
        b64 = _b64.b64encode(content).decode("ascii")
        return jsonify({
            "ok": True,
            "dataUrl": f"data:{ctype};base64,{b64}",
            "source": url,
            "bytes": len(content),
            "via": "wikipedia",
        })

    # 2) DuckDuckGo Images — real search results.
    ddg = _duckduckgo_image(query)
    if ddg:
        url, content, ctype = ddg
        b64 = _b64.b64encode(content).decode("ascii")
        return jsonify({
            "ok": True,
            "dataUrl": f"data:{ctype};base64,{b64}",
            "source": url,
            "bytes": len(content),
            "via": "duckduckgo",
        })

    # 3-4) Generic photo fallbacks. Unsplash Source is intentionally absent:
    # the endpoint is deprecated/unreliable and must not appear in Code output.
    from urllib.parse import quote
    q_encoded = quote(query)
    candidates = [
        ("loremflickr", f"https://loremflickr.com/{width}/{height}/{q_encoded}"),
        ("picsum", f"https://picsum.photos/seed/{q_encoded}/{width}/{height}"),
    ]
    for via, url in candidates:
        try:
            r = requests.get(url, timeout=12, allow_redirects=True)
            if r.status_code != 200:
                last_error = f"{url}: HTTP {r.status_code}"
                continue
            ctype = r.headers.get("Content-Type", "").split(";")[0].strip() or "image/jpeg"
            if not ctype.startswith("image/"):
                last_error = f"{url}: content-type {ctype}"
                continue
            content = r.content
            if len(content) < 2000:
                last_error = f"{url}: payload too small ({len(content)} bytes)"
                continue
            b64 = _b64.b64encode(content).decode("ascii")
            data_url = f"data:{ctype};base64,{b64}"
            return jsonify({
                "ok": True,
                "dataUrl": data_url,
                "source": url,
                "bytes": len(content),
                "via": via,
            })
        except Exception as e:
            last_error = f"{url}: {e}"
    return jsonify({"ok": False, "error": last_error or "no image source available"}), 504


