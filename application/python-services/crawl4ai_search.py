"""
Crawl4AI-based web search and content extraction.
Replaces DuckDuckGo HTML scraping with proper JS-rendered crawling via Playwright.

Usage:
  python crawl4ai_search.py --mode search --query "machine learning tutorial" --limit 8
  python crawl4ai_search.py --mode extract --url "https://example.com" --prompt "résumé principal"
  python crawl4ai_search.py --mode images --query "cat face reference" --limit 6

Falls back to lightweight HTTP if Crawl4AI/Playwright is not installed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import html as html_module
import urllib.parse
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
#  Auto-install Crawl4AI + Playwright si absent
# ---------------------------------------------------------------------------

def ensure_crawl4ai() -> bool:
    """Install crawl4ai and playwright if missing. Returns True if available."""
    try:
        import crawl4ai  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "crawl4ai[sync]", "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Install playwright browsers
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
#  Crawl4AI search engine
# ---------------------------------------------------------------------------

SEARCH_ENGINES = [
    "https://www.google.com/search?q={query}&num={limit}",
    "https://search.brave.com/search?q={query}",
    "https://html.duckduckgo.com/html/?q={query}",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)


def search_with_crawl4ai(query: str, limit: int = 8) -> list[dict]:
    """Search using Crawl4AI with Playwright for JS-rendered results."""
    from crawl4ai import WebCrawler
    from crawl4ai.extraction_strategy import LLMExtractionStrategy, NoExtractionStrategy

    crawler = WebCrawler(verbose=False)
    crawler.warmup()

    results: list[dict] = []

    # Try Google first, then Brave, then DuckDuckGo
    for engine_url in SEARCH_ENGINES:
        url = engine_url.format(
            query=urllib.parse.quote_plus(query),
            limit=limit,
        )
        try:
            result = crawler.run(
                url=url,
                extraction_strategy=NoExtractionStrategy(),
                bypass_cache=True,
                word_count_threshold=10,
            )
            if not result.success:
                continue

            md = result.markdown or ""
            # Parse markdown links from results
            link_re = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')
            for match in link_re.finditer(md):
                title = match.group(1).strip()
                href = match.group(2).strip()
                # Filter out search engine internal links
                if any(d in href for d in ['google.com/search', 'brave.com/search', 'duckduckgo.com']):
                    continue
                if len(title) < 5:
                    continue
                results.append({"title": title, "url": href})
                if len(results) >= limit:
                    break

            if results:
                break
        except Exception:
            continue

    return results


def search_fallback(query: str, limit: int = 8) -> list[dict]:
    """Fallback: Google HTML scrape without Playwright."""
    results: list[dict] = []
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read(500_000).decode("utf-8", errors="replace")

        # Extract snippets and links
        snippet_re = re.compile(
            r'class="result__snippet"[^>]*>([\s\S]*?)</a>',
            re.IGNORECASE,
        )
        link_re = re.compile(
            r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            re.IGNORECASE,
        )

        for m in link_re.finditer(data):
            href = html_module.unescape(m.group(1))
            title = re.sub(r'<[^>]+>', '', html_module.unescape(m.group(2))).strip()
            # Resolve DuckDuckGo redirect URLs
            if '/l/?' in href or 'uddg=' in href:
                parsed = urllib.parse.urlparse(href if href.startswith('http') else f'https://html.duckduckgo.com{href}')
                uddg = urllib.parse.parse_qs(parsed.query).get('uddg', [None])[0]
                if uddg:
                    href = urllib.parse.unquote(uddg)
            if not href.startswith('http'):
                continue
            results.append({"title": title or href, "url": href})
            if len(results) >= limit:
                break

        snippets: list[str] = []
        for m in snippet_re.finditer(data):
            clean = re.sub(r'<[^>]+>', '', html_module.unescape(m.group(1))).strip()
            if len(clean) > 30:
                snippets.append(clean)

        # Enrich results with snippets
        for i, s in enumerate(snippets):
            if i < len(results):
                results[i]["snippet"] = s

    except Exception:
        pass
    return results


def extract_page(url: str, prompt: str = "") -> dict:
    """Extract content from a URL using Crawl4AI."""
    has_crawl4ai = ensure_crawl4ai()
    if has_crawl4ai:
        try:
            from crawl4ai import WebCrawler
            from crawl4ai.extraction_strategy import NoExtractionStrategy

            crawler = WebCrawler(verbose=False)
            crawler.warmup()
            result = crawler.run(
                url=url,
                extraction_strategy=NoExtractionStrategy(),
                bypass_cache=True,
            )
            if result.success:
                return {
                    "ok": True,
                    "title": result.metadata.get("title", "") if result.metadata else "",
                    "markdown": (result.markdown or "")[:8000],
                    "links": result.links[:20] if result.links else [],
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # Fallback: urllib
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read(500_000).decode("utf-8", errors="replace")
        # Basic HTML to text
        text = re.sub(r'<script[\s\S]*?</script>', '', data, flags=re.I)
        text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_module.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return {"ok": True, "title": "", "markdown": text[:8000], "links": []}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def search_images(query: str, limit: int = 6) -> list[dict]:
    """Search for images using Crawl4AI."""
    has_crawl4ai = ensure_crawl4ai()
    images: list[dict] = []

    if has_crawl4ai:
        try:
            from crawl4ai import WebCrawler
            from crawl4ai.extraction_strategy import NoExtractionStrategy

            crawler = WebCrawler(verbose=False)
            crawler.warmup()

            # Use Google Images
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}&tbm=isch"
            result = crawler.run(
                url=url,
                extraction_strategy=NoExtractionStrategy(),
                bypass_cache=True,
            )
            if result.success and result.media:
                for img in result.media.get("images", [])[:limit]:
                    src = img.get("src", "")
                    if src.startswith("http") and not any(x in src.lower() for x in [".svg", "logo", "icon", "favicon", "pixel"]):
                        images.append({
                            "url": src,
                            "alt": img.get("alt", ""),
                            "score": img.get("score", 0),
                        })
            if images:
                return images
        except Exception:
            pass

    # Fallback: DuckDuckGo image search via regular search + page inspection
    search_results = search_fallback(f"{query} image reference photo", limit=4)
    for sr in search_results:
        try:
            req = urllib.request.Request(sr["url"], headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=8) as resp:
                html_text = resp.read(300_000).decode("utf-8", errors="replace")

            img_re = re.compile(
                r'<(?:meta[^>]+(?:og:image|twitter:image)[^>]+content|img[^>]+(?:src|data-src))=["\']([^"\']+)["\']',
                re.I,
            )
            for m in img_re.finditer(html_text):
                img_url = urllib.parse.urljoin(sr["url"], html_module.unescape(m.group(1)))
                if img_url.startswith("http") and not any(x in img_url.lower() for x in [".svg", "logo", "icon", "pixel", "favicon"]):
                    images.append({"url": img_url, "alt": sr.get("title", ""), "score": 0})
                    if len(images) >= limit:
                        break
        except Exception:
            continue
        if len(images) >= limit:
            break

    return images


def do_search(query: str, limit: int) -> dict[str, Any]:
    """Main search: try Crawl4AI, fallback to HTTP scrape."""
    has_crawl4ai = ensure_crawl4ai()

    if has_crawl4ai:
        try:
            results = search_with_crawl4ai(query, limit)
            if results:
                return {"ok": True, "engine": "crawl4ai", "results": results}
        except Exception:
            pass

    # Fallback
    results = search_fallback(query, limit)
    return {"ok": bool(results), "engine": "fallback", "results": results}


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl4AI search & extraction")
    parser.add_argument("--mode", choices=["search", "extract", "images"], default="search")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--url", help="URL to extract (for mode=extract)")
    parser.add_argument("--prompt", default="", help="Extraction prompt")
    parser.add_argument("--limit", type=int, default=8, help="Max results")
    args = parser.parse_args()

    try:
        if args.mode == "search":
            if not args.query:
                print(json.dumps({"ok": False, "error": "Missing --query"}))
                return 1
            result = do_search(args.query, args.limit)
            print(json.dumps(result))

        elif args.mode == "extract":
            if not args.url:
                print(json.dumps({"ok": False, "error": "Missing --url"}))
                return 1
            result = extract_page(args.url, args.prompt)
            print(json.dumps(result))

        elif args.mode == "images":
            if not args.query:
                print(json.dumps({"ok": False, "error": "Missing --query"}))
                return 1
            images = search_images(args.query, args.limit)
            print(json.dumps({"ok": bool(images), "images": images}))

        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
