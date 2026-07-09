import argparse
import base64
import hashlib
import json
import os

OLLAMA_URL = os.environ.get("AURORA_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = "qwen3-vl:8b"
FALLBACK_MODEL = "qwen3-vl:30b"


def question_hash(question):
    return hashlib.sha256(question.encode("utf-8")).hexdigest()[:8]


def _load_mock(question):
    path = os.environ.get("AURORA_VLM_MOCK")
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    entry = data.get(question_hash(question), data.get("default"))
    if not isinstance(entry, dict):
        raise ValueError("mock sans entree %s ni default" % question_hash(question))
    return entry


def _encode_images(images):
    encoded = []
    for p in images:
        with open(p, "rb") as fh:
            encoded.append(base64.b64encode(fh.read()).decode("ascii"))
    return encoded


def _chat(model, content, images_b64, timeout):
    import requests
    payload = {
        "model": model,
        "format": "json",
        "think": False,
        "stream": False,
        "options": {"temperature": 0},
        "messages": [{"role": "user", "content": content, "images": images_b64}],
    }
    resp = requests.post(OLLAMA_URL + "/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def ask_vlm(images, question, schema_hint="", model=None, timeout=120):
    mock = _load_mock(question)
    if mock is not None:
        return mock
    model = model or os.environ.get("AURORA_VISION_MODEL", DEFAULT_MODEL)
    content = question
    if schema_hint:
        content = question + "\nReponds uniquement en JSON strict au format: " + schema_hint
    images_b64 = _encode_images(images)
    last_err = None
    for _attempt in range(2):
        try:
            raw = _chat(model, content, images_b64, timeout)
        except Exception as exc:
            if model == DEFAULT_MODEL and "not found" in str(exc).lower():
                model = FALLBACK_MODEL
                raw = _chat(model, content, images_b64, timeout)
            else:
                raise
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            last_err = ValueError("reponse JSON non-objet: %s" % type(data).__name__)
        except ValueError as exc:
            last_err = exc
        content = content + "\nTa reponse precedente etait invalide. Reponds UNIQUEMENT avec un objet JSON valide."
    raise ValueError("reponse VLM invalide apres retry: %s" % last_err)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="+", required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--schema-hint", default="", dest="schema_hint")
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()
    out = ask_vlm(a.images, a.question, a.schema_hint, model=a.model, timeout=a.timeout)
    print(json.dumps(out, ensure_ascii=True))


if __name__ == "__main__":
    main()
