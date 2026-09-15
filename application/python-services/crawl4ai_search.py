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
import time
import html as html_module
import urllib.parse
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
#  Auto-install Crawl4AI + Playwright si absent
# ---------------------------------------------------------------------------

def _legacy_api_present() -> bool:
    """crawl4ai expose-t-il encore l'API synchrone `WebCrawler` ?

    C'est le symbole que tout ce fichier utilise. Les versions recentes de
    crawl4ai l'ont retire au profit de `AsyncWebCrawler` : le paquet
    s'importe donc parfaitement alors que `from crawl4ai import WebCrawler`
    echoue. Tester la presence du paquet ne disait rien d'utile.
    """
    try:
        from crawl4ai import WebCrawler  # noqa: F401
        return True
    except Exception:
        return False


def ensure_crawl4ai() -> bool:
    """Vrai seulement si l'API réellement utilisée ici est disponible.

    Renvoyer True sur la seule presence du paquet faisait echouer chaque
    extraction de page : `extract_page` partait sur la voie crawl4ai, prenait
    un ImportError, et renvoyait `{"ok": false}` sans jamais essayer le repli
    HTTP qui, lui, marche. Une recherche annoncait donc des sources qu'elle
    n'avait jamais ouvertes.
    """
    if _legacy_api_present():
        return True
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
        return _legacy_api_present()
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


BOILERPLATE_BLOCKS = ("script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg", "template")


def html_to_text(raw_html: str) -> str:
    """HTML -> texte lisible, sans le mobilier de la page.

    Le nettoyage precedent enlevait seulement <script> et <style>, puis
    aplatissait le reste. Sur un article Wikipedia, les 400 premiers
    caracteres etaient donc « Aller au contenu / Menu principal / Faire un
    don » — et comme le contexte envoye au modele est tronque, la moitie de
    ce qu'il lisait etait un menu. On coupe d'abord le mobilier, et on garde
    <main> ou <article> quand la page en declare un.
    """
    text = raw_html
    for tag in BOILERPLATE_BLOCKS:
        text = re.sub(rf"<{tag}\b[\s\S]*?</{tag}>", " ", text, flags=re.I)

    # Corps principal si la page le declare : c'est la que vit l'article.
    for tag in ("article", "main"):
        blocks = re.findall(rf"<{tag}\b[^>]*>([\s\S]*?)</{tag}>", text, re.I)
        if blocks:
            candidate = max(blocks, key=len)
            if len(candidate) > 600:
                text = candidate
                break

    # Les sauts de bloc deviennent des sauts de ligne : sans ca, titres,
    # paragraphes et cellules de tableau se collent en une seule phrase.
    text = re.sub(r"</(p|div|li|tr|h[1-6]|section|blockquote)>", "\n", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    # Restes de wikitexte et de JSON embarque : certaines pages exposent
    # leur source dans un attribut, qui ressort en bouillie apres le
    # deshabillage des balises. Ce n'est pas du contenu, ca fait du bruit
    # dans le contexte envoye au modele.
    text = re.sub(r"\{\{[\s\S]{0,600}?\}\}", " ", text)
    text = re.sub(r"\[\[(?:File|Fichier|Image):[\s\S]{0,400}?\]\]", " ", text, flags=re.I)
    text = re.sub(r"<ref[\s\S]{0,600}?</ref>", " ", text, flags=re.I)

    lines = [line.strip() for line in text.split("\n")]
    kept = [
        line for line in lines
        if len(line) > 1
        # Une ligne saturee d'accolades et de guillemets est un fragment de
        # JSON, pas une phrase.
        and (len(line) < 40 or (line.count('"') + line.count('{') + line.count('}')) / len(line) < 0.08)
    ]
    return "\n".join(kept).strip()


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
        except Exception:
            # On NE sort PAS ici : le repli urllib plus bas sait lire la
            # page. Sortir sur `{"ok": false}` rendait toute lecture de page
            # impossible des que crawl4ai etait installe.
            pass

    # Fallback: urllib
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read(500_000).decode("utf-8", errors="replace")
        title_match = re.search(r"<title[^>]*>([\s\S]{0,300}?)</title>", data, re.I)
        title = html_module.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip() if title_match else ""
        return {"ok": True, "title": title, "markdown": html_to_text(data)[:8000], "links": []}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _json_api(url: str, timeout: int = 15, attempts: int = 2) -> dict:
    """GET une API JSON publique. Renvoie {} en cas d'echec.

    Une seule tentative ne suffit pas : Wikipedia et Commons repondent
    regulierement 503 sous charge, et un 503 passager faisait retomber toute
    la recherche a zero resultat — donc la conversation sur la memoire du
    modele, sans le dire. Deux essais espaces d'une demi-seconde absorbent
    l'essentiel de ces creux.
    """
    last: dict = {}
    for attempt in range(max(1, attempts)):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "AuroraIA/2.0 (assistant personnel; recherche documentaire)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read(2_000_000).decode("utf-8", errors="replace"))
        except Exception:
            if attempt + 1 < max(1, attempts):
                time.sleep(0.6)
    return last


def _images_wikimedia(query: str, limit: int) -> list[dict]:
    """Photos de Wikimedia Commons.

    API stable, sans cle, sans cookie, avec la page d'origine et la licence.
    C'est la source la plus fiable pour un sujet nomme (monument, espece,
    personnalite, objet) : le grattage d'un moteur d'images renvoyait surtout
    des vignettes de 90 px ou des pixels de tracking.
    """
    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        "&generator=search&gsrnamespace=6&gsrsearch=" + urllib.parse.quote_plus(query)
        + f"&gsrlimit={max(1, min(20, limit))}"
        "&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=1024"
    )
    data = _json_api(url)
    pages = (data.get("query") or {}).get("pages") or {}
    out: list[dict] = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        full = info.get("url") or ""
        thumb = info.get("thumburl") or full
        if not full.startswith("http"):
            continue
        # Les SVG et les icones ne sont pas des photos.
        if full.lower().endswith((".svg", ".ogv", ".webm", ".ogg")):
            continue
        meta = info.get("extmetadata") or {}
        license_name = (meta.get("LicenseShortName") or {}).get("value") or ""
        out.append({
            "url": full,
            "thumb": thumb,
            "alt": re.sub(r"^File:|\.[A-Za-z0-9]+$", "", page.get("title", "")).strip(),
            "sourcePage": info.get("descriptionurl") or "",
            "license": license_name,
            "width": info.get("width") or 0,
            "height": info.get("height") or 0,
            "provider": "wikimedia",
        })
        if len(out) >= limit:
            break
    return out


def _images_openverse(query: str, limit: int) -> list[dict]:
    """Photos Openverse (Creative Commons, agrege Flickr/Smithsonian/etc.)."""
    url = (
        "https://api.openverse.org/v1/images/?q=" + urllib.parse.quote_plus(query)
        + f"&page_size={max(1, min(20, limit))}"
    )
    data = _json_api(url)
    out: list[dict] = []
    for row in data.get("results", []) or []:
        full = row.get("url") or ""
        if not full.startswith("http"):
            continue
        out.append({
            "url": full,
            "thumb": row.get("thumbnail") or full,
            "alt": row.get("title") or "",
            "sourcePage": row.get("foreign_landing_url") or "",
            "license": (row.get("license") or "").upper(),
            "width": row.get("width") or 0,
            "height": row.get("height") or 0,
            "provider": "openverse",
        })
        if len(out) >= limit:
            break
    return out


def _query_variants(query: str) -> list[str]:
    """La requete, puis des versions de plus en plus courtes.

    Une banque d'images cherche un SUJET, pas une question. « tour eiffel
    hauteur exacte » ne correspond a aucun fichier de Commons alors que
    « tour eiffel » en donne des centaines. On raccourcit donc par la fin
    jusqu'a obtenir quelque chose, au lieu de rendre une liste vide.
    """
    base = " ".join((query or "").split())
    if not base:
        return []
    variants = [base]
    words = base.split()
    for cut in (3, 2, 1):
        if len(words) > cut:
            shortened = " ".join(words[:cut])
            if shortened not in variants:
                variants.append(shortened)
    return variants


def search_images(query: str, limit: int = 6) -> list[dict]:
    """Photos affichables pour une requete.

    Ordre : Wikimedia Commons, puis Openverse, puis Crawl4AI/Google Images,
    puis grattage des og:image des pages de resultats. Les deux premieres
    sources sont des API declarees : elles rendent l'URL pleine resolution,
    la page d'origine et la licence, ce que le grattage ne donnait jamais.
    Elles sont aussi les seules a repondre quand Playwright n'est pas installe
    — ce qui etait le cas ici, d'ou une recherche d'images qui renvoyait
    toujours une liste vide.
    """
    images: list[dict] = []
    seen: set[str] = set()

    for provider in (_images_wikimedia, _images_openverse):
        for variant in _query_variants(query):
            try:
                rows = provider(variant, limit)
            except Exception:
                continue
            for row in rows:
                if row["url"] in seen:
                    continue
                seen.add(row["url"])
                images.append(row)
            if images:
                break
        if len(images) >= limit:
            return images[:limit]

    has_crawl4ai = ensure_crawl4ai()

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
                        if src in seen:
                            continue
                        seen.add(src)
                        images.append({
                            "url": src,
                            "thumb": src,
                            "alt": img.get("alt", ""),
                            "sourcePage": "",
                            "license": "",
                            "provider": "crawl4ai",
                        })
            if images:
                return images[:limit]
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
                    if img_url in seen:
                        continue
                    seen.add(img_url)
                    images.append({
                        "url": img_url,
                        "thumb": img_url,
                        "alt": sr.get("title", ""),
                        "sourcePage": sr["url"],
                        "license": "",
                        "provider": "page",
                    })
                    if len(images) >= limit:
                        break
        except Exception:
            continue
        if len(images) >= limit:
            break

    return images[:limit]


def search_wikipedia(query: str, limit: int = 5) -> list[dict]:
    """Recherche encyclopedique via l'API REST de Wikipedia (fr puis en).

    Filet de securite : le grattage HTML de DuckDuckGo se fait couper des
    qu'on enchaine quelques requetes — il repond alors une page « Please
    complete the following challenge », soit zero resultat. Une recherche qui
    ne renvoie rien fait retomber la conversation sur la memoire du modele,
    c'est-a-dire exactement ce qu'on essaie d'eviter. L'API de Wikipedia n'a
    ni cle, ni cookie, ni captcha, et repond sur la grande majorite des
    sujets factuels.
    """
    out: list[dict] = []
    # Meme raccourcissement que pour les images : une encyclopedie cherche un
    # sujet. « tour eiffel hauteur exacte » ne correspond a aucun article,
    # « tour eiffel » si.
    attempts = [(base, variant)
                for base in ("https://fr.wikipedia.org", "https://en.wikipedia.org")
                for variant in _query_variants(query)]
    for base, variant in attempts:
        url = f"{base}/w/rest.php/v1/search/page?limit={max(1, min(20, limit))}&q=" + urllib.parse.quote_plus(variant)
        data = _json_api(url)
        for page in data.get("pages", []) or []:
            key = page.get("key") or ""
            if not key:
                continue
            excerpt = re.sub(r"<[^>]+>", "", html_module.unescape(page.get("excerpt") or ""))
            description = page.get("description") or ""
            out.append({
                "title": page.get("title") or key.replace("_", " "),
                "url": f"{base}/wiki/" + urllib.parse.quote(key),
                "snippet": (description or excerpt).strip(),
            })
            if len(out) >= limit:
                return out
        if out:
            return out
    return out


def do_search(query: str, limit: int) -> dict[str, Any]:
    """Recherche : Crawl4AI, puis grattage HTML, puis Wikipedia.

    Les trois etages sont cumulables : si le grattage ne remonte que deux
    liens, on complete avec Wikipedia plutot que de rendre une liste courte.
    """
    has_crawl4ai = ensure_crawl4ai()

    if has_crawl4ai:
        try:
            results = search_with_crawl4ai(query, limit)
            if results:
                return {"ok": True, "engine": "crawl4ai", "results": results}
        except Exception:
            pass

    results = search_fallback(query, limit)
    engine = "fallback"

    if len(results) < limit:
        seen = {r.get("url") for r in results}
        added = 0
        try:
            for row in search_wikipedia(query, limit - len(results)):
                if row["url"] in seen:
                    continue
                seen.add(row["url"])
                results.append(row)
                added += 1
        except Exception:
            pass
        if added:
            engine = "wikipedia" if added == len(results) else "fallback+wikipedia"

    return {"ok": bool(results), "engine": engine, "results": results}


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
