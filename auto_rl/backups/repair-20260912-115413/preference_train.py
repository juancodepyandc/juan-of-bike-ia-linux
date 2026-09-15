"""DPO on synthetic code preferences and a flow-matching DPO surrogate for 3D.

Cloud training needs only the dense TRELLIS structural flow, not the rendering
CUDA extensions. Candidate selection still requires the full local mesh audit.
"""
from __future__ import annotations
import gc
import json
import os
import sys
import time
import types
from pathlib import Path
import torch
import torch.nn.functional as F
from safetensors.torch import load_file
from .lora import LowRankAdapter
from .storage import atomic_json


def dense_trellis(source_root, model_path):
    import torch.utils.checkpoint
    # A private namespace prevents importing optional mesh/voxel CUDA extensions.
    prefix = "aurora_dense_trellis"
    package = types.ModuleType(prefix)
    package.__path__ = [str(Path(source_root) / "trellis2")]
    sys.modules[prefix] = package
    models = types.ModuleType(prefix + ".models")
    models.__path__ = [str(Path(source_root) / "trellis2/models")]
    sys.modules[prefix + ".models"] = models
    utils = types.ModuleType(prefix + ".modules.utils")
    def convert_module_to(layer, dtype):
        if isinstance(layer, torch.nn.Linear):
            for p in layer.parameters():
                p.data = p.data.to(dtype)
    utils.convert_module_to = convert_module_to
    utils.manual_cast = lambda x, dtype: x if torch.is_autocast_enabled() else x.to(dtype)
    utils.str_to_dtype = lambda s: {"float16": torch.float16, "bfloat16": torch.bfloat16,
                                    "float32": torch.float32}[s]
    sys.modules[prefix + ".modules.utils"] = utils
    import importlib
    cls = importlib.import_module(prefix + ".models.sparse_structure_flow").SparseStructureFlowModel
    args = json.loads(Path(str(model_path) + ".json").read_text())["args"]
    args.update(use_checkpoint=True, dtype="float16")
    model = cls(**args)
    model.load_state_dict(load_file(str(model_path) + ".safetensors"), strict=True)
    return model.eval().requires_grad_(False).to("cuda")


def train_preferences(c, records, input_root, output, epochs, seconds, callback, check=lambda: None):
    torch.set_num_threads(4)
    os.environ["ATTN_BACKEND"] = "sdpa"
    root, output = Path(input_root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + seconds
    device_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    if c["module"] == "3d":
        model = dense_trellis(c["trellis_root"], c["training_model_path"])
        adapter = LowRankAdapter(model, c["rank"], c["max_layers"], c["seed"]).to("cuda")
        tokenizer = None
    elif c["module"] == "code":
        from .backends import CodeBackend
        backend = CodeBackend(c, {"code": c["training_model_path"]})
        model, adapter, tokenizer = backend.model, backend.adapter.to("cuda"), backend.tokenizer
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.config.use_cache = False
    else:
        raise ValueError("Ce formateur de préférences attend 3d ou code")
    if (root / "initial.safetensors").exists():
        adapter.load(root / "initial.safetensors")
    if not records:
        raise ValueError("Aucune préférence mesurée : entraînement interdit")
    train = [r for r in records if r["split"] == "train"]
    validation = [r for r in records if r["split"] == "validation"]
    if not train or not validation:
        raise ValueError("Préférences d'apprentissage et de validation distinctes requises")
    optimizer = torch.optim.AdamW(adapter.parameters(), lr=c["train_learning_rate"], weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda", enabled=device_dtype == torch.float16)
    history, best_loss, best_epoch = [], float("inf"), 0

    def code_logp(record, key):
        prompt = tokenizer.apply_chat_template([
            {"role": "system", "content": "Write correct Python. Return only the complete Python code, without examples or tests."},
            {"role": "user", "content": record["prompt"]}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)[-384:]
        response_ids = tokenizer.encode(record[key], add_special_tokens=False)[:512] + [tokenizer.eos_token_id]
        ids = torch.tensor([prompt_ids + response_ids], device="cuda")
        logits = model(input_ids=ids, use_cache=False).logits[:, len(prompt_ids)-1:-1]
        labels = ids[:, len(prompt_ids):]
        # Fused cross entropy avoids a retained float32 vocabulary log-softmax.
        nll = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1), reduction="sum")
        return -nll.float()

    def loss_for(record, seed):
        torch.manual_seed(seed)
        if c["module"] == "code":
            with torch.no_grad():
                adapter.enabled = False
                ref_chosen = code_logp(record, "chosen")
                ref_rejected = code_logp(record, "rejected")
            adapter.enabled = True
            chosen = code_logp(record, "chosen")
            rejected = code_logp(record, "rejected")
            preference_logit = c["dpo_beta"] * ((chosen-ref_chosen) - (rejected-ref_rejected))
            anchor = ((chosen-ref_chosen) / 512).square()
        else:
            data = load_file(str(root / record["tensors"]))
            chosen_z, rejected_z = data["chosen"].cuda(), data["rejected"].cuda()
            cond = data["cond"].cuda()
            t = torch.rand((1,), device="cuda").clamp(0.05, 0.95)
            noise = torch.randn_like(chosen_z)
            sigma = 1e-5
            def sample(z):
                x = (1-t) * z + (sigma + (1-sigma)*t) * noise
                target = (1-sigma) * noise - z
                return x, target
            chosen_x, chosen_target = sample(chosen_z)
            rejected_x, rejected_target = sample(rejected_z)
            with torch.no_grad():
                adapter.enabled = False
                ref_c = model(chosen_x, t*1000, cond).detach()
                ref_r = model(rejected_x, t*1000, cond).detach()
                ref_c_loss = F.mse_loss(ref_c.float(), chosen_target)
                ref_r_loss = F.mse_loss(ref_r.float(), rejected_target)
            adapter.enabled = True
            current_c = model(chosen_x, t*1000, cond)
            current_r = model(rejected_x, t*1000, cond)
            c_loss = F.mse_loss(current_c.float(), chosen_target)
            r_loss = F.mse_loss(current_r.float(), rejected_target)
            preference_logit = c["dpo_beta"] * ((ref_c_loss-c_loss) - (ref_r_loss-r_loss))
            anchor = F.mse_loss(current_c.float(), ref_c.float()) + F.mse_loss(current_r.float(), ref_r.float())
        return F.softplus(-preference_logit) + c["anchor_penalty"] * anchor

    def validate_current():
        with torch.no_grad(), torch.autocast("cuda", dtype=device_dtype):
            return sum(float(loss_for(r, 7281+i)) for i, r in enumerate(validation)) / len(validation)

    try:
        initial_loss = validate_current()
        best_loss = initial_loss
        adapter.save(output / "candidate.safetensors")
        for epoch in range(1, epochs + 1):
            check()
            if time.monotonic() >= deadline:
                break
            epoch_losses = []
            for i, record in enumerate(train):
                check()
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast("cuda", dtype=device_dtype):
                    loss = loss_for(record, c["seed"] + epoch * 1000 + i)
                if not torch.isfinite(loss):
                    raise RuntimeError("Loss non finie : candidat non publiable")
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(adapter.parameters(), 1.0, error_if_nonfinite=True)
                scaler.step(optimizer)
                scaler.update()
                epoch_losses.append(float(loss.detach()))
            validation_loss = validate_current()
            if validation_loss < best_loss - 1e-6:
                best_loss, best_epoch = validation_loss, epoch
                adapter.save(output / "candidate.safetensors")
            row = {"epoch": epoch, "loss": sum(epoch_losses)/len(epoch_losses),
                   "validation_loss": validation_loss, "best_epoch": best_epoch,
                   "peak_vram_gb": torch.cuda.max_memory_allocated()/2**30}
            history.append(row)
            atomic_json(output / "training.json", history)
            callback(row)
            if epoch % c["checkpoint_every"] == 0:
                adapter.save(output / "latest.safetensors")
                temp = output / "optimizer.tmp.pt"
                torch.save({"optimizer": optimizer.state_dict(), "scaler": scaler.state_dict(), "epoch": epoch}, temp)
                os.replace(temp, output / "optimizer.pt")
            # Once validation has plateaued, more epochs primarily risk overfitting.
            if epoch - best_epoch >= 100:
                break
        if not history:
            raise RuntimeError("Aucune époque complète avant la limite")
        metrics = {"completed_epochs": len(history), "requested_epochs": epochs, "best_epoch": best_epoch,
                   "initial_validation_loss": initial_loss, "best_validation_loss": best_loss,
                   "training_gpu": torch.cuda.get_device_name(0), "training_dtype": str(device_dtype),
                   "train_pairs": len(train), "validation_pairs": len(validation),
                   "algorithm": "code_DPO" if c["module"] == "code" else "flow_matching_DPO_surrogate",
                   "note": "La loss de validation ne constitue pas une mesure de qualité des sorties finales."}
        atomic_json(output / "training_metrics.json", metrics)
        return metrics
    finally:
        adapter.close()
        del model, adapter, optimizer
        gc.collect()
        torch.cuda.empty_cache()
