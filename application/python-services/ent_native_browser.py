"""
Native ENT browser session for the Aurora desktop app.

The frontend sends credentials for a single run through stdin. This script
opens a local Chromium session with Playwright, signs in, visits requested ENT
sections, and returns text snapshots plus downloadable links as JSON.
"""

from __future__ import annotations

import json
import mimetypes
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

SECTION_KEYWORDS = {
    "devoirs": ["devoir", "travail", "cahier de textes", "homework"],
    "notes": ["note", "resultat", "résultat", "moyenne", "grade"],
    "agenda": ["agenda", "emploi du temps", "calendrier", "planning"],
    "fichiers": ["fichier", "document", "ressource", "cloud", "casier", "piece jointe", "pièce jointe"],
}


def ensure_playwright() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except Exception:
        pass
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "playwright", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def visible_input(locator):
    try:
        count = locator.count()
        for i in range(min(count, 20)):
            item = locator.nth(i)
            try:
                if item.is_visible(timeout=250):
                    return item
            except Exception:
                continue
    except Exception:
        return None
    return None


def fill_login_in_frame(frame, username: str, password: str) -> bool:
    password_field = visible_input(frame.locator('input[type="password"]'))
    if password_field is None:
        return False
    user_field = visible_input(frame.locator(
        'input[type="email"], input[type="text"], input[name*="user" i], '
        'input[name*="login" i], input[name*="email" i], input[name*="identifiant" i], '
        'input[id*="user" i], input[id*="login" i], input[id*="email" i], '
        'input[autocomplete="username"]'
    ))
    if user_field is None:
        inputs = frame.locator("input")
        try:
            for i in range(min(inputs.count(), 30)):
                item = inputs.nth(i)
                if item.is_visible(timeout=250):
                    input_type = (item.get_attribute("type") or "text").lower()
                    if input_type in {"text", "email", "tel"}:
                        user_field = item
                        break
        except Exception:
            pass
    if user_field is None:
        return False

    user_field.fill(username, timeout=3000)
    password_field.fill(password, timeout=3000)

    submit = visible_input(frame.locator(
        'button[type="submit"], input[type="submit"], button:has-text("Connexion"), '
        'button:has-text("Se connecter"), button:has-text("Login"), button:has-text("Valider"), '
        'button:has-text("Continuer")'
    ))
    if submit is not None:
        submit.click(timeout=5000)
    else:
        password_field.press("Enter", timeout=3000)
    return True


def page_has_login(page) -> bool:
    try:
        if re.search(r"/login|/auth|connexion|sign.?in", page.url, re.I):
            return True
        for frame in page.frames:
            if frame.locator('input[type="password"]').count() > 0:
                return True
    except Exception:
        return False
    return False


def click_section_candidate(page, section: str) -> bool:
    keywords = SECTION_KEYWORDS.get(section, [section])
    pattern = re.compile("|".join(re.escape(k) for k in keywords), re.I)
    for frame in page.frames:
        try:
            elements = frame.locator("a, button, [role='button'], [role='menuitem']")
            for i in range(min(elements.count(), 250)):
                element = elements.nth(i)
                try:
                    text = (element.inner_text(timeout=400) or "").strip()
                    title = (element.get_attribute("title") or "").strip()
                    aria = (element.get_attribute("aria-label") or "").strip()
                    label = " ".join([text, title, aria])
                    if label and pattern.search(label) and element.is_visible(timeout=400):
                        element.click(timeout=4000)
                        page.wait_for_timeout(1500)
                        return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def navigate_section(page, section: str, target: str) -> None:
    if target:
        try:
            page.goto(urljoin(page.url, target), wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass
    click_section_candidate(page, section)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(2500)


def collect_frame_text(frame) -> str:
    try:
        return (frame.locator("body").inner_text(timeout=3000) or "").strip()
    except Exception:
        return ""


def collect_attachments(page) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    file_re = re.compile(r"\.(pdf|docx?|odt|rtf|txt|csv|xlsx?|pptx?|jpg|jpeg|png|webp|zip)(?:[?#].*)?$", re.I)
    hint_re = re.compile(
        r"telecharg|télécharg|download|attachment|piece\s*jointe|pi[eè]ce\s*jointe|"
        r"fichier|document|ressource|corrig|annale|sujet|fiche",
        re.I,
    )
    for frame in page.frames:
        try:
            links = frame.locator("a[href], area[href]")
            for i in range(min(links.count(), 300)):
                link = links.nth(i)
                href = link.get_attribute("href") or ""
                if not href:
                    continue
                url = urljoin(frame.url or page.url, href)
                if url in seen:
                    continue
                text = (link.inner_text(timeout=500) or "").strip()
                download = link.get_attribute("download") or ""
                type_attr = link.get_attribute("type") or ""
                if not (
                    file_re.search(url)
                    or file_re.search(download)
                    or hint_re.search(url)
                    or hint_re.search(text)
                    or hint_re.search(download)
                    or re.search(r"pdf|word|excel|powerpoint|zip|octet-stream", type_attr, re.I)
                ):
                    continue
                seen.add(url)
                out.append({
                    "url": url,
                    "text": text[:200],
                    "filename": download or "",
                    "download": download or "",
                    "type": type_attr or "",
                    "scope": frame.url or page.url,
                })
                if len(out) >= 200:
                    return out
        except Exception:
            continue
    return out


def safe_filename(value: str, fallback: str) -> str:
    name = unquote((value or "").split("?")[0].split("#")[0]).strip()
    name = Path(name).name
    name = re.sub(r"[^\w.\-() ]+", "_", name, flags=re.UNICODE).strip(" .")
    return name[:120] or fallback


def filename_from_response(attachment: dict[str, Any], headers: dict[str, str], index: int) -> str:
    disposition = headers.get("content-disposition") or headers.get("Content-Disposition") or ""
    match = re.search(r"filename\*?=(?:UTF-8''|\"?)([^\";]+)", disposition, re.I)
    if match:
        return safe_filename(match.group(1), f"resource-{index}")
    candidate = attachment.get("filename") or attachment.get("download") or ""
    if not candidate:
        candidate = Path(urlparse(str(attachment.get("url") or "")).path).name
    name = safe_filename(str(candidate), f"resource-{index}")
    if "." not in name:
        mime = headers.get("content-type", "").split(";")[0].strip()
        ext = mimetypes.guess_extension(mime) or ""
        if ext:
            name = f"{name}{ext}"
    return name


def unique_path(folder: Path, name: str) -> Path:
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for i in range(2, 1000):
        next_candidate = folder / f"{stem}-{i}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    return folder / f"{stem}-{int(time.time())}{suffix}"


def download_attachments(context, attachments: list[dict[str, Any]], folder: Path) -> list[dict[str, Any]]:
    folder.mkdir(parents=True, exist_ok=True)
    enriched: list[dict[str, Any]] = []
    for index, attachment in enumerate(attachments[:120], start=1):
        current = dict(attachment)
        url = str(current.get("url") or "")
        if not url:
            enriched.append(current)
            continue
        try:
            response = context.request.get(url, timeout=30000)
            headers = dict(response.headers)
            if not response.ok:
                current["downloaded"] = False
                current["downloadError"] = f"HTTP {response.status}"
                enriched.append(current)
                continue
            body = response.body()
            if len(body) > 40 * 1024 * 1024:
                current["downloaded"] = False
                current["downloadError"] = "Fichier trop volumineux (>40 MB)"
                enriched.append(current)
                continue
            path = unique_path(folder, filename_from_response(current, headers, index))
            path.write_bytes(body)
            current["downloaded"] = True
            current["localPath"] = str(path)
            current["sizeBytes"] = len(body)
            current["mime"] = headers.get("content-type", "")
        except Exception as exc:
            current["downloaded"] = False
            current["downloadError"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        enriched.append(current)
    return enriched


def snapshot_page(page) -> dict[str, Any]:
    parts: list[str] = []
    for frame in page.frames:
        text = collect_frame_text(frame)
        if text:
            label = frame.name or frame.url or "frame"
            parts.append(f"\n\n=== {label} ===\n{text}")
    joined = "\n".join(parts).strip()
    return {
        "text": joined[:80000],
        "title": page.title(),
        "url": page.url,
        "containers": [],
    }


def run(payload: dict[str, Any]) -> dict[str, Any]:
    if not ensure_playwright():
        return {"ok": False, "error": "Playwright indisponible et installation impossible"}

    from playwright.sync_api import sync_playwright

    login_url = str(payload.get("loginUrl") or "").strip()
    username = str(payload.get("username") or "")
    password = str(payload.get("password") or "")
    sections = payload.get("sections") or []
    section_paths = payload.get("sectionPaths") or {}
    profile_name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(payload.get("profileKey") or "default"))[:80]
    profile_dir = Path(payload.get("profileRoot") or Path.cwd() / "output" / "ent_native_profiles") / profile_name
    download_root = Path(payload.get("downloadRoot") or Path.cwd() / "output" / "ent_downloads" / profile_name)
    profile_dir.mkdir(parents=True, exist_ok=True)

    if not login_url or not username or not password:
        return {"ok": False, "error": "loginUrl + username + password requis"}

    results: dict[str, Any] = {}
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            viewport={"width": 1366, "height": 900},
            user_agent=USER_AGENT,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(login_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)

        submitted = False
        for frame in page.frames:
            try:
                if fill_login_in_frame(frame, username, password):
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted and page_has_login(page):
            context.close()
            return {"ok": False, "reason": "no_login_form", "error": "Formulaire de connexion introuvable"}

        deadline = time.time() + 90
        while time.time() < deadline:
            page.wait_for_timeout(1500)
            if not page_has_login(page):
                break

        if page_has_login(page):
            body = collect_frame_text(page.main_frame).lower()
            if re.search(r"captcha|recaptcha|hcaptcha", body):
                reason = "captcha"
            elif re.search(r"code|mfa|2fa|double.?facteur|otp", body):
                reason = "mfa"
            else:
                reason = "auth_pending"
            context.close()
            return {
                "ok": False,
                "reason": reason,
                "error": "Connexion non terminee. Termine la verification dans la fenetre ouverte puis relance.",
            }

        for section in sections:
            section = str(section)
            target = section_paths.get(section) or ""
            navigate_section(page, section, target)
            attachments = collect_attachments(page)
            attachments = download_attachments(context, attachments, download_root / section)
            results[section] = {
                "ok": True,
                "snapshot": snapshot_page(page),
                "attachments": attachments,
                "hostname": page.url.split("/")[2] if "://" in page.url else "",
            }

        context.close()
    return {"ok": True, "sectionResults": results}


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    result = run(payload)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
