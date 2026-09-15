"""Trainable low-rank corrections. Original model parameters stay frozen."""
import json
import math
import os
from pathlib import Path
import torch
from safetensors.torch import load_file, save_file


class LowRankAdapter(torch.nn.Module):
    def __init__(self, model, rank=8, max_layers=8, seed=1):
        super().__init__()
        model.eval().requires_grad_(False)
        self.enabled, self.handles = True, []
        self.rank, self.seed = rank, seed
        choices = [(n, m) for n, m in model.named_modules() if isinstance(m, torch.nn.Linear)
                   and m.in_features >= 32 and m.out_features >= 32 and
                   not any(k in n for k in ("lm_head", "embed", "out_layer"))]
        indices = torch.linspace(0, len(choices) - 1, min(len(choices), max_layers)).long().tolist()
        if not indices:
            raise ValueError("Aucune couche compatible LoRA")
        self.names = [choices[i][0] for i in indices]
        self.a, self.b = torch.nn.ParameterList(), torch.nn.ParameterList()
        rng = torch.Generator().manual_seed(seed)
        for i in indices:
            name, layer = choices[i]
            self.a.append(torch.nn.Parameter(torch.randn(rank, layer.in_features, generator=rng) / math.sqrt(layer.in_features)))
            self.b.append(torch.nn.Parameter(torch.zeros(layer.out_features, rank)))
            self.handles.append(layer.register_forward_hook(self._hook(len(self.a) - 1)))
        self.reset_drift()

    def _hook(self, index):
        def hook(layer, args, out):
            if not self.enabled:
                return out
            x = args[0]
            delta = (x @ self.a[index].to(x).T) @ self.b[index].to(x).T / self.rank
            if not torch.is_grad_enabled():
                self.drift_sum += float(delta.float().square().mean() / (out.float().square().mean() + 1e-6))
                self.drift_count += 1
            return out + delta.to(out.dtype)
        return hook

    def reset_drift(self):
        self.drift_sum, self.drift_count = 0.0, 0

    @property
    def drift(self):
        return self.drift_sum / max(1, self.drift_count)

    def save(self, path):
        temporary = Path(path).with_suffix(".tmp.safetensors")
        save_file({k: v.detach().cpu().contiguous() for k, v in self.state_dict().items()}, str(temporary),
                  metadata={"kind": "aurora-lora-v1", "targets": json.dumps(self.names),
                            "rank": str(self.rank), "seed": str(self.seed)})
        os.replace(temporary, path)

    def load(self, path):
        from safetensors import safe_open
        with safe_open(str(path), framework="pt", device="cpu") as f:
            meta = f.metadata()
        if meta.get("kind") != "aurora-lora-v1" or json.loads(meta["targets"]) != self.names:
            raise ValueError("L'adaptateur LoRA ne correspond pas au modèle")
        tensors = load_file(str(path))
        if any(not torch.isfinite(t).all() for t in tensors.values()):
            raise ValueError("Poids non finis")
        self.load_state_dict(tensors, strict=True)

    def close(self):
        for handle in self.handles:
            handle.remove()


def is_lora(path):
    from safetensors import safe_open
    with safe_open(str(path), framework="pt", device="cpu") as f:
        return f.metadata().get("kind") == "aurora-lora-v1"
