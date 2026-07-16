#!/usr/bin/env python3
"""Recherche, extraction, embeddings et reranking RAG du WS15 Code."""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import pathlib
import re
import urllib.parse
import urllib.request
from typing import Any, Iterable


DEFAULT_EMBED_MODEL = "nomic-embed-text"


def post_json(base_url: str, path: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        urllib.parse.urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/")),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace") or "{}")


def result_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("resultsList", "results", "hits"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def extracted_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        if payload.get("ok") is False:
            return ""
        for key in ("markdown", "content", "text", "result", "extracted_content"):
            text = extracted_text(payload.get(key))
            if text.strip():
                return text
        for value in payload.values():
            text = extracted_text(value)
            if text.strip():
                return text
    if isinstance(payload, list):
        return "\n".join(filter(None, (extracted_text(item) for item in payload)))
    return ""


def fetch_page_text(url: str, timeout: int = 30) -> str:
    parts = urllib.parse.urlsplit(url)
    hostname = (parts.hostname or "").encode("idna").decode("ascii")
    authority = hostname if parts.port is None else f"{hostname}:{parts.port}"
    normalized_url = urllib.parse.urlunsplit((
        parts.scheme,
        authority,
        urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%:@"),
        urllib.parse.quote(urllib.parse.unquote(parts.query), safe="=&%:@/?+"),
        "",
    ))
    request = urllib.request.Request(normalized_url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AuroraIA-Code-RAG/1.0)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(750_000).decode("utf-8", errors="replace")
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()[:12_000]


def hashed_embedding(text: str, dimensions: int = 256) -> list[float]:
    vector = [0.0] * dimensions
    for term in re.findall(r"[a-z0-9_]{3,}", text.lower()):
        digest = hashlib.sha256(term.encode("utf-8")).digest()
        vector[int.from_bytes(digest[:2], "big") % dimensions] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def embed_texts(texts: list[str], model: str = DEFAULT_EMBED_MODEL) -> tuple[list[list[float]], str]:
    try:
        payload = post_json("http://127.0.0.1:11434", "/api/embed", {
            "model": model,
            "input": [text[:8000] for text in texts],
            "truncate": True,
        }, timeout=120)
        embeddings = payload.get("embeddings") or []
        if len(embeddings) == len(texts) and all(isinstance(row, list) and row for row in embeddings):
            return embeddings, f"ollama:{model}"
    except Exception:
        pass
    return [hashed_embedding(text) for text in texts], "local-hash-256-fallback"


def cosine(left: Iterable[float], right: Iterable[float]) -> float:
    left_values, right_values = list(left), list(right)
    if len(left_values) != len(right_values):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left_values, right_values)) / (left_norm * right_norm)


def build_rag_trace(base_url: str, out_dir: pathlib.Path, prompt: str) -> dict[str, Any]:
    trace: dict[str, Any] = {
        "searchEndpoint": "/api/web/search",
        "extractEndpoint": "/api/web/extract",
        "results": [],
        "fetchedPages": 0,
        "reranker": "embedding-cosine+lexical-overlap",
    }
    try:
        search = post_json(base_url, "/api/web/search", {
            "query": f"{prompt[:180]} design architecture best practices",
            "limit": 6,
        }, timeout=45)
        documents: list[dict[str, Any]] = []
        for index, item in enumerate(result_rows(search)[:3], start=1):
            url = str(item.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                continue
            try:
                extracted = post_json(base_url, "/api/web/extract", {
                    "url": url,
                    "prompt": "Extraire les principes techniques et visuels utiles, sans copier le contenu.",
                }, timeout=45)
                content = extracted_text(extracted).strip()[:12_000]
                if not content:
                    raise RuntimeError(str(extracted.get("error") or "extraction bridge vide"))
            except Exception as error:
                try:
                    content = fetch_page_text(url)
                    item = {**item, "extractFallback": "direct-http", "bridgeExtractError": str(error)}
                except Exception as fallback_error:
                    content = ""
                    item = {**item, "extractError": str(fallback_error), "bridgeExtractError": str(error)}
            if content:
                page_path = out_dir / "rag" / f"page-{index:02d}.txt"
                page_path.parent.mkdir(parents=True, exist_ok=True)
                page_path.write_text(content, encoding="utf-8")
                trace["fetchedPages"] += 1
            documents.append({
                "title": item.get("title"),
                "url": url,
                "snippet": item.get("snippet"),
                "content": content,
                "extractError": item.get("extractError"),
                "extractFallback": item.get("extractFallback"),
                "bridgeExtractError": item.get("bridgeExtractError"),
            })

        if documents:
            model = os.environ.get("AURORA_CODE_EMBED_MODEL", DEFAULT_EMBED_MODEL)
            vectors, embedding_name = embed_texts([prompt] + [
                f"{doc.get('title') or ''}\n{doc.get('snippet') or ''}\n{doc.get('content') or ''}"
                for doc in documents
            ], model)
            trace["embedding"] = embedding_name
            query_terms = set(re.findall(r"[a-z0-9_]{3,}", prompt.lower()))
            for document, vector in zip(documents, vectors[1:]):
                candidate_text = (
                    f"{document.get('title') or ''} {document.get('snippet') or ''} "
                    f"{document.get('content') or ''}"
                ).lower()
                candidate_terms = set(re.findall(r"[a-z0-9_]{3,}", candidate_text))
                lexical = len(query_terms & candidate_terms) / max(1, len(query_terms))
                document["score"] = round(0.85 * cosine(vectors[0], vector) + 0.15 * lexical, 6)
                document.pop("content", None)
            documents.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
            trace["results"] = documents
        else:
            trace["embedding"] = "not-run-no-search-results"
    except Exception as error:
        trace["error"] = str(error)

    target = out_dir / "rag" / "references.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
    return trace
