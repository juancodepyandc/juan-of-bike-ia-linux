"""User-fed photo queue. Only measured, accepted improvements leave A_TRAITER."""
from __future__ import annotations
import base64
import io
import json
import random
import re
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
    root = QUEUE_ROOT / {"3d": "3D", "image": "Images", "code": "Code", "audio": "Voix", "conversation": "Conversation", "cyber": "Cyber", "cowork": "Cowork", "learning": "Apprentissage", "video": "Video", "animation": "Animation"}[module]
    for name in ("A_TRAITER", "VALIDES", "REAPPROVISIONNEMENT"):
        (root/name).mkdir(parents=True, exist_ok=True)
    return root


def local_brief(instruction, image=None):
    from PIL import Image
    from .resources import release_idle_comfy
    if not release_idle_comfy():
        raise RuntimeError("ComfyUI est occupé ; la description attend un GPU disponible")
    message = {"role": "user", "content": instruction}
    if image:
        with Image.open(image) as im:
            im = im.convert("RGB")
            im.thumbnail((640, 640))
            data = io.BytesIO()
            im.save(data, format="JPEG", quality=85)
        message["images"] = [base64.b64encode(data.getvalue()).decode()]
    for budget in (2048, 8192):
        body = {"model": "qwen3-vl:8b", "stream": False, "think": False, "keep_alive": 0,
                "options": {"temperature": 0.7 if image is None else 0, "num_predict": budget,
                            "num_ctx": max(4096, budget+1024), "seed": random.randrange(2**31)}}
        if image is None:
            # This installed VL model ignores think=False in /api/chat. Its
            # actual Qwen template accepts a closed thinking prefix in raw mode.
            body.update(raw=True, prompt="<|im_start|>system\nReturn only the requested text, at most 80 English words.\n<|im_end|>\n"
                + "<|im_start|>user\n" + instruction + "\n<|im_end|>\n<|im_start|>assistant\n<think>\n</think>\n\n")
            endpoint = "generate"
        else:
            body['messages'] = [message]
            endpoint = "chat"
        request = urllib.request.Request("http://127.0.0.1:11434/api/" + endpoint, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=300) as response:
            answer = json.load(response)
        text = (answer.get("response", "") if image is None else answer.get("message", {}).get("content", "")).strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        if text and "<think>" not in text and answer.get("done_reason") != "length":
            return text
    raise RuntimeError("Description locale vide ou incomplète après deux budgets de génération")


def refill(c, count, check=lambda: None):
    root = folders(c["module"])
    journal = root / "REAPPROVISIONNEMENT" / (time.strftime("%Y%m%d-%H%M%S") + ".json")
    plan = {"created_at": time.time(), "items": [], "errors": []}
    for i in range(count):
        check()
        item = {"status": "pending"}
        name = "auto_" + uuid.uuid4().hex[:12]
        try:
            brief = local_brief("Invent ONE new visually complex but physically coherent subject for a photorealistic image, "
                "with subtle geometry, materials, articulation or occlusion that generative models often get wrong. "
                "Vary subjects between people, animals and manufactured objects, without choosing from a fixed list. "
                "Return ONLY a concise English image prompt. Single isolated subject, entire subject visible, neutral background.")
            item['prompt'] = brief
            # Explicitly selected external references, otherwise local FLUX synthesis.
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


def tasks_from_queue(c, task_dir, check=lambda: None, progress=None):
    from PIL import Image
    if c.get('curriculum_version') in {'radical-v2','radical-v3'}:
        from .challenge_curriculum import prepare_visual
        return prepare_visual(c,task_dir,check,progress=progress)
    count = c["train_tasks"] + c["eval_tasks"]
    task_dir = Path(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    if c["module"] == "image":
        # Image generation needs text prompts, not fabricated reference photos.
        prompts = [
            "A watchmaker repairing an open pocket watch, both hands visible, tiny brass gears, soft studio light",
            "A glass teapot pouring amber tea into a porcelain cup, physically consistent transparent surfaces",
            "A red cargo bicycle with two wheels and a wicker basket, complete side view, neutral background",
            "A snowy pine branch above a dark lake, crisp needles and natural reflections",
            "A black violin resting beside its bow, four strings and precise wooden curves",
            "A ceramic artist shaping a vase on a wheel, anatomically coherent hands and wet clay",
            "A complete articulated brass scorpion, detailed joints, raised curved tail, isolated studio photograph",
            "A gothic blue crystal cathedral, carved buttresses, symmetric windows, architectural photograph",
            "A striped cat sleeping inside a woven basket, coherent paws and soft fur",
            "A transparent perfume bottle with a metal cap and embossed flowers, product photograph",
            "An antique wooden sailing ship model, rigging and folded sails, entire object visible",
            "A feathered owl opening both wings, coherent feathers, complete silhouette"]
        import random
        random.Random(c.get('audit_partition_seed',c["seed"])).shuffle(prompts)
        if c.get("prompt"):
            prompts[0] = c["prompt"]
        while len(prompts) < count:
            check()
            prompts.append(local_brief("Invent one physically coherent, difficult photographic image prompt; return only the prompt."))
        return [{"id":f"image_{i:03d}","prompt":p,"origin":"synthetic_prompt"} for i,p in enumerate(prompts[:count])]
    root = folders(c["module"])
    candidates = []
    def collect():
        items = []
        seen_images, seen_prompts = set(), set()
        sources = sorted((root / "A_TRAITER").iterdir())
        if c.get("reference_image"):
            sources.insert(0, Path(c["reference_image"]).expanduser().resolve())
        for source in sources:
            if not source.is_file() or source.suffix.lower() not in FORMATS:
                continue
            sha = file_hash(source)
            metadata = read_json(source.with_suffix(".json"), {})
            prompt = (c.get("prompt") if str(source) == c.get("reference_image") else None) or metadata.get("prompt")
            if not prompt and source.with_suffix(".txt").is_file():
                prompt = source.with_suffix(".txt").read_text().strip()
            if not prompt:
                prompt = local_brief("Describe only the visible object's geometry and materials in English.", source)
            signature = " ".join(prompt.split()).casefold()
            if sha in seen_images or signature in seen_prompts:
                continue
            seen_images.add(sha); seen_prompts.add(signature)
            items.append((source, sha, prompt))
        return items
    candidates = collect()
    if len(candidates) < count and c.get("auto_refill"):
        refill(c, count-len(candidates), check)
        candidates = collect()
    if len(candidates) < count:
        raise ValueError(f"Références 3D distinctes insuffisantes : {len(candidates)}/{count}. Ajouter des images décrites dans {root / 'A_TRAITER'}.")
    tasks = []
    for i, (source, sha, prompt) in enumerate(candidates[:count]):
        check()
        destination = task_dir / (sha + ".png")
        with Image.open(source) as im:
            im.convert("RGBA" if "A" in im.getbands() else "RGB").save(destination)
        task = {"id":f"photo_{sha[:16]}","prompt":prompt,"image":str(destination),
                "queue_source":str(source),"queue_sha256":sha,"origin":"local_reference"}
        tasks.append(task)
        atomic_json(destination.with_suffix(".json"), task)
    # Release idle ComfyUI weights after creating this batch's references.
    # Never interrupt an active or pending generation from another UI session.
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=5) as response:
            queue = json.load(response)
        if not queue.get("queue_running") and not queue.get("queue_pending"):
            request = urllib.request.Request("http://127.0.0.1:8188/free", data=json.dumps({"unload_models": True, "free_memory": True}).encode(), headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(request, timeout=15):
                pass
    except (OSError, ValueError):
        pass
    from .curriculum import validate_tasks
    return validate_tasks(tasks, c)


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
