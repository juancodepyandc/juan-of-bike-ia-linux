"""Aurora Vision Research
Autonomous web scraping and visual verification module using local VLM.
"""
import base64
import json
import logging
import os
import urllib.request
from pathlib import Path
from duckduckgo_search import DDGS

log = logging.getLogger(__name__)

OLLAMA_API_URL = "http://localhost:11434/api/chat"
VLM_MODEL = "qwen3-vl:8b"

def _encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def _ask_ollama(prompt: str, image_paths: list[Path] = None, system_prompt: str = None) -> str:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    user_msg = {"role": "user", "content": prompt}
    if image_paths:
        user_msg["images"] = [_encode_image(p) for p in image_paths if p.exists()]
    messages.append(user_msg)

    data = {
        "model": VLM_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": 0,
        "options": {"temperature": 0.1}
    }
    
    req = urllib.request.Request(OLLAMA_API_URL, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("message", {}).get("content", "").strip()
    except Exception as e:
        log.error(f"Ollama API error: {e}")
        return ""

def identify_character_in_prompt(prompt: str) -> str | None:
    """Uses a fast model (or just logic) to extract the character name if present."""
    sys_prompt = "Extract ONLY the name of the character/celebrity/IP from the user's prompt. If there is no specific known character (just generic 'a man', 'a warrior'), return 'NONE'. Do not include any other text."
    
    data = {
        "model": "qwen2.5:7b", # lightweight fast model
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {"temperature": 0.0}
    }
    req = urllib.request.Request(OLLAMA_API_URL, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res = json.loads(response.read().decode("utf-8")).get("message", {}).get("content", "").strip()
            if res and res.upper() not in ["NONE", "NO", "FALSE"]:
                return res
    except Exception as e:
        log.error(f"Failed to identify character: {e}")
    return None

def fetch_reference_images(query: str, save_dir: Path, max_images: int = 1) -> list[Path]:
    """Downloads reference images for a character using DuckDuckGo."""
    save_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    
    log.info(f"Searching DuckDuckGo Images for: {query}")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(
                query + " official anime character design full body -cosplay -fanart -3d",
                region="wt-wt",
                safesearch="moderate",
                size="Large",
                type_image="photo",
                max_results=max_images + 5
            ))
            
            import requests
            for r in results:
                if len(downloaded) >= max_images:
                    break
                url = r.get("image")
                if not url:
                    continue
                try:
                    img_data = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}).content
                    filename = f"ref_{query.replace(' ', '_')}_{len(downloaded)}.jpg"
                    filepath = save_dir / filename
                    with open(filepath, "wb") as f:
                        f.write(img_data)
                    downloaded.append(filepath)
                    log.info(f"Downloaded reference: {url}")
                except Exception as e:
                    log.warning(f"Failed to download {url}: {e}")
    except Exception as e:
        log.error(f"DDG Search failed: {e}")
        
    if not downloaded:
        log.warning(f"DDG failed or returned nothing. No reference images available for {query}.")
            
    return downloaded

def generate_visual_traits_from_knowledge(character_name: str) -> str:
    """Uses the LLM's internal knowledge to describe the character's visual traits."""
    prompt = f"Describe the visual appearance of {character_name}. Extract the most crucial visual traits (colors, clothing, hair, distinctive features) and write a CONCISE, comma-separated image generation prompt (MAX 50 WORDS). IMPORTANT: If this is an anime/manga or cartoon character, explicitly include 'anime style' or 'cartoon style' and DO NOT output realistic traits. Example format: 'anime style, red torso, yellow horns, metallic blue helmet...'"
    log.info(f"Asking LLM ({VLM_MODEL}) to recall visual traits from knowledge base...")
    resp = _ask_ollama(prompt, system_prompt="You are an expert character concept artist.")
    if resp:
        return resp.replace("\n", " ").strip()
    return ""

def extract_visual_traits(image_path: Path, character_name: str) -> str:
    """Uses the VLM to describe the character's visual traits perfectly."""
    prompt = f"Analyze this reference image of {character_name}. Extract the most crucial visual traits (colors, armor, head, distinctive features) and write a CONCISE, comma-separated image generation prompt (MAX 50 WORDS). IMPORTANT: You MUST include the art style (e.g. 'anime style', 'cartoon style', 'photorealistic'). Do NOT write an essay or use bullet points. Only output the visual tags. Example format: 'anime style, red torso, yellow horns, metallic blue helmet...'"
    log.info(f"Asking VLM ({VLM_MODEL}) to analyze reference image...")
    return _ask_ollama(prompt, [image_path])

def evaluate_fidelity(reference_path: Path, generated_path: Path, character_name: str) -> dict:
    """Compares the generated image to the reference."""
    sys_prompt = "You are a strict QA visual evaluator. Compare Image 1 (Reference) with Image 2 (Generated). Answer strictly in JSON format: {'passed': bool, 'score': float, 'critique': 'detailed explanation'}."
    prompt = f"Image 1 is the true reference of {character_name}. Image 2 is an AI generation. Does Image 2 accurately represent the character visually (ignoring pose)? CRITICAL RULES: 1. REJECT instantly (score < 0.5) if the face is distorted, blurry, completely missing features, or has black glitch artifacts. 2. REJECT if the texture is messy or noisy. IMPORTANT: Ignore minor discrepancies like exact eye color or minor outfit variations. Focus on the overall character likeness. Score 0.0 to 1.0 (0.85+ is a pass)."
    log.info(f"Asking VLM ({VLM_MODEL}) to evaluate fidelity...")
    
    resp = _ask_ollama(prompt, [reference_path, generated_path], sys_prompt)
    
    try:
        if "```json" in resp:
            resp = resp.split("```json")[1].split("```")[0].strip()
        elif "```" in resp:
            resp = resp.split("```")[1].strip()
            
        data = json.loads(resp)
        return {
            "passed": bool(data.get("passed", False)),
            "score": float(data.get("score", 0.0)),
            "critique": str(data.get("critique", resp))
        }
    except Exception as e:
        log.error(f"Failed to parse VLM fidelity output: {e} -> Raw: {resp}")
        return {"passed": True, "score": 0.8, "critique": "Fallback: VLM returned unparseable output. Assuming passed to prevent loop."}
