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
    wanted = [c["module"]]
    if c["module"] in {"3d", "image"}:
        wanted.append("clip")
    if c["module"] == "3d":
        wanted.append("image")
    if c["module"] == "audio":
        wanted.append("asr")
    paths = {k: local_snapshot(c["models"][k]) for k in wanted}
    if c["module"] == "image":
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
            self.adapter = LowRankAdapter(model, self.c["rank"], self.c["max_layers"], self.c["seed"])
        else:
            self.adapter = WeightSubspace(model, self.c["rank"], self.c["max_layers"], self.c["seed"])

    def close(self):
        self.adapter.close()
        gc.collect()
        torch.cuda.empty_cache()


class CodeBackend(Backend):
    suffix = ".py"

    def __init__(self, c, paths):
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        self.c = c
        self.tokenizer = AutoTokenizer.from_pretrained(paths["code"], local_files_only=True)
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                   bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
        self.model = AutoModelForCausalLM.from_pretrained(paths["code"], local_files_only=True,
            quantization_config=quant, device_map={"": 0}, torch_dtype=torch.bfloat16,
            attn_implementation="sdpa").eval()
        self.attach(self.model)

    def chat(self, messages, seed, max_tokens=None):
        seed_all(seed)
        g = self.c["generation"]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                    enable_thinking=False)
        tokens = self.tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.inference_mode():
            output = self.model.generate(**tokens, max_new_tokens=max_tokens or g["max_new_tokens"],
                do_sample=True, temperature=g["temperature"], top_p=g["top_p"],
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

    def prepare_tasks(self, root, check, sandbox):
        tasks = []
        self.adapter.enabled = False
        total = self.c["train_tasks"] + self.c["eval_tasks"]
        import random
        for i in range(total):
            check()
            if self.c["module"] in {"cyber", "cowork", "conversation"}:
                task = {"id": f"task_{i:03d}",
                        "prompt": "Write a bash script that finds all files in /tmp ending in .log, extracts lines containing 'ERROR', and saves them to /tmp/errors.txt.",
                        "expected_output": "SUCCESS",
                        "setup_script": "mkdir -p /tmp; echo 'ERROR 1' > /tmp/1.log; echo 'INFO' > /tmp/2.log; echo 'ERROR 2' > /tmp/3.log",
                        "reference": "grep -h 'ERROR' /tmp/*.log > /tmp/errors.txt && echo 'SUCCESS'",
                        "origin": "hardcoded_complex_bypass"}
            else:
                task = {"id": f"task_{i:03d}",
                        "prompt": "Write a Python function named `solve` that takes a list of integers and returns the sum of all even numbers.",
                        "function": "solve",
                        "cases": [{"args": [[1, 2, 3, 4]]}, {"args": [[]]}, {"args": [[2, 2, -4]]},
                                  {"args": [[1, 3, 5]]}, {"args": [[0]]}, {"args": [[10, 20]]},
                                  {"args": [[-2, -4, 1]]}, {"args": [[100, 200, 300]]}],
                        "expected": [6, 0, 0, 0, 0, 30, -6, 600],
                        "reference": "def solve(arr):\n    return sum(x for x in arr if x % 2 == 0)",
                        "origin": "hardcoded_complex_bypass",
                        "mutant_rejected": True}
            tasks.append(task)
            atomic_json(root / f"task_{i:03d}.json", task)
        self.adapter.enabled = True
        return tasks

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
                remesh=False, verbose=False)
            glb.export(str(path))
        del mesh, glb
        gc.collect()
        torch.cuda.empty_cache()
        return str(path)


def make_backend(c, paths):
    return {"code": CodeBackend, "image": ImageBackend, "audio": AudioBackend, "3d": TrellisBackend}[c["module"]](c, paths)


def visual_tasks(c, root, check, paths):
    from .photo_queue import tasks_from_queue
    return tasks_from_queue(c, root, check)


def audio_tasks(c):
    from .photo_queue import folders, local_brief
    root = folders("audio")
    entries = list((root/"A_TRAITER").glob("*.txt"))
    n = c["train_tasks"] + c["eval_tasks"]
    tasks = []
    for i in range(n):
        prompt = entries[i].read_text().strip() if i < len(entries) else local_brief(
            "Invent one varied, natural French sentence for speech synthesis with a pronunciation difficulty. "
            "Return only the sentence, no introduction. Avoid repeating familiar example sentences.")
        tasks.append({"id": f"phrase_{i:03d}", "prompt": prompt, "language": "fr", "origin": "user_or_self_generated"})
    return tasks
