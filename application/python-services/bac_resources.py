"""bac_resources — fetch real BAC subjects from trusted French education sites.

Used by the Academy module to enrich the AI's context when generating exos /
fiches / quizzes : instead of inventing exercises from scratch, we feed the
generator actual past exam content so the output matches the real assessment
style.

Supported sources (first pass):
  - ecebac.fr                — épreuves pratiques STI2D / SVT / PC / NSI
  - sujetsdebac.fr           — annales générales (best-effort scrape)
  - lesbonsprofs.com (index) — just metadata, no scrape
  - annabac.com (index)      — just metadata
  - lumni.fr                 — public service ressources

Usage:
  python bac_resources.py --list \\
    --filiere sti2d --matiere sin --session 2026
  python bac_resources.py --subject 4076
  python bac_resources.py --discover "dérivées terminale"
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AuroraIA/1.0 (educational)"

ECEBAC_FILIERE = {
    'sti2d':  108,
    'gen':    62,
    'sthr':   100,
    'stl':    63,
    'std2a':  115,
    'stav':   113,
}
ECEBAC_MATIERE = {
    'sin':   112,
    'ac':    109,
    'ee':    110,
    'itec':  111,
    'pc':    80,    # épreuve ECE
    'svt':   81,
    'bioeco': 82,
    'nsi':   90,
}

# Catalog of trusted French BAC resources — used as prompt enrichment and as
# fallbacks when ecebac doesn't cover the requested topic.
TRUSTED_SITES = [
    {
        'name': 'ecebac.fr',
        'description': "Épreuves pratiques BAC (STI2D, PC, SVT, NSI) — sujets officiels",
        'root': 'https://ecebac.fr',
        'types': ['sti2d-sin', 'sti2d-ac', 'sti2d-ee', 'sti2d-itec', 'pc', 'svt', 'nsi'],
    },
    {
        'name': 'sujetsdebac.fr',
        'description': "Annales générales tous bacs, corrigés candidats",
        'root': 'https://www.sujetdebac.fr',
        'types': ['general', 'techno'],
    },
    {
        'name': 'freemaths.fr',
        'description': "Exercices et corrigés maths lycée (1re / Terminale)",
        'root': 'https://www.freemaths.fr',
        'types': ['maths'],
    },
    {
        'name': 'lesbonsprofs.com',
        'description': "Cours vidéo structurés niveau lycée",
        'root': 'https://www.lesbonsprofs.com',
        'types': ['general'],
    },
    {
        'name': 'annabac.com',
        'description': "Annales corrigées avec fiches de méthode",
        'root': 'https://www.annabac.com',
        'types': ['general'],
    },
    {
        'name': 'lumni.fr',
        'description': "Service public d'éducation, ressources vérifiées",
        'root': 'https://www.lumni.fr',
        'types': ['general'],
    },
    {
        'name': 'kartable.fr',
        'description': "Cours + exercices corrigés (accès freemium)",
        'root': 'https://www.kartable.fr',
        'types': ['general'],
    },
    {
        'name': 'khanacademy.fr',
        'description': "Cours + exercices gratuits, traduits en FR",
        'root': 'https://fr.khanacademy.org',
        'types': ['maths', 'sciences'],
    },
    {
        'name': 'maths-lycee.fr',
        'description': "Cours et exos maths Terminale tout spécialité",
        'root': 'https://www.maths-lycee.fr',
        'types': ['maths'],
    },
    {
        'name': 'nsi.lesalgos.net',
        'description': "Cours NSI (informatique lycée) open-source",
        'root': 'https://nsi.lesalgos.net',
        'types': ['nsi'],
    },
]


def fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return raw.decode('utf-8', errors='replace')


def strip_html(html: str, max_chars: int = 8000) -> str:
    """Collapse HTML to plain text for prompt injection. Not perfect, good enough."""
    html = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.I)
    html = re.sub(r'<style[\s\S]*?</style>', ' ', html, flags=re.I)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'&nbsp;', ' ', html)
    html = re.sub(r'&amp;', '&', html)
    html = re.sub(r'&lt;', '<', html)
    html = re.sub(r'&gt;', '>', html)
    html = re.sub(r'&eacute;', 'é', html)
    html = re.sub(r'&egrave;', 'è', html)
    html = re.sub(r'&agrave;', 'à', html)
    html = re.sub(r'&ocirc;', 'ô', html)
    html = re.sub(r'&ecirc;', 'ê', html)
    html = re.sub(r'&acirc;', 'â', html)
    html = re.sub(r'&ugrave;', 'ù', html)
    html = re.sub(r'&ccedil;', 'ç', html)
    html = re.sub(r'&[a-z]+;', ' ', html)
    html = re.sub(r'\s+', ' ', html).strip()
    return html[:max_chars]


def list_ecebac(filiere: str, matiere: str, session: int = 2026, spe: int = 0) -> list[dict]:
    """Returns available subjects on ecebac.fr for a given stream/subject/year.

    Each entry has:
      id, number, title, url, corrige_available (bool)
    """
    fil = ECEBAC_FILIERE.get(filiere.lower())
    mat = ECEBAC_MATIERE.get(matiere.lower())
    if fil is None or mat is None:
        raise ValueError(f"Unknown filière/matière combo: {filiere}/{matiere}")
    url = f"https://ecebac.fr/listaca.php?fil={fil}&mat={mat}&spe={spe}&session={session}"
    try:
        html = fetch(url)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ecebac.fr returned {e.code}")
    # Each row has a link like /sujet/<id> with the title in between.
    subjects: list[dict] = []
    # Pattern: <a href="/sujet/4076"...>...title...</a>
    for m in re.finditer(r'href="/sujet/(\d+)"[^>]*>([^<]+)</a>', html):
        sub_id = m.group(1)
        title = m.group(2).strip()
        if not title or any(s['id'] == sub_id for s in subjects):
            continue
        subjects.append({
            'id': sub_id,
            'title': title,
            'url': f'https://ecebac.fr/sujet/{sub_id}',
            'source': 'ecebac.fr',
            'filiere': filiere.lower(),
            'matiere': matiere.lower(),
            'session': session,
        })
    return subjects


def fetch_ecebac_subject(subject_id: str) -> dict:
    """Scrape a single ecebac.fr subject page."""
    url = f"https://ecebac.fr/sujet/{subject_id}"
    html = fetch(url)
    # Extract the main body between <main> or the content column
    body = html
    for tag in ('main', 'article', 'section'):
        m = re.search(rf'<{tag}[^>]*>([\s\S]+?)</{tag}>', html, re.I)
        if m:
            body = m.group(1)
            break
    text = strip_html(body, max_chars=6000)
    # Surface direct PDF / ZIP links for completeness
    files = list({
        m.group(1) for m in
        re.finditer(r'href="([^"]+\.(?:pdf|zip|docx|ino|pdsprj))"', html, re.I)
    })
    files = [f if f.startswith('http') else f'https://ecebac.fr{f}' for f in files]
    title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    return {
        'id': subject_id,
        'url': url,
        'source': 'ecebac.fr',
        'title': (title_m.group(1).strip() if title_m else f'Sujet {subject_id}'),
        'text': text,
        'files': files[:12],
    }


def discover_freemaths(query: str) -> list[dict]:
    """Very loose search on freemaths.fr for a keyword."""
    try:
        url = f"https://www.freemaths.fr/?s={urllib.parse.quote(query)}"
        html = fetch(url)
    except Exception:
        return []
    out: list[dict] = []
    for m in re.finditer(r'<a[^>]+href="(https?://www\.freemaths\.fr/[^"]+)"[^>]*>\s*<h2[^>]*>([^<]+)</h2>', html):
        out.append({
            'title': m.group(2).strip(),
            'url': m.group(1),
            'source': 'freemaths.fr',
        })
        if len(out) >= 5:
            break
    return out


def discover_sujetsdebac(query: str) -> list[dict]:
    """Light scrape on sujetsdebac.fr for keywords."""
    try:
        url = f"https://www.sujetdebac.fr/recherche.html?q={urllib.parse.quote(query)}"
        html = fetch(url)
    except Exception:
        return []
    out: list[dict] = []
    for m in re.finditer(r'<a[^>]+href="(/[^"]+)"[^>]*>([^<]{10,120})</a>', html):
        href, title = m.group(1), m.group(2).strip()
        if 'sujet' in href or 'annale' in href:
            out.append({
                'title': title,
                'url': f"https://www.sujetdebac.fr{href}",
                'source': 'sujetsdebac.fr',
            })
            if len(out) >= 5:
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true', help='list available subjects (requires --filiere + --matiere)')
    ap.add_argument('--filiere', default='sti2d')
    ap.add_argument('--matiere', default='sin')
    ap.add_argument('--session', type=int, default=2026)
    ap.add_argument('--spe', type=int, default=0)
    ap.add_argument('--subject', help='ecebac.fr subject id to fetch')
    ap.add_argument('--discover', help='keyword search across other sites')
    ap.add_argument('--catalog', action='store_true', help='list all trusted sites')
    args = ap.parse_args()

    try:
        if args.catalog:
            print(json.dumps({'ok': True, 'sites': TRUSTED_SITES}, ensure_ascii=False))
            return 0
        if args.subject:
            data = fetch_ecebac_subject(args.subject)
            print(json.dumps({'ok': True, 'subject': data}, ensure_ascii=False))
            return 0
        if args.discover:
            results: list[dict] = []
            results += discover_freemaths(args.discover)
            results += discover_sujetsdebac(args.discover)
            print(json.dumps({'ok': True, 'results': results, 'query': args.discover}, ensure_ascii=False))
            return 0
        if args.list:
            subjects = list_ecebac(args.filiere, args.matiere, args.session, args.spe)
            print(json.dumps({'ok': True, 'subjects': subjects, 'count': len(subjects)}, ensure_ascii=False))
            return 0
        ap.print_help()
        return 1
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'{type(e).__name__}: {e}'}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
