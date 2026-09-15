"""Low-rank weight subspace optimized by antithetic evolution strategies.

Only coefficients are learned. A/B bases are deterministic and frozen. This is
NOT full LoRA SGD or PPO; inference consumes the learned delta W = B diag(c) A.
The original tensors are never modified, even temporarily.
"""
from __future__ import annotations

import math
import torch
from safetensors.torch import load_file, save_file


class WeightSubspace:
    def __init__(self, model, rank=4, max_layers=8, seed=1, targets=None):
        self.layers, self.handles = [], []
        self.enabled = True
        self.drift_sum, self.drift_count = 0.0, 0
        model.eval().requires_grad_(False)
        candidates = [(n, m) for n, m in model.named_modules()
                      if isinstance(m, torch.nn.Linear) and m.in_features >= 32 and m.out_features >= 32
                      and not any(s in n for s in ("lm_head", "embed", "out_layer"))]
        if targets:
            candidates = [(n, m) for n, m in candidates if n in targets]
            if [n for n, _ in candidates] != targets:
                raise ValueError("Les couches du modèle ne correspondent pas à l'adaptateur")
        else:
            if not candidates:
                raise ValueError("Aucune couche linéaire compatible trouvée")
            indices = torch.linspace(0, len(candidates) - 1, min(max_layers, len(candidates))).long().tolist()
            candidates = [candidates[i] for i in indices]
        g = torch.Generator().manual_seed(seed)
        for index, (name, layer) in enumerate(candidates):
            # Expected activation delta scales with c, independently of width.
            a = torch.randn(rank, layer.in_features, generator=g) / math.sqrt(layer.in_features)
            b = torch.randn(layer.out_features, rank, generator=g) / math.sqrt(rank)
            entry = {"name": name, "a": a, "b": b, "c": torch.zeros(rank), "cache": None}
            self.layers.append(entry)
            self.handles.append(layer.register_forward_hook(self._hook(entry)))
        self.rank, self.seed = rank, seed

    def _hook(self, entry):
        def apply(layer, args, out):
            if not self.enabled:
                return out
            x = args[0]
            if not isinstance(x, torch.Tensor) or not isinstance(out, torch.Tensor):
                raise TypeError("Cette couche n'accepte pas l'adaptateur dense")
            key = (x.device, x.dtype)
            if entry["cache"] is None or entry["cache"][0] != key:
                entry["cache"] = (key, entry["a"].to(x), entry["b"].to(x), entry["c"].to(x))
            _, a, b, c = entry["cache"]
            delta = ((x @ a.T) * c) @ b.T
            # Local activation drift, explicitly not a distributional KL.
            self.drift_sum += float(delta.float().square().mean() / (out.float().square().mean() + 1e-6))
            self.drift_count += 1
            return out + delta.to(out.dtype)
        return apply

    def vector(self):
        return torch.cat([e["c"] for e in self.layers]).clone()

    def set_vector(self, vector):
        if vector.numel() != len(self.layers) * self.rank or not torch.isfinite(vector).all():
            raise ValueError("Coefficients invalides")
        for i, e in enumerate(self.layers):
            e["c"] = vector[i * self.rank:(i + 1) * self.rank].float().cpu().clone()
            e["cache"] = None
        self.reset_drift()

    def reset_drift(self):
        self.drift_sum, self.drift_count = 0.0, 0

    @property
    def drift(self):
        return self.drift_sum / max(1, self.drift_count)

    def save(self, path):
        tensors = {}
        for i, e in enumerate(self.layers):
            for key in ("a", "b", "c"):
                tensors[f"{i}.{key}"] = e[key].contiguous()
        import json
        import os
        from pathlib import Path
        tmp = Path(path).with_suffix(".tmp.safetensors")
        save_file(tensors, str(tmp), metadata={"kind": "aurora-weight-subspace-v1",
                  "targets": json.dumps([e["name"] for e in self.layers]),
                  "rank": str(self.rank), "seed": str(self.seed)})
        os.replace(tmp, path)

    def load(self, path):
        from safetensors import safe_open
        import json
        with safe_open(str(path), framework="pt", device="cpu") as f:
            meta = f.metadata()
        if meta.get("kind") != "aurora-weight-subspace-v1" or json.loads(meta["targets"]) != [e["name"] for e in self.layers]:
            raise ValueError("Adaptateur incompatible avec ce modèle")
        tensors = load_file(str(path))
        for i, e in enumerate(self.layers):
            for key in ("a", "b", "c"):
                t = tensors[f"{i}.{key}"]
                if t.shape != e[key].shape or not torch.isfinite(t).all():
                    raise ValueError("Tenseur d'adaptateur invalide")
                e[key] = t
            e["cache"] = None

    def close(self):
        for h in self.handles:
            h.remove()


def es_gradient(noises, positive, negative, sigma):
    """Gradient ascent of expected reward under symmetric Gaussian noise."""
    noise = torch.stack(noises)
    differences = torch.tensor(positive) - torch.tensor(negative)
    return (differences[:, None] * noise).mean(0) / (2 * sigma)


def project(vector, radius):
    return vector * min(1.0, radius / max(float(vector.norm()), 1e-12))
