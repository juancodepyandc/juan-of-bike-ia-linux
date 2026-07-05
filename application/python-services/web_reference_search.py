#!/usr/bin/env python3
"""
web_reference_search.py
Searches the web for character reference sheets / back views to avoid hallucinating
hidden details (like wings, jetpacks) when generating 3D models.
"""

import sys
import json
import argparse
import urllib.request
from pathlib import Path

try:
    from duckduckgo_search import DDGS
except ImportError:
    print(json.dumps({"error": "duckduckgo_search not installed."}))
    sys.exit(1)

def search_character_back(character_name: str, output_dir: str, limit: int = 2) -> dict:
    query = f"{character_name} back view model sheet OR orthographic"
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    try:
        with DDGS() as ddgs:
            # We search for images
            images = list(ddgs.images(query, max_results=limit))
            
            for i, img_data in enumerate(images):
                url = img_data.get("image")
                if not url:
                    continue
                
                # Download the image
                ext = url.split(".")[-1].lower()
                if ext not in ["jpg", "jpeg", "png", "webp"]:
                    ext = "jpg"
                
                # Safely slice long URLs
                if len(ext) > 5:
                    ext = "jpg"
                    
                local_path = out_dir / f"{character_name.replace(' ', '_')}_web_ref_{i}.{ext}"
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=5) as response, open(local_path, 'wb') as out_file:
                        out_file.write(response.read())
                    results.append(str(local_path))
                except Exception as e:
                    pass
    except Exception as e:
        return {"ok": False, "error": str(e)}
        
    return {"ok": True, "downloaded_references": results}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    
    result = search_character_back(args.character, args.output_dir)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
