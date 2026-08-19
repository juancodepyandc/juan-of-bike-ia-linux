"""
Native web search helper for 3D reference discovery.

Modes:
  python reference_visual_search.py --query "Lian Li Strimer Plus v2" --limit 6
  python reference_visual_search.py --download-url "https://example.com/image.png"
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36 AuroraIA/2.0"
)
SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/?q={query}"
# Endpoint ASYNC de Bing Images : c'est celui que le JS de la page appelle. Il
# renvoie les metadonnees image (m="{...murl...}") DIRECTEMENT dans le HTML, alors
# que /images/search ne les charge qu'en JS (le scrape n'y trouvait que des ancres
# parasites hors-sujet). Indispensable pour des sujets de niche (personnages, etc.).
BING_IMAGES_ENDPOINT = "https://www.bing.com/images/async?q={query}&first=1&count=35&mmasync=1"
MAX_HTML_BYTES = 650_000
MAX_IMAGE_BYTES = 8_500_000

RESULT_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE,
)
META_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image|twitter:image:src)["\'][^>]+content=["\'](?P<url>[^"\']+)["\']',
    re.IGNORECASE,
)
LINK_IMAGE_RE = re.compile(
    r'<link[^>]+rel=["\'](?:image_src|preload)["\'][^>]+href=["\'](?P<url>[^"\']+)["\']',
    re.IGNORECASE,
)
TITLE_RE = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](?P<title>[^"\']+)["\']',
    re.IGNORECASE,
)
IMG_TAG_RE = re.compile(
    r'<img[^>]+(?:src|data-src)=["\'](?P<url>[^"\']+)["\']',
    re.IGNORECASE,
)
JSON_LD_IMAGE_RE = re.compile(
    r'"image"\s*:\s*(?P<value>\[[^\]]+\]|"[^"]+")',
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search or download visual references")
    parser.add_argument("--query", help="Search query for web reference pages")
    parser.add_argument("--limit", type=int, default=6, help="Max page results to inspect")
    parser.add_argument("--download-url", help="Direct image URL to download")
    return parser.parse_args()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def request_bytes(url: str, max_bytes: int, accept: str = "*/*") -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        content_type = response.headers.get("Content-Type", "")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise RuntimeError(f"Payload too large for {url}")
        return data, content_type


def decode_text(data: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset=([a-zA-Z0-9_\-]+)", content_type)
    if match:
        charset = match.group(1)
    try:
        return data.decode(charset, errors="replace")
    except Exception:
        return data.decode("utf-8", errors="replace")


def normalize_result_url(href: str) -> str | None:
    raw = html.unescape(href)
    if raw.startswith("//"):
        raw = f"https:{raw}"
    if raw.startswith("/l/?") or "duckduckgo.com/l/?" in raw:
        parsed = urllib.parse.urlparse(raw if raw.startswith("http") else f"https://html.duckduckgo.com{raw}")
        uddg = urllib.parse.parse_qs(parsed.query).get("uddg", [None])[0]
        if uddg:
            return urllib.parse.unquote(uddg)
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return None


def search_duckduckgo(query: str, limit: int) -> list[dict]:
    try:
        url = SEARCH_ENDPOINT.format(query=urllib.parse.quote_plus(query))
        data, content_type = request_bytes(url, MAX_HTML_BYTES, accept="text/html,application/xhtml+xml")
        html_text = decode_text(data, content_type)
    except Exception:
        return []

    seen: set[str] = set()
    results: list[dict] = []
    for match in RESULT_LINK_RE.finditer(html_text):
        page_url = normalize_result_url(match.group("href"))
        if not page_url or page_url in seen:
            continue
        seen.add(page_url)
        results.append({
            "title": clean_text(match.group("title")),
            "pageUrl": page_url,
        })
        if len(results) >= limit:
            break

    return results


def looks_like_real_image(url: str) -> bool:
    lowered = url.lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    if any(marker in lowered for marker in [
        ".svg",
        "logo",
        "sprite",
        "avatar",
        "icon",
        "favicon",
        "blank.gif",
        "tracking",
        "pixel.",
        "data:image",
        "thumb-120",
        "thumb-150",
        "thumb-200",
        "thumb-300",
        "thumb-440",
        "thumb-480",
        "100x100",
        "120x120",
        "150x150",
        "180x180",
        "200x200",
        "240x240",
        "thumbnail",
        "wallpaper-thumb",
    ]):
        return False
    return True


def extract_json_ld_images(html_text: str, base_url: str) -> list[str]:
    output: list[str] = []
    for match in JSON_LD_IMAGE_RE.finditer(html_text):
        value = match.group("value").strip()
        candidates: list[str] = []
        if value.startswith("["):
            candidates.extend(re.findall(r'"([^"]+)"', value))
        else:
            candidates.append(value.strip('"'))
        for candidate in candidates:
            normalized = urllib.parse.urljoin(base_url, html.unescape(candidate))
            if looks_like_real_image(normalized):
                output.append(normalized)
    return output


def unique_urls(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def inspect_page(result: dict) -> list[dict]:
    page_url = result["pageUrl"]
    try:
      data, content_type = request_bytes(page_url, MAX_HTML_BYTES, accept="text/html,application/xhtml+xml")
      html_text = decode_text(data, content_type)
    except Exception:
      return []

    title_match = OG_TITLE_RE.search(html_text) or TITLE_RE.search(html_text)
    page_title = clean_text(title_match.group("title")) if title_match else result["title"]

    candidates = [
        urllib.parse.urljoin(page_url, html.unescape(match.group("url")))
        for match in META_IMAGE_RE.finditer(html_text)
    ]
    candidates.extend(
        urllib.parse.urljoin(page_url, html.unescape(match.group("url")))
        for match in LINK_IMAGE_RE.finditer(html_text)
    )
    candidates.extend(extract_json_ld_images(html_text, page_url))
    candidates.extend(
        urllib.parse.urljoin(page_url, html.unescape(match.group("url")))
        for match in IMG_TAG_RE.finditer(html_text)
    )

    output: list[dict] = []
    for image_url in unique_urls(candidates):
        if not looks_like_real_image(image_url):
            continue
        output.append({
            "title": page_title or result["title"],
            "pageUrl": page_url,
            "imageUrl": image_url,
            "width": 0,
            "height": 0,
        })
        if len(output) >= 3:
            break

    return output


def download_image(url: str) -> dict:
    data, content_type = request_bytes(url, MAX_IMAGE_BYTES, accept="image/*,*/*;q=0.8")
    return {
        "ok": True,
        "contentType": content_type or "application/octet-stream",
        "base64": base64.b64encode(data).decode("ascii"),
    }


def search_via_crawl4ai(query: str, limit: int) -> list[dict]:
    """Try Crawl4AI image search first for better results."""
    try:
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "crawl4ai_search.py")
        result = subprocess.run(
            [sys.executable, script, "--mode", "images", "--query", query, "--limit", str(limit)],
            capture_output=True, timeout=25, cwd=os.path.dirname(__file__),
        )
        if result.returncode == 0:
            data = json.loads(result.stdout.decode("utf-8", errors="replace"))
            if data.get("ok") and data.get("images"):
                return [
                    {
                        "title": img.get("alt", query),
                        "pageUrl": "",
                        "imageUrl": img["url"],
                        "width": 0,
                        "height": 0,
                        "query": query,
                    }
                    for img in data["images"]
                ]
    except Exception:
        pass
    return []


def search_bing_images(query: str, limit: int) -> list[dict]:
    """Fallback image search using Bing's public image result metadata."""
    try:
        url = BING_IMAGES_ENDPOINT.format(query=urllib.parse.quote_plus(query))
        data, content_type = request_bytes(url, MAX_HTML_BYTES, accept="text/html,application/xhtml+xml")
        html_text = decode_text(data, content_type)
    except Exception:
        return []

    output: list[dict] = []
    seen: set[str] = set()
    # Bing stores image metadata inside escaped JSON on result anchors, usually
    # as m="{&quot;murl&quot;:&quot;...&quot;,&quot;purl&quot;:&quot;...&quot;}".
    for raw_meta in re.findall(r'\bm=["\'](?P<meta>\{.*?\})["\']', html_text, flags=re.IGNORECASE):
        try:
            meta = json.loads(html.unescape(raw_meta))
        except Exception:
            continue
        image_url = str(meta.get("murl") or meta.get("turl") or "").strip()
        if not looks_like_real_image(image_url) or image_url in seen:
            continue
        seen.add(image_url)
        output.append({
            "title": clean_text(str(meta.get("t") or meta.get("desc") or query)),
            "pageUrl": str(meta.get("purl") or meta.get("surl") or ""),
            "imageUrl": image_url,
            "width": int(meta.get("ow") or meta.get("w") or 0),
            "height": int(meta.get("oh") or meta.get("h") or 0),
            "query": query,
        })
        if len(output) >= limit:
            break

    # Defensive second pass for pages where the metadata has been serialized
    # outside the m="..." attribute.
    if len(output) < limit:
        unescaped = html.unescape(html_text)
        for match in re.finditer(r'"murl"\s*:\s*"(?P<url>https?:\/\/[^"]+)"', unescaped):
            image_url = match.group("url").replace("\\/", "/")
            if not looks_like_real_image(image_url) or image_url in seen:
                continue
            seen.add(image_url)
            output.append({
                "title": query,
                "pageUrl": "",
                "imageUrl": image_url,
                "width": 0,
                "height": 0,
                "query": query,
            })
            if len(output) >= limit:
                break

    return output


def main() -> int:
    args = parse_args()

    try:
        if args.download_url:
            print(json.dumps(download_image(args.download_url)))
            return 0

        if not args.query:
            print(json.dumps({"ok": False, "error": "Missing --query"}))
            return 1

        # Essayer Crawl4AI d'abord (Playwright, meilleur rendu JS)
        crawl_candidates = search_via_crawl4ai(args.query, max(3, args.limit))
        if crawl_candidates:
            print(json.dumps({"ok": True, "candidates": crawl_candidates, "engine": "crawl4ai"}))
            return 0

        # Fallback direct images: useful when generic web result pages do not
        # expose OG images or DuckDuckGo HTML returns sparse markup.
        bing_candidates = search_bing_images(args.query, max(3, args.limit))
        if bing_candidates:
            print(json.dumps({"ok": True, "candidates": bing_candidates, "engine": "bing-images"}))
            return 0

        # Fallback: DuckDuckGo HTML scrape classique
        search_results = search_duckduckgo(args.query, max(1, min(args.limit, 8)))
        candidates: list[dict] = []
        seen: set[str] = set()
        for result in search_results:
            for candidate in inspect_page(result):
                dedupe_key = f"{candidate['pageUrl']}::{candidate['imageUrl']}"
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                candidates.append(candidate | {"query": args.query})
                if len(candidates) >= max(3, args.limit):
                    break
            if len(candidates) >= max(3, args.limit):
                break

        print(json.dumps({"ok": True, "candidates": candidates, "engine": "duckduckgo"}))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
