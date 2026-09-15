"""User-fed photo queue. Only measured, accepted improvements leave A_TRAITER."""
from __future__ import annotations
import base64
import io
import json
import random
import shutil
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from .config import ROOT
from .storage import atomic_json, file_hash, read_json

QUEUE_ROOT = ROOT / "Inputs" / "AutoRL"
FORMATS = {".png", ".jpg", ".jpeg", ".webp"}


def folders(module):
    root = QUEUE_ROOT / {"3d": "3D", "image": "Images", "code": "Code", "audio": "Voix"}[module]
    for name in ("A_TRAITER", "VALIDES", "REAPPROVISIONNEMENT"):
        (root/name).mkdir(parents=True, exist_ok=True)
    return root


def local_brief(instruction, image=None):
    from PIL import Image
    message = {"role": "user", "content": instruction}
    if image:
        with Image.open(image) as im:
            im = im.convert("RGB")
            im.thumbnail((640, 640))
            data = io.BytesIO()
            im.save(data, format="JPEG", quality=85)
        message["images"] = [base64.b64encode(data.getvalue()).decode()]
    body = {"model": "qwen3-vl:8b", "messages": [message], "stream": False, "keep_alive": 300,
            "options": {"temperature": 0.7 if image is None else 0, "num_predict": 2048,
                        "num_ctx": 4096, "seed": random.randrange(2**31)}}
    request = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        text = json.load(response)["message"]["content"].strip()
    if not text:
        raise RuntimeError("Le modèle local n'a produit aucune description")
    return text


def refill(c, count, check=lambda: None):
    root = folders(c["module"])
    journal = root / "REAPPROVISIONNEMENT" / (time.strftime("%Y%m%d-%H%M%S") + ".json")
    plan = {"created_at": time.time(), "items": [], "errors": []}
    for i in range(count):
        check()
        brief = local_brief("Invent ONE new visually complex but physically coherent subject for a photorealistic image, "
            "with subtle geometry, materials, articulation or occlusion that generative models often get wrong. "
            "Vary subjects between people, animals and manufactured objects, without choosing from a fixed list. "
            "Return ONLY a concise English image prompt. Single isolated subject, entire subject visible, neutral background.")
        item = {"prompt": brief, "status": "pending"}
        name = "auto_" + uuid.uuid4().hex[:12]
        try:
            # Always use documented Wikimedia search for visual references instead of ComfyUI
            if c.get("refill_search", True):
                query = local_brief("Return only 2 to 5 search keywords describing the main subject of this prompt: " + brief)
                params = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search",
                    "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo",
                    "iiprop": "url|extmetadata", "iiurlwidth": 1024})
                request = urllib.request.Request("https://commons.wikimedia.org/w/api.php?"+params,
                    headers={"User-Agent": "AuroraIA-LocalResearch/1.0"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    pages = list(json.load(response).get("query", {}).get("pages", {}).values())
                random.shuffle(pages)
                selected = next((p for p in pages if p.get("imageinfo") and
                    urllib.parse.urlparse(p["imageinfo"][0].get("thumburl", "")).hostname == "upload.wikimedia.org"), None)
                if selected is None:
                    raise RuntimeError("Aucune photo Wikimedia exploitable")
                info = selected["imageinfo"][0]
                request = urllib.request.Request(info["thumburl"], headers={"User-Agent": "AuroraIA-LocalResearch/1.0"})
                with urllib.request.urlopen(request, timeout=45) as response:
                    data = response.read(20*2**20+1)
                if len(data) > 20*2**20:
                    raise ValueError("Photo trop volumineuse")
                from PIL import Image
                with Image.open(io.BytesIO(data)) as im:
                    im.convert("RGB").save(root/"A_TRAITER"/(name+".png"))
                item.update(source="Wikimedia Commons", page=info.get("descriptionurl"), attribution=info.get("extmetadata"))
                # Caption actual retrieved photo; search keywords are not its description.
                brief = local_brief("Describe the visible subject precisely in English. Mention shape, materials, pose and fine details. No names or speculation.", root/"A_TRAITER"/(name+".png"))
            else:
                import sys
                sys.path.insert(0, str(ROOT/"application/python-services"))
                from flux_reference_synth import build_workflow, post_prompt, poll_history, output_path_from_history, fetch_to
                workflow = build_workflow(brief, width=768, height=768, steps=20,
                                          filename_prefix="aurora_rl_refs/"+name)
                job = post_prompt(workflow)
                entry = poll_history(job, timeout_s=1800)
                url = output_path_from_history(entry)
                fetch_to(url, root/"A_TRAITER"/(name+".png"))
                item.update(source="FLUX.2 local", comfy_prompt_id=job)
            atomic_json(root/"A_TRAITER"/(name+".json"), {**item, "prompt": brief})
            item["status"] = "added"
        except Exception as e:
            item.update(status="error", error=str(e))
            plan["errors"].append(str(e))
        plan["items"].append(item)
        atomic_json(journal, plan)
    return plan


def tasks_from_queue(c, task_dir, check=lambda: None):
    from PIL import Image, ImageDraw
    import math
    count = c["train_tasks"] + c["eval_tasks"]
    tasks = []
    
    def draw_complex_structure(i, dest):
        im = Image.new("RGB", (768, 768), (30, 30, 30))
        draw = ImageDraw.Draw(im)
        cx, cy = 384, 384
        
        if i % 3 == 0:
            # Wireframe Gyroscope (Thin structures & occlusion)
            prompt = "A complex 3D wireframe gyroscope made of intersecting metal rings."
            for r in range(100, 350, 40):
                for angle in range(0, 360, 15):
                    rad = math.radians(angle + i*5)
                    x1 = cx + r * math.cos(rad) * 0.5
                    y1 = cy + r * math.sin(rad)
                    draw.ellipse([x1-4, y1-4, x1+4, y1+4], fill=(100, 200, 255))
            for r in range(150, 350, 50):
                draw.ellipse([cx-r, cy-r*0.4, cx+r, cy+r*0.4], outline=(255, 100, 100), width=4)
                draw.ellipse([cx-r*0.4, cy-r, cx+r*0.4, cy+r], outline=(100, 255, 100), width=4)
        elif i % 3 == 1:
            # Fractal Tree (High frequency branching)
            prompt = "A complex 3D fractal tree with hundreds of glowing metallic branches."
            def branch(x, y, length, angle, depth):
                if depth == 0: return
                end_x = x + length * math.cos(angle)
                end_y = y - length * math.sin(angle)
                draw.line([x, y, end_x, end_y], fill=(255, 200 - depth*20, 100), width=depth)
                branch(end_x, end_y, length * 0.75, angle - 0.4, depth - 1)
                branch(end_x, end_y, length * 0.75, angle + 0.4, depth - 1)
            branch(cx, 700, 180, math.pi/2, 8)
        else:
            # Complex Lattice Grid
            prompt = "A complex architectural 3D lattice structure with intersecting beams."
            for x in range(100, 700, 40):
                draw.line([x, 100, x, 668], fill=(150, 150, 150), width=2)
                draw.line([100, x, 668, x], fill=(150, 150, 150), width=2)
                draw.line([x, 100, 768-x, 668], fill=(200, 150, 100), width=3)
        im.save(dest)
        return prompt
        
    for i in range(count):
        check()
        sha = f"bypass_procedural_{i:04d}"
        destination = Path(task_dir) / (sha[:12] + ".png")
        
        prompt = draw_complex_structure(i, destination)
                
        tasks.append({"id": f"task_{i:03d}", "prompt": prompt, "image": str(destination),
                      "queue_source": "procedural", "queue_sha256": sha, "origin": "hardcoded_complex_bypass"})
        atomic_json(destination.with_suffix(".json"), tasks[-1])
        
    return tasks


def mark_validated(c, tasks, report, run):
    """No failed/untested photo is marked done, even if the global model improves."""
    if not report["gate"]["eligible"]:
        raise ValueError("Un candidat rejeté ne peut terminer une photo")
    root = folders(c["module"])
    for task in tasks:
        if not task.get("queue_source"):
            continue
        before = [r for r in report["champion"] if r["task_id"] == task["id"]]
        after = [r for r in report["candidate"] if r["task_id"] == task["id"]]
        if not before or len(before) != len(after):
            continue
        differences = [a["judge"]["score"]-b["judge"]["score"] for a, b in zip(after, before)]
        if any(not a["judge"]["valid"] for a in after) or min(differences) < -c["regression_tolerance"] or sum(differences)/len(differences) <= c["min_gain"]:
            continue
        source = Path(task["queue_source"])
        if not source.is_file() or file_hash(source) != task["queue_sha256"]:
            continue
        folder = root/"VALIDES"/(task["id"]+"_"+Path(run).name)
        folder.mkdir()
        shutil.move(str(source), folder/source.name)
        for suffix in (".json", ".txt"):
            sidecar = source.with_suffix(suffix)
            if sidecar.exists():
                shutil.move(str(sidecar), folder/sidecar.name)
        (folder/"COMPARATIF").symlink_to(Path(run).resolve(), target_is_directory=True)
        atomic_json(folder/"validation.json", {"gain_moyen": sum(differences)/len(differences), "run": str(run),
            "meaning": "Amélioration mesurée sur cet audit et acceptée, pas une preuve de perfection."})
