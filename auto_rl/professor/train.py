"""Supervised LoRA / QLoRA fine-tuning of a real student on a targeted curriculum.

Only assistant tokens carry loss, prompts are rendered exactly as at inference,
a development split taken from the training pool selects the checkpoint, and a
wall-clock budget stops the run with an adapter already saved. Nothing here
decides whether the adapter is better: that is the examiner's job.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import time
from pathlib import Path

from .inference import ATTENTION_TARGETS, LORA_TARGETS
from .records import atomic_json, file_hash, rank

DEFAULTS = {"rank": 16, "alpha": 32, "dropout": 0.05, "learning_rate": 2e-4, "epochs": 2.0, "batch_size": 4,
            "accumulate": 4, "max_tokens": 1024, "warmup_ratio": 0.05, "dev_share": 0.05, "eval_every": 50,
            "patience": 4, "attention_only": False, "seed": 20261111, "max_grad_norm": 1.0}


def encode(student, items, max_tokens):
    """Tokenise ``prompt + answer + end-of-turn``; over-long examples are dropped, never truncated."""
    tokenizer, end = student.tokenizer, student.end_text()
    encoded, dropped = [], 0
    for item in items:
        prompt = tokenizer(student.render(item["messages"]), add_special_tokens=False)["input_ids"]
        answer = tokenizer(item["target"] + end, add_special_tokens=False)["input_ids"]
        if len(prompt) + len(answer) > max_tokens or not answer:
            dropped += 1
            continue
        encoded.append({"id": item["id"], "skill": item["skill"], "prompt": prompt, "answer": answer})
    return encoded, dropped


def batches(encoded, batch_size, seed):
    """Length-sorted batches in a seeded order: less padding, reproducible runs."""
    ordered = sorted(encoded, key=lambda e: len(e["prompt"]) + len(e["answer"]))
    groups = [ordered[i:i + batch_size] for i in range(0, len(ordered), batch_size)]
    random.Random(seed).shuffle(groups)
    return groups


def collate(group, pad_id, torch, device):
    width = max(len(e["prompt"]) + len(e["answer"]) for e in group)
    ids = torch.full((len(group), width), pad_id, dtype=torch.long)
    mask = torch.zeros((len(group), width), dtype=torch.long)
    labels = torch.full((len(group), width), -100, dtype=torch.long)
    for row, example in enumerate(group):
        tokens = example["prompt"] + example["answer"]
        ids[row, :len(tokens)] = torch.tensor(tokens)
        mask[row, :len(tokens)] = 1
        labels[row, len(example["prompt"]):len(tokens)] = torch.tensor(example["answer"])
    return ids.to(device), mask.to(device), labels.to(device)


def lora_targets(model, attention_only):
    """Projection layers that really exist in this model, outside any vision tower."""
    wanted = ATTENTION_TARGETS if attention_only else LORA_TARGETS
    present = {name.rsplit(".", 1)[-1] for name, module in model.named_modules()
               if hasattr(module, "weight") and getattr(module.weight, "ndim", 0) == 2}
    found = [name for name in wanted if name in present]
    return found or "all-linear"


def _dev_loss(model, groups, pad_id, torch, device, autocast):
    total, count = 0.0, 0
    model.eval()
    with torch.no_grad():
        for group in groups:
            ids, mask, labels = collate(group, pad_id, torch, device)
            with autocast():
                loss = model(input_ids=ids, attention_mask=mask, labels=labels).loss
            tokens = int((labels != -100).sum())
            total += loss.item() * tokens
            count += tokens
    model.train()
    return total / max(1, count)


def train(student, items, folder, *, config=None, budget_seconds=None, progress=None):
    """Fine-tune ``student`` in place and save the selected adapter under ``folder/adapter``."""
    import torch
    from peft import LoraConfig, get_peft_model
    settings = {**DEFAULTS, **(config or {})}
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if student.adapter is not None:
        raise RuntimeError("Train from the base model: detach the current adapter first")
    torch.manual_seed(settings["seed"])
    started = time.monotonic()
    encoded, dropped = encode(student, items, settings["max_tokens"])
    if len(encoded) < 8:
        raise ValueError(f"Only {len(encoded)} usable training examples ({dropped} exceeded {settings['max_tokens']} tokens)")
    ordered = sorted(encoded, key=lambda e: rank(e["id"], "aurora-dev-split"))
    dev_count = min(max(4, int(len(ordered) * settings["dev_share"])), 400)
    dev, fit = ordered[:dev_count], ordered[dev_count:]

    model = student.model
    cuda = torch.cuda.is_available()
    if student.four_bit:
        from peft import prepare_model_for_kbit_training
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    elif cuda:
        model.gradient_checkpointing_enable()
    model.config.use_cache = False
    targets = lora_targets(model, settings["attention_only"])
    lora = {"r": settings["rank"], "lora_alpha": settings["alpha"], "lora_dropout": settings["dropout"],
            "target_modules": targets, "task_type": "CAUSAL_LM", "bias": "none"}
    try:
        model = get_peft_model(model, LoraConfig(**lora, exclude_modules=r".*(visual|vision|audio).*"))
    except TypeError:                                    # older peft without exclude_modules
        model = get_peft_model(model, LoraConfig(**lora))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_parameters = sum(p.numel() for p in model.parameters())
    device = model.get_input_embeddings().weight.device
    pad_id = student.tokenizer.pad_token_id

    fp16 = cuda and student.dtype == torch.float16

    def autocast():
        return torch.autocast("cuda", dtype=student.dtype) if cuda else torch.autocast("cpu", enabled=False)
    scaler = None
    if fp16:
        try:
            scaler = torch.amp.GradScaler("cuda")
        except (AttributeError, TypeError):              # torch < 2.3
            scaler = torch.cuda.amp.GradScaler()
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=settings["learning_rate"],
                                  weight_decay=0.0)
    per_epoch = math.ceil(len(fit) / settings["batch_size"])
    planned = max(1, math.ceil(per_epoch * settings["epochs"] / settings["accumulate"]))
    warmup = max(1, int(planned * settings["warmup_ratio"]))

    def rate(step):
        if step < warmup:
            return (step + 1) / warmup
        progress_ratio = min(1.0, (step - warmup) / max(1, planned - warmup))
        return 0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * progress_ratio))
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, rate)
    dev_groups = batches(dev, settings["batch_size"], settings["seed"])
    log_path = folder / "training_log.jsonl"
    best = {"loss": None, "step": 0}
    initial_dev = _dev_loss(model, dev_groups, pad_id, torch, device, autocast)
    history = [{"step": 0, "dev_loss": initial_dev, "elapsed_seconds": round(time.monotonic() - started, 1)}]
    step, micro, running, stale, stopped = 0, 0, None, 0, "completed"
    seen_batches = skipped_batches = 0
    out_of_memory = getattr(torch.cuda, "OutOfMemoryError", RuntimeError) if cuda else ()
    model.train()
    optimizer.zero_grad(set_to_none=True)
    epoch = 0
    with log_path.open("w", encoding="utf-8") as log:
        log.write(json.dumps(history[0]) + "\n")
        while step < planned and stopped == "completed":
            for group in batches(fit, settings["batch_size"], settings["seed"] + epoch):
                seen_batches += 1
                try:
                    ids, mask, labels = collate(group, pad_id, torch, device)
                    with autocast():
                        loss = model(input_ids=ids, attention_mask=mask, labels=labels).loss
                    if not torch.isfinite(loss):
                        stopped = "non_finite_loss"
                        break
                    scaled = loss / settings["accumulate"]
                    (scaler.scale(scaled) if fp16 else scaled).backward()
                except out_of_memory:
                    # One over-long batch must not lose the run: drop its partial gradients and go on.
                    # Too many of them means the settings do not fit this GPU, which is an error.
                    optimizer.zero_grad(set_to_none=True)
                    torch.cuda.empty_cache()
                    micro -= micro % settings["accumulate"]
                    skipped_batches += 1
                    if skipped_batches > 10 and skipped_batches > 0.2 * seen_batches:
                        stopped = "out_of_memory"
                        break
                    continue
                value = loss.detach().item()
                running = value if running is None else 0.95 * running + 0.05 * value
                micro += 1
                if micro % settings["accumulate"]:
                    continue
                if fp16:
                    scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_((p for p in model.parameters() if p.requires_grad), settings["max_grad_norm"])
                if fp16:
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                step += 1
                elapsed = time.monotonic() - started
                out_of_time = budget_seconds is not None and elapsed > budget_seconds
                if step % settings["eval_every"] == 0 or step == planned or out_of_time:
                    current = _dev_loss(model, dev_groups, pad_id, torch, device, autocast)
                    row = {"step": step, "train_loss": running, "dev_loss": current, "lr": scheduler.get_last_lr()[0],
                           "elapsed_seconds": round(elapsed, 1)}
                    history.append(row)
                    log.write(json.dumps(row) + "\n")
                    log.flush()
                    if best["loss"] is None or current < best["loss"]:
                        best = {"loss": current, "step": step}
                        model.save_pretrained(str(folder / "adapter"))
                        stale = 0
                    else:
                        stale += 1
                    if progress:
                        progress({"phase": "training", "step": step, "steps": planned, "train_loss": running,
                                  "dev_loss": current, "best_dev_loss": best["loss"], "elapsed_seconds": round(elapsed, 1)})
                    if stale >= settings["patience"]:
                        stopped = "early_stopping"
                if out_of_time:
                    stopped = "time_budget"
                if step >= planned or stopped != "completed":
                    break
            epoch += 1
    if best["loss"] is None:                             # nothing was evaluated: keep what exists, say so
        model.save_pretrained(str(folder / "adapter"))
        best = {"loss": None, "step": step}
    # Continue with the SELECTED checkpoint, not the last one: reload it into the student.
    base = model.unload()
    if hasattr(base, "gradient_checkpointing_disable"):
        base.gradient_checkpointing_disable()
    base.config.use_cache = True
    student.model = base
    student.model.eval()
    student.attach(folder / "adapter")
    adapter_files = {p.name: file_hash(p) for p in sorted((folder / "adapter").iterdir()) if p.is_file()}
    receipt = {"kind": "aurora_professor_training", "student": {**student.describe(), "adapter": "adapter"},
               "settings": settings, "lora_targets": targets, "trainable_parameters": trainable,
               "total_parameters": total_parameters, "examples": {"fit": len(fit), "dev": len(dev), "dropped_too_long": dropped},
               "examples_per_skill": _count(fit), "data_sha256": _data_digest(items),
               "steps": step, "planned_steps": planned, "stopped": stopped, "selected_step": best["step"],
               "batches": {"seen": seen_batches, "skipped_out_of_memory": skipped_batches},
               "initial_dev_loss": initial_dev, "selected_dev_loss": best["loss"], "history": history,
               "elapsed_seconds": round(time.monotonic() - started, 1), "adapter_files": adapter_files,
               "note": "A lower development loss is not evidence of better answers; only the paired exam decides."}
    atomic_json(folder / "train_receipt.json", receipt)
    return receipt


def _count(encoded):
    counts = {}
    for example in encoded:
        counts[example["skill"]] = counts.get(example["skill"], 0) + 1
    return dict(sorted(counts.items()))


def _data_digest(items):
    lines = sorted(json.dumps([item["id"], item["messages"], item["target"]], ensure_ascii=False, sort_keys=True) for item in items)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()
