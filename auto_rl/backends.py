from __future__ import annotations

import gc
import json
import os
import random
import re
import sys
from pathlib import Path

import numpy as np
import torch

from .adapters import WeightSubspace
from .config import TEXT_MODULES
from .storage import atomic_json, digest


def local_snapshot(repo):
    if Path(repo).is_dir():
        return str(Path(repo).resolve())
    from huggingface_hub import snapshot_download
    caches = [Path.home() / ".cache/huggingface/hub",
              Path(__file__).resolve().parents[1] / "modele/huggingface/hub"]
    for cache in caches:
        try:
            return snapshot_download(repo, cache_dir=str(cache), local_files_only=True)
        except Exception:
            continue
    raise RuntimeError(f"Modèle absent du cache local : {repo}")


def resolve_paths(c):
    if c["module"] in {"video", "animation"}:
        from .temporal_backend import temporal_paths
        return temporal_paths(c)
    wanted = [c["module"]]
    if c["module"] in {"3d", "image"}:
        wanted.append("clip")
    if c["module"] == "3d":
        wanted.append("image")
    if c["module"] == "audio":
        wanted.append("asr")
    paths = {k: (str(Path(c["comfy_unet"]).resolve()) if k == "image" and c["module"] == "image" and c.get("trainer") == "surrogate_es" else local_snapshot(c["models"][k])) for k in wanted}
    if c["module"] == "image":
        if c.get("trainer") == "surrogate_es":
            if not Path(paths["image"]).is_file():
                raise RuntimeError("GGUF FLUX.2 absent : " + paths["image"])
            for key in ("comfy_clip", "comfy_vae"):
                source = Path(c[key]).resolve()
                if not source.is_file():
                    raise RuntimeError("Poids ComfyUI absents : " + str(source))
                paths[key] = str(source)
        elif not (Path(paths["image"]) / "model_index.json").is_file():
            raise RuntimeError("FLUX.2 installé au format ComfyUI/GGUF ; ce formateur requiert un pipeline Diffusers complet. Le modèle image actuel ne peut pas être entraîné par ce backend.")
        if not Path(c["aesthetic_weights"]).is_file():
            raise RuntimeError("Poids du juge esthétique absents : lancer scripts/setup_auto_rl.sh")
        paths["aesthetic"] = c["aesthetic_weights"]
    if c["module"] == "3d":
        for repo in ("microsoft/TRELLIS-image-large", "camenduru/dinov3-vitl16-pretrain-lvd1689m", "1038lab/RMBG-2.0"):
            paths[repo] = local_snapshot(repo)
    return paths


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed % (2 ** 32))
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False


def extract_code(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    matches = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    return matches[-1].strip() if matches else text


class Backend:
    suffix = ".txt"

    def attach(self, model):
        if self.c.get("trainer") == "preference_lora":
            from .lora import LowRankAdapter
            self.adapter = LowRankAdapter(model, self.c["rank"], self.c["max_layers"], self.c.get('adapter_seed',self.c["seed"]))
        else:
            self.adapter = WeightSubspace(model, self.c["rank"], self.c["max_layers"], self.c["seed"])

    def close(self):
        self.adapter.close()
        for name in ('model','pipe','last_latent'):
            if hasattr(self,name):setattr(self,name,None)
        gc.collect()
        torch.cuda.empty_cache()


class CodeBackend(Backend):
    suffix = ".py"

    def __init__(self, c, paths):
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        self.c = c
        self.tokenizer = AutoTokenizer.from_pretrained(paths[c["module"]], local_files_only=True)
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                   bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
        self.model = AutoModelForCausalLM.from_pretrained(paths[c["module"]], local_files_only=True,
            quantization_config=quant, device_map={"": 0}, torch_dtype=torch.bfloat16 if (torch.cuda.get_device_capability()[0] >= 8) else torch.float16,
            attn_implementation="sdpa").eval()
        self.attach(self.model)

    def chat(self, messages, seed, max_tokens=None):
        seed_all(seed)
        g = self.c["generation"]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                    enable_thinking=False)
        tokens = self.tokenizer(prompt, return_tensors="pt").to("cuda")
        sampling = ({"do_sample": True, "temperature": g["temperature"], "top_p": g["top_p"]}
                    if g["temperature"] > 0 else {"do_sample": False})
        with torch.inference_mode():
            output = self.model.generate(**tokens, max_new_tokens=max_tokens or g["max_new_tokens"],
                **sampling,
                pad_token_id=self.tokenizer.eos_token_id, use_cache=True)
        return self.tokenizer.decode(output[0, tokens.input_ids.shape[1]:], skip_special_tokens=True)

    def generate(self, task, seed, path, feedback=None):
        messages = [{"role": "system", "content": "Write correct Python. Return only the complete Python code, without examples or tests."},
                    {"role": "user", "content": task["prompt"]}]
        if feedback:
            messages.extend(feedback)
        text = self.chat(messages, seed)
        Path(path).write_text(extract_code(text))
        return str(path)

    def kl_to_base(self, task, artifact):
        """Exact next-token KL(base || adapter), on the last 32 sampled contexts."""
        text = task["prompt"] + "\n" + Path(artifact).read_text()
        tokens = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=1024).to("cuda")
        with torch.inference_mode():
            self.adapter.enabled = False
            ref = self.model(**tokens).logits[:, -32:].float().log_softmax(-1)
            self.adapter.enabled = True
            current = self.model(**tokens).logits[:, -32:].float().log_softmax(-1)
            value = (ref.exp() * (ref - current)).sum(-1).mean().clamp_min(0)
        return float(value)

    def prepare_tasks(self, root, check, sandbox=None):
        if self.c["module"] == "learning":
            from .learning_curriculum import build_tasks
        else:
            from .curriculum import build_tasks
        tasks = build_tasks(self.c)
        for task in tasks:
            check()
            atomic_json(root / (task["id"] + ".json"), task)
        return tasks


class ConversationBackend(CodeBackend):
    suffix = ".txt"

    def generate(self, task, seed, path, feedback=None):
        messages = [{"role": "system", "content": "Follow the instructions precisely. Return only the requested JSON."},
                    {"role": "user", "content": task["prompt"]}]
        if feedback:
            messages.extend(feedback)
        Path(path).write_text(self.chat(messages, seed))
        return str(path)


class ImageBackend(Backend):
    suffix = ".png"

    def __init__(self, c, paths, adapt=True):
        from diffusers import DiffusionPipeline
        self.c = c
        variant = {"variant": "fp16"} if list(Path(paths["image"]).rglob("*.fp16.safetensors")) else {}
        self.pipe = DiffusionPipeline.from_pretrained(paths["image"], torch_dtype=torch.float16,
                                                     local_files_only=True, use_safetensors=True, **variant).to("cuda")
        self.pipe.set_progress_bar_config(disable=True)
        self.pipe.enable_vae_slicing()
        if adapt:
            self.attach(self.pipe.unet if hasattr(self.pipe, "unet") else self.pipe.transformer)

    def generate(self, task, seed, path, feedback=None):
        g = self.c["generation"]
        seed_all(seed)
        with torch.inference_mode():
            image = self.pipe(prompt=task["prompt"], width=g["width"], height=g["height"],
                num_inference_steps=g["steps"], guidance_scale=g["guidance_scale"],
                num_images_per_prompt=1, generator=torch.Generator("cuda").manual_seed(seed)).images[0]
        image.save(path)
        return str(path)


class AudioBackend(Backend):
    suffix = ".wav"

    def __init__(self, c, paths):
        from kokoro import KModel, KPipeline
        self.c = c
        root = Path(paths["audio"])
        model = KModel(repo_id=c["models"]["audio"], config=str(root / "config.json"),
                       model=str(root / "kokoro-v1_0.pth")).eval().to("cuda")
        self.pipe = KPipeline(lang_code="f", model=model, device="cuda")
        self.voice = str(root / "voices" / (c["generation"]["voice"] + ".pt"))
        if not Path(self.voice).is_file():
            raise RuntimeError(f"Voix locale absente : {self.voice}")
        self.attach(model)

    def generate(self, task, seed, path, feedback=None):
        import soundfile as sf
        seed_all(seed)
        with torch.inference_mode():
            pieces = [item.audio.cpu().numpy() for item in self.pipe(task["prompt"], voice=self.voice,
                      speed=self.c["generation"]["speed"], split_pattern=r"\n+")]
        if not pieces:
            raise RuntimeError("Kokoro n'a produit aucun échantillon")
        sf.write(path, np.concatenate(pieces), 24000, subtype="PCM_16")
        return str(path)


class TrellisBackend(Backend):
    suffix = ".glb"

    def __init__(self, c, paths):
        self.c = c
        sys.path.insert(0, c["trellis_root"])
        os.environ.setdefault("ATTN_BACKEND", "xformers")
        os.environ.setdefault("SPCONV_ALGO", "native")
        os.environ.setdefault("CUDA_HOME", "/usr/local/cuda-12.8")
        os.environ["PATH"] = os.environ["CUDA_HOME"] + "/bin:" + os.environ.get("PATH", "")
        from trellis2.pipelines import Trellis2ImageTo3DPipeline
        self.pipe = Trellis2ImageTo3DPipeline.from_pretrained(paths["3d"])
        self.pipe.low_vram = True
        self.pipe.to(torch.device("cuda"))
        for model in self.pipe.models.values():
            model.eval().requires_grad_(False)
        # Real pretrained structural flow; textures/decoders remain frozen.
        self.attach(self.pipe.models["sparse_structure_flow_model"])
        self.last_latent = None
        original_sample = self.pipe.sparse_structure_sampler.sample
        def capture(model, noise, **kwargs):
            sampled = original_sample(model, noise, **kwargs)
            self.last_latent = {"latent": sampled.samples.detach().float().cpu(),
                                "cond": kwargs["cond"].detach().float().cpu()}
            return sampled
        self.pipe.sparse_structure_sampler.sample = capture

    def generate(self, task, seed, path, feedback=None):
        from PIL import Image
        import o_voxel
        seed_all(seed)
        g = self.c["generation"]
        with Image.open(task["image"]) as source:
            image = source.copy()
        with torch.inference_mode():
            mesh = self.pipe.run(image, seed=seed, pipeline_type=g["trellis_pipeline"],
                max_num_tokens=g["max_num_tokens"],
                sparse_structure_sampler_params={"steps": g["steps"]},
                shape_slat_sampler_params={"steps": g["steps"]},
                tex_slat_sampler_params={"steps": g["steps"]})[0]
            glb = o_voxel.postprocess.to_glb(vertices=mesh.vertices, faces=mesh.faces,
                attr_volume=mesh.attrs, coords=mesh.coords, attr_layout=mesh.layout,
                voxel_size=mesh.voxel_size, aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                decimation_target=g["decimation_target"], texture_size=g["texture_size"],
                remesh=bool(g.get("remesh", False)), verbose=False)
            glb.export(str(path))
        del mesh, glb
        gc.collect()
        torch.cuda.empty_cache()
        _limite_faces(path, int(g.get("judge_face_limit", 250000)),
                      int(g["decimation_target"]))
        return str(path)


def _limite_faces(path, limite, decimation_target):
    """Garde-fou: un maillage trop dense invalide l'audit ENTIER.

    `auto_rl/render_mesh.py:30-33` ne calcule les auto-intersections que si
    le maillage a au plus 250 000 faces; au-dela il renvoie `None`, et
    `judges.py:134` then rend la ligne `valid=False`
    (`inter is not None and ...`). Or `evaluation.py:29-35` exige que
    TOUTES les lignes soient valides: un seul maillage trop dense suffit a
    jeter un audit de 288 generations.

    `decimation_target` vaut 100 000 par defaut (`config.py:54`), donc la
    generation normale reste tres en dessous. Ce filet n'agit que si la
    decimation de o_voxel n'a pas tenu, et il est symetrique: les trois
    branches (base, champion, candidat) passent par le meme code, donc la
    comparaison reste equitable.
    """
    try:
        import trimesh
        m = trimesh.load(str(path), force="mesh", process=False)
        faces = len(getattr(m, "faces", []) or [])
    except Exception:  # noqa: BLE001
        return
    if faces <= limite:
        return
    try:
        m = m.simplify_quadric_decimation(face_count=max(limite // 2, 1000))
        m.export(str(path))
        print("[3d] maillage de %d faces > %d: decimation de secours appliquee"
              % (faces, limite), flush=True)
    except Exception as exc:  # noqa: BLE001
        # On ne pretend jamais avoir mesure ce qu'on n'a pas mesure: le
        # juge le juge refusera la ligne, et c'est correct.
        print("[3d] %d faces > %d et decimation impossible (%s): ligne d'audit "
              "invalideee par le juge" % (faces, limite, str(exc)[:80]), flush=True)


def make_backend(c, paths):
    if c["module"] in {"video", "animation"}:
        from .temporal_backend import VideoBackend, AnimationBackend
        return (VideoBackend if c["module"] == "video" else AnimationBackend)(c, paths)
    if c["module"] == "image" and c.get("trainer") == "surrogate_es":
        from .comfy_backend import ComfyImageBackend
        return ComfyImageBackend(c, paths)
    return {"code": CodeBackend, "cyber": CodeBackend, "cowork": CodeBackend, "conversation": ConversationBackend, "learning": ConversationBackend, "image": ImageBackend, "audio": AudioBackend, "3d": TrellisBackend}[c["module"]](c, paths)


def visual_tasks(c, root, check, paths, progress=None):
    from .photo_queue import tasks_from_queue
    return tasks_from_queue(c, root, check, progress=progress)


def audio_tasks(c):
    if c.get('curriculum_version') in {'radical-v2','radical-v3'}:
        from .challenge_curriculum import audio_briefs
        return audio_briefs(c)
    from .photo_queue import folders
    root = folders("audio")
    entries = sorted((root/"A_TRAITER").glob("*.txt"))
    prompts = [p.read_text().strip() for p in entries]
    prompts += [
        "Les chercheurs évaluent précisément les résultats de cette expérience.",
        "Hier, huit étudiants ont étudié les anciennes archives de la bibliothèque.",
        "Trois petits trains traversent tranquillement la plaine après la pluie.",
        "Veuillez vérifier chaque chiffre avant de confirmer votre réservation.",
        "Le chirurgien échange avec une jeune collègue au sujet du diagnostic.",
        "Au printemps, les hirondelles reviennent près des vieux chênes du village.",
        "Cette équation exige une distinction précise entre vitesse et accélération.",
        "Un magnifique paysage apparaît derrière les montagnes enneigées.",
        "La température diminuera progressivement au cours de la prochaine nuit.",
        "Quatre vingt dix neuf voyageurs attendent leur correspondance à la gare.",
        "Les enfants cueillent des groseilles et des framboises dans le jardin.",
        "Pourquoi faudrait il choisir immédiatement entre ces deux possibilités ?",
        "Si vous souhaitez poursuivre, veuillez sélectionner le bouton suivant.",
        "La synchronisation nécessite une connexion suffisamment stable.",
        "Nous enregistrerons votre message dès que le signal sonore retentira.",
        "Les vagues viennent doucement mourir sur les galets de la plage.",
        "Une cuillère de miel adoucira cette infusion de thym et de verveine.",
        "Le physicien distingue soigneusement les hypothèses des observations."
    ]
    prompts = list(dict.fromkeys(p for p in prompts if p))
    n = c["train_tasks"] + c["eval_tasks"]
    if c.get("prompt") and c["prompt"] not in prompts:
        prompts.insert(0,c["prompt"])
    if len(prompts) < n:
        raise ValueError(f"Ajouter des phrases distinctes dans {root / 'A_TRAITER'} : {len(prompts)}/{n}")
    random.Random(c.get('audit_partition_seed',c["seed"])).shuffle(prompts)
    return [{"id":f"phrase_{i:03d}","prompt":prompt,"language":"fr","origin":"synthetic_or_user_text"} for i,prompt in enumerate(prompts[:n])]
