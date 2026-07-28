"""Veille factuelle des modèles vidéo/voix suivis par AuroraIA.

Le script interroge uniquement les API officielles GitHub et Hugging Face.
Il écrit un rapport atomique, mais ne télécharge aucun poids et ne modifie
jamais la stratégie revue manuellement.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable


WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = WORKSPACE / "output" / "video-metrics" / "model_watch_latest.json"
USER_AGENT = "AuroraIA-video-model-watch/1.0"

GITHUB_REPOS = {
    "wan2.2": "Wan-Video/Wan2.2",
    "cosyvoice": "QwenAudio/CosyVoice",
    "longcat-video": "meituan-longcat/LongCat-Video",
    "anytalker": "HKUST-C4G/AnyTalker",
    "stable-video-infinity": "vita-epfl/Stable-Video-Infinity",
    "stand-in": "WeChatCV/Stand-In",
    "infinite-talk": "MeiGen-AI/InfiniteTalk",
    "latentsync": "bytedance/LatentSync",
}

HF_MODELS = {
    "wan2.2-ti2v-5b": "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
    "ltx-2.3-fp8": "Lightricks/LTX-2.3-fp8",
    "cosyvoice3": "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
    "longcat-avatar-1.5": "meituan-longcat/LongCat-Video-Avatar-1.5",
    "refalign-14b": "gudaochangsheng/RefAlign-14B",
    "svi-model": "vita-video-gen/svi-model",
}


def fetch_json(url: str, timeout: float = 15.0) -> object:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _safe_fetch(fetcher: Callable[[str, float], object], url: str, timeout: float) -> dict:
    started = time.monotonic()
    try:
        payload = fetcher(url, timeout)
        return {
            "ok": True,
            "url": url,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "payload": payload,
        }
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "url": url,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": f"{type(exc).__name__}: {str(exc)[:300]}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error": f"{type(exc).__name__}: {str(exc)[:300]}",
        }


def _github_summary(name: str, result: dict) -> dict:
    base = {
        "id": name,
        "provider": "github",
        "source": result["url"],
        "ok": result["ok"],
        "latency_ms": result.get("latency_ms"),
    }
    if not result["ok"]:
        return {**base, "error": result.get("error")}
    payload = result.get("payload")
    if not isinstance(payload, dict):
        return {**base, "ok": False, "error": "github_payload_not_object"}
    license_info = payload.get("license") if isinstance(payload.get("license"), dict) else {}
    return {
        **base,
        "full_name": payload.get("full_name"),
        "default_branch": payload.get("default_branch"),
        "pushed_at": payload.get("pushed_at"),
        "updated_at": payload.get("updated_at"),
        "archived": bool(payload.get("archived")),
        "license": license_info.get("spdx_id"),
        "html_url": payload.get("html_url"),
    }


def _hf_summary(name: str, result: dict) -> dict:
    base = {
        "id": name,
        "provider": "huggingface",
        "source": result["url"],
        "ok": result["ok"],
        "latency_ms": result.get("latency_ms"),
    }
    if not result["ok"]:
        return {**base, "error": result.get("error")}
    payload = result.get("payload")
    if not isinstance(payload, dict):
        return {**base, "ok": False, "error": "huggingface_payload_not_object"}
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    license_tag = next(
        (str(tag).split(":", 1)[1] for tag in tags if str(tag).startswith("license:")),
        None,
    )
    siblings = payload.get("siblings") if isinstance(payload.get("siblings"), list) else []
    known_bytes = sum(
        int(item.get("size") or 0)
        for item in siblings
        if isinstance(item, dict) and isinstance(item.get("size"), (int, float))
    )
    return {
        **base,
        "model_id": payload.get("modelId") or payload.get("id"),
        "sha": payload.get("sha"),
        "last_modified": payload.get("lastModified"),
        "private": bool(payload.get("private")),
        "gated": payload.get("gated", False),
        "license": license_tag,
        "files": len(siblings),
        "known_size_bytes": known_bytes or None,
    }


def detect_official_wan27(payload: object) -> dict:
    """Un Wan 2.7 n'est confirmé que dans l'espace officiel Wan-AI."""
    models = payload if isinstance(payload, list) else []
    exact = []
    for item in models:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("modelId") or item.get("id") or "")
        owner, _, name = model_id.partition("/")
        normalized = name.lower().replace("_", "").replace("-", "").replace(".", "")
        if owner == "Wan-AI" and "wan27" in normalized:
            exact.append(model_id)
    return {
        "verified": bool(exact),
        "official_model_ids": sorted(set(exact)),
        "decision": (
            "official_weights_found_review_required"
            if exact
            else "no_official_wan2.7_weights_found"
        ),
    }


def build_report(
    *,
    fetcher: Callable[[str, float], object] = fetch_json,
    timeout: float = 15.0,
) -> dict:
    jobs = []
    for name, repo in GITHUB_REPOS.items():
        url = f"https://api.github.com/repos/{repo}"
        jobs.append(("github", name, url))
    for name, model_id in HF_MODELS.items():
        encoded = urllib.parse.quote(model_id, safe="/")
        url = f"https://huggingface.co/api/models/{encoded}"
        jobs.append(("huggingface", name, url))

    wan_query = urllib.parse.urlencode({
        "author": "Wan-AI",
        "search": "Wan2.7",
        "limit": "100",
        "full": "true",
    })
    jobs.append((
        "wan2.7-watch",
        "wan2.7",
        f"https://huggingface.co/api/models?{wan_query}",
    ))

    # Une source lente ou indisponible ne doit jamais immobiliser toute la
    # veille. L'ordre du rapport reste déterministe malgré les requêtes
    # parallèles.
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(8, len(jobs)),
        thread_name_prefix="aurora-model-watch",
    ) as executor:
        futures = [
            executor.submit(_safe_fetch, fetcher, url, timeout)
            for _provider, _name, url in jobs
        ]
        results = [future.result() for future in futures]

    sources = []
    wan_result = None
    for (provider, name, _url), result in zip(jobs, results):
        if provider == "github":
            sources.append(_github_summary(name, result))
        elif provider == "huggingface":
            sources.append(_hf_summary(name, result))
        else:
            wan_result = result
    assert wan_result is not None
    wan_watch = (
        detect_official_wan27(wan_result.get("payload"))
        if wan_result.get("ok")
        else {
            "verified": None,
            "official_model_ids": [],
            "decision": "official_source_unreachable_no_conclusion",
            "error": wan_result.get("error"),
        }
    )
    checked = sum(1 for source in sources if source.get("ok"))
    return {
        "ok": checked > 0,
        "kind": "video_model_watch",
        "generated_at": int(time.time()),
        "policy": {
            "official_sources_only": True,
            "downloads_performed": False,
            "strategy_modified": False,
            "license_is_metadata_not_quality_filter": True,
        },
        "coverage": {
            "checked": checked,
            "expected": len(sources),
            "complete": checked == len(sources) and wan_result.get("ok") is True,
        },
        "wan2.7": wan_watch,
        "sources": sources,
    }


def write_atomic(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = build_report(timeout=max(2.0, min(60.0, args.timeout)))
    if not args.no_write:
        write_atomic(Path(args.output), report)
        report["report_path"] = str(Path(args.output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
