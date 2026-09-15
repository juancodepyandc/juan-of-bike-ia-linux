from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import numpy as np

from .sandbox import Sandbox


def result(score, metrics, valid=True, reasons=None, limitations=None):
    values = [v for v in metrics.values() if isinstance(v, (int, float))]
    if not math.isfinite(float(score)) or any(not math.isfinite(float(v)) for v in values):
        return {"score": 0.0, "valid": False, "metrics": {}, "reasons": ["Mesure non finie"], "limitations": []}
    return {"score": float(np.clip(score, 0, 1)), "valid": bool(valid),
            "metrics": metrics, "reasons": reasons or [], "limitations": limitations or []}


class ClipJudge:
    def __init__(self, path, aesthetic_path=None):
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self.torch = torch
        self.model = CLIPModel.from_pretrained(path, local_files_only=True).eval().requires_grad_(False).cpu()
        self.processor = CLIPProcessor.from_pretrained(path, local_files_only=True)
        self.aesthetic = None
        self.last_aesthetic = []
        if aesthetic_path:
            from safetensors.torch import load_file
            self.aesthetic = torch.nn.Linear(512, 1).eval().requires_grad_(False)
            self.aesthetic.load_state_dict(load_file(aesthetic_path))

    def scores(self, images, prompt):
        batch = self.processor(text=[prompt], images=images, return_tensors="pt", padding=True, truncation=True)
        with self.torch.inference_mode():
            out = self.model(**batch)
            cosine = out.image_embeds @ out.text_embeds.T
            if self.aesthetic is not None:
                self.last_aesthetic = self.aesthetic(out.image_embeds).flatten().tolist()
        return cosine[:, 0].clamp(0, 1).tolist()


class ImageJudge:
    def __init__(self, clip):
        self.clip = clip

    def score(self, artifact, task):
        from PIL import Image
        with Image.open(artifact) as im:
            image = im.convert("RGB")
        rgb = np.asarray(image, dtype=np.float32) / 255
        gray = rgb.mean(-1)
        grad = (np.abs(np.diff(gray, axis=0)).mean() + np.abs(np.diff(gray, axis=1)).mean()) / 2
        contrast = float(gray.std())
        alignment = float(self.clip.scores([image], task["prompt"])[0])
        aesthetic = float(self.clip.last_aesthetic[0])
        blank = contrast < 0.012
        clipping = float(((rgb <= 0.002) | (rgb >= 0.998)).mean())
        technical = min(1, contrast / 0.15) * min(1, grad / 0.015)
        return result(0.6 * alignment + 0.3 * np.clip(aesthetic / 10, 0, 1) + 0.1 * technical,
                      {"clip_cosine": alignment, "contrast": contrast, "edge_energy": float(grad),
                       "extreme_pixels": clipping, "laion_aesthetic_0_10": aesthetic}, not blank,
                      ["Image quasi uniforme"] if blank else [],
                      ["CLIP mesure l'alignement global, pas l'anatomie ni le comptage.",
                       "LAION prédit une préférence esthétique moyenne, pas l'absence d'artefacts."])


class MeshJudge:
    def __init__(self, clip, views=4, size=256):
        self.clip, self.views, self.size = clip, views, size

    def score(self, artifact, task):
        import trimesh
        from PIL import Image
        mesh = trimesh.load(artifact, force="mesh", process=False)
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0 or not np.isfinite(mesh.vertices).all():
            return result(0, {}, False, ["Maillage vide ou sommets invalides"])
        # Weld only a copy for topology analysis; texture seams are not holes.
        topo = mesh.copy()
        topo.merge_vertices(merge_tex=True, merge_norm=True)
        counts = np.bincount(topo.edges_unique_inverse)
        nonmanifold = float((counts > 2).mean())
        boundary = float((counts == 1).mean())
        # Do not materialize thousands of Trimesh objects. Each carries caches
        # and textures; a fragmented 100k-face mesh exhausted 30 GiB of RAM.
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        adjacent = topo.face_adjacency
        graph = coo_matrix((np.ones(len(adjacent), dtype=np.uint8),
                            (adjacent[:, 0], adjacent[:, 1])),
                           shape=(len(topo.faces), len(topo.faces))).tocsr()
        component_count, labels = connected_components(graph, directed=False)
        areas = np.bincount(labels, weights=topo.area_faces, minlength=component_count)
        fragment = float(1 - areas.max() / max(areas.sum(), 1e-12)) if len(areas) else 1.0
        degenerate = float((topo.area_faces < max(float(topo.area), 1e-12) * 1e-12).mean())
        face_count=len(mesh.faces)
        # Blender must not coexist with retained trimesh textures/topology
        # caches. Keep just the measured scalars for the final score.
        del mesh,topo,graph,adjacent,counts,labels,areas
        import gc
        gc.collect()
        render_dir = Path(artifact).with_suffix("").with_name(Path(artifact).stem + "_views")
        blender = shutil.which("blender") or str(Path.home() / ".local/bin/blender")
        render_dir.mkdir(parents=True, exist_ok=True)
        with (render_dir / "blender.log").open("w") as log:
            run = subprocess.run([blender, "-b", "--factory-startup", "--disable-autoexec", "-t", "4",
                                  "--python", str(Path(__file__).with_name("render_mesh.py")), "--",
                                  str(Path(artifact).resolve()), str(render_dir.resolve()),
                                  str(self.views), str(self.size)], stdout=log, stderr=subprocess.STDOUT, timeout=240)
        if run.returncode:
            raise RuntimeError(f"Échec du rendu Blender : {render_dir / 'blender.log'}")
        rendered = sorted(render_dir.glob("view_*.png"))
        if len(rendered) != self.views:
            raise RuntimeError("Nombre de vues incomplet")
        images = []
        for p in rendered:
            with Image.open(p) as im:
                images.append(im.convert("RGB"))
        scores = self.clip.scores(images, task["prompt"])
        inter = json.loads((render_dir / "geometry.json").read_text())["self_intersections"]
        topology = max(0, 1 - 5 * nonmanifold - boundary - fragment - 5 * degenerate)
        if inter is not None:
            topology *= 1 / (1 + inter / max(1, face_count) * 20)
        metrics = {"nonmanifold_edge_fraction": nonmanifold, "boundary_edge_fraction": boundary,
                   "fragment_area_fraction": fragment, "degenerate_face_fraction": degenerate,
                   "self_intersections": inter, "clip_mean": float(np.mean(scores)),
                   "clip_worst_view": min(scores), "views": [str(p) for p in rendered],
                   "faces": face_count, "components": int(component_count)}
        valid = inter is not None and degenerate < 0.1 and nonmanifold < 0.1
        return result(0.45 * topology + 0.35 * np.mean(scores) + 0.2 * min(scores), metrics, valid,
                      [] if valid else ["Géométrie invalide ou intersections non évaluées"],
                      ["Des pièces séparées peuvent être intentionnelles.",
                       "Vues CLIP : alignement sémantique, sans preuve de structure ni de nombre de roues."])


def normalize_text(text):
    return " ".join(re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", text).lower()).split())


def word_error_rate(reference, hypothesis):
    a, b = normalize_text(reference).split(), normalize_text(hypothesis).split()
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j - 1] + (x != y)))
        row = new
    return row[-1] / max(1, len(a))


class AudioJudge:
    def __init__(self, asr_path):
        from faster_whisper import WhisperModel
        self.asr = WhisperModel(asr_path, device="cpu", compute_type="int8", cpu_threads=4,
                                local_files_only=True)

    def score(self, artifact, task):
        import soundfile as sf
        waveform, sr = sf.read(artifact, dtype="float32", always_2d=True)
        x = waveform.mean(1)
        if len(x) < sr // 5 or not np.isfinite(x).all():
            return result(0, {}, False, ["Signal trop court ou non fini"])
        clipping = float((np.abs(x) >= 0.999).mean())
        rms = float(np.sqrt(np.mean(x ** 2)))
        frame = max(1, int(sr * 0.02))
        power = np.array([np.mean(x[i:i + frame] ** 2) for i in range(0, len(x), frame)])
        low, high = np.percentile(power, [10, 90])
        # No clean reference: this is a dynamic-range proxy, NOT a true SNR.
        snr_proxy = float(10 * np.log10((high + 1e-10) / (low + 1e-10)))
        segments, _ = self.asr.transcribe(str(artifact), language=task.get("language", "fr"),
                                           beam_size=1, condition_on_previous_text=False)
        transcript = " ".join(s.text for s in segments)
        wer = word_error_rate(task["prompt"], transcript)
        clarity = max(0, 1 - wer)
        valid = rms > 0.001 and clipping < 0.02 and bool(normalize_text(transcript))
        return result(0.9 * clarity + 0.1 * max(0, 1 - clipping * 50),
                      {"wer": wer, "transcription": transcript, "clipping_fraction": clipping,
                       "rms": rms, "snr_proxy_db": snr_proxy, "duration_s": len(x) / sr}, valid,
                      [] if valid else ["Silence, saturation ou transcription vide"],
                      ["Le SNR exact est inconnu sans signal propre de référence.",
                       "Whisper peut commettre des erreurs de transcription."])


def values_equal(actual, expected):
    if type(actual) != type(expected) and not (type(actual) in (int, float) and type(expected) in (int, float)):
        return False
    if isinstance(expected, float):
        return math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-8)
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(values_equal(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(values_equal(actual[k], expected[k]) for k in expected)
    return actual == expected


class CodeJudge:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def score(self, artifact, task, attempts=1):
        code = Path(artifact).read_text()
        cases = task["cases"]
        if len(cases) < 6 or len(task["expected"]) != len(cases):
            return result(0, {}, False, ["Suite de tests incomplète"])
        executed = self.sandbox.python(code, task["function"], cases)
        got = executed["results"]
        passed = [isinstance(v, dict) and "value" in v and values_equal(v["value"], expected)
                  for v, expected in zip(got, task["expected"])]
        valid_execution = executed["exit_code"] == 0 and len(got) == len(cases)
        count = sum(passed) if valid_execution else 0
        failures = [{"input": cases[i], "expected": task["expected"][i], "actual": got[i]}
                    for i, ok in enumerate(passed) if not ok][:2]
        return result(count / len(cases) / max(1, attempts),
                      {"passed": count, "total": len(cases), "exit_code": executed["exit_code"],
                       "failed_examples": failures,
                       "attempts": attempts, "traceback": executed["stderr"] or
                       json.dumps([v for v in got if "error" in v], ensure_ascii=False)},
                      True, limitations=["Exercices synthétiques avec oracle indépendant ; couverture limitée aux cas testés."])


class ConversationJudge:
    def score(self, artifact, task, attempts=1):
        text = Path(artifact).read_text().strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        try:
            got = json.loads(text)
        except (ValueError, TypeError):
            got = None
        expected = task["expected_json"]["answers"]
        answers = got.get("answers", []) if isinstance(got, dict) else []
        if not isinstance(answers, list):
            answers = []
        passed = sum(values_equal(a, b) for a, b in zip(answers, expected)) if len(answers) == len(expected) else 0
        total=len(expected)
        verification=task['expected_json'].get('verification')
        if verification is not None:
            total+=1
            passed+=int(isinstance(got,dict) and values_equal(got.get('verification'),verification))
        return result(passed / total, {"passed": passed, "total": total, "json_valid": got is not None},
                      True, limitations=["Raisonnement structuré vérifié ; ce score ne mesure pas la qualité générale d'une conversation."])


class AgentJudge:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def score(self, artifact, task, attempts=1):
        script = Path(artifact).read_text()
        setup = task.get("setup_script", "")
        # Run in bash sandbox
        executed = self.sandbox.bash(script, setup)
        
        # Cyber/Cowork validation: exit code 0 is a base requirement.
        # An optional expected string in stdout can also be checked.
        valid_execution = executed["exit_code"] == 0
        expected_output = task.get("expected_output", "")
        
        passed = valid_execution
        if expected_output and expected_output not in executed["stdout"]:
            passed = False
            
        return result(1.0 / max(1, attempts) if passed else 0.0,
                      {"exit_code": executed["exit_code"], "attempts": attempts,
                       "stdout_preview": executed["stdout"][:200],
                       "stderr": executed["stderr"]},
                      True, limitations=["Sandbox isolée : aucune action réelle sur l'hôte."])


def make_judge(config, paths):
    module = config["module"]
    if module in {"video", "animation"}:
        from .temporal_judges import VideoJudge, AnimationJudge
        return VideoJudge(ClipJudge(paths["clip"])) if module == "video" else AnimationJudge()
    if module in {"code", "cyber", "cowork"}:
        sandbox = Sandbox(config["python_image"], config["sandbox_timeout"])
        sandbox.check()
        return CodeJudge(sandbox)
    if module in {"conversation", "learning"}:
        return ConversationJudge()
    if module == "audio":
        return AudioJudge(paths["asr"])
    clip = ClipJudge(paths["clip"], paths.get("aesthetic"))
    return MeshJudge(clip, config["render_views"], config["render_size"]) if module == "3d" else ImageJudge(clip)
