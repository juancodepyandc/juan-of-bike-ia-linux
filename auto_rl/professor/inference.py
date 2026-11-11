"""Student models: Transformers (training and examination) and Ollama (deployment check).

Both expose ``generate(list_of_messages, max_new_tokens) -> list[str]`` with greedy
decoding, so a base model and its candidate are examined under identical conditions.
Heavy libraries are imported lazily: the pure-Python parts of the professor stay
importable on machines without torch.
"""
from __future__ import annotations

import json
import time
import urllib.request

#: Attention and MLP projections of the Qwen/Llama families.
LORA_TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
ATTENTION_TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj")


def library_versions():
    versions = {}
    for name in ("torch", "transformers", "peft", "datasets", "bitsandbytes", "accelerate", "tokenizers"):
        try:
            versions[name] = __import__(name).__version__
        except Exception:
            versions[name] = None
    return versions


def hardware():
    """Measured hardware, never assumed: an absent GPU is reported as absent."""
    info = {"cuda": False, "gpus": [], "bf16": False}
    try:
        import torch
        info["threads"] = torch.get_num_threads()
        if torch.cuda.is_available():
            info["cuda"] = True
            info["bf16"] = bool(torch.cuda.is_bf16_supported())
            for index in range(torch.cuda.device_count()):
                free, total = torch.cuda.mem_get_info(index)
                info["gpus"].append({"name": torch.cuda.get_device_name(index), "free_gb": round(free / 2 ** 30, 2),
                                     "total_gb": round(total / 2 ** 30, 2),
                                     "capability": list(torch.cuda.get_device_capability(index))})
    except ImportError:
        info["torch"] = None
    try:
        import psutil
        memory = psutil.virtual_memory()
        info["ram_available_gb"] = round(memory.available / 2 ** 30, 2)
        info["ram_total_gb"] = round(memory.total / 2 ** 30, 2)
    except ImportError:
        pass
    return info


def _from_pretrained(loader, name, dtype, **kwargs):
    """``dtype`` replaced ``torch_dtype`` in recent Transformers; support both."""
    try:
        return loader.from_pretrained(name, dtype=dtype, **kwargs)
    except TypeError:
        return loader.from_pretrained(name, torch_dtype=dtype, **kwargs)


class TransformersStudent:
    """A causal language model, optionally 4-bit quantised, optionally with a LoRA adapter."""

    backend = "transformers"

    def __init__(self, model_id, *, revision=None, four_bit=None, adapter=None, max_prompt_tokens=3072,
                 thinking=False, token=None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.model_id, self.revision, self.thinking = model_id, revision, thinking
        self.max_prompt_tokens = max_prompt_tokens
        cuda = torch.cuda.is_available()
        self.four_bit = cuda if four_bit is None else bool(four_bit and cuda)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, token=token)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        kwargs = {"revision": revision, "token": token, "low_cpu_mem_usage": True}
        if cuda:
            # ``is_bf16_supported`` is also true where bf16 is only emulated (T4, compute capability 7.5),
            # which was measured at ~0.6 s per decoding step. Use bf16 only where it is native.
            native = min(torch.cuda.get_device_capability(i)[0] for i in range(torch.cuda.device_count())) >= 8
            self.dtype = torch.bfloat16 if native else torch.float16
            kwargs["device_map"] = "auto"
            if self.four_bit:
                from transformers import BitsAndBytesConfig
                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=self.dtype)
        else:
            self.dtype = torch.float32
        self.model = _from_pretrained(AutoModelForCausalLM, model_id, self.dtype, **kwargs)
        self.model.eval()
        self.adapter = None
        if adapter:
            self.attach(adapter)

    # -- prompt rendering ---------------------------------------------------
    def render(self, messages):
        """Generation prompt exactly as used for inference (non-thinking unless asked)."""
        try:
            return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                      enable_thinking=self.thinking)
        except TypeError:
            return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def end_text(self):
        """Text that closes an assistant turn in this model's chat template."""
        probe = "⁣AURORA_END_PROBE⁣"
        rendered = self.tokenizer.apply_chat_template(
            [{"role": "user", "content": "x"}, {"role": "assistant", "content": probe}], tokenize=False)
        tail = rendered[rendered.rfind(probe) + len(probe):]
        return tail if tail.strip() else (self.tokenizer.eos_token or "")

    @property
    def device(self):
        return next(self.model.parameters()).device

    # -- adapters -----------------------------------------------------------
    def attach(self, adapter):
        from peft import PeftModel
        if self.adapter is not None:
            raise RuntimeError("An adapter is already attached to this student")
        self.model = PeftModel.from_pretrained(self.model, str(adapter))
        self.model.eval()
        self.adapter = str(adapter)

    def detach(self):
        if self.adapter is not None:
            self.model = self.model.unload()
            self.model.eval()
            self.adapter = None

    # -- generation ---------------------------------------------------------
    def generate(self, conversations, max_new_tokens, batch_size=8):
        """Greedy answers, in input order. Over-long prompts return ``None`` (skipped, not graded)."""
        torch, tokenizer = self.torch, self.tokenizer
        prompts = [self.render(messages) for messages in conversations]
        lengths = [len(ids) for ids in tokenizer(prompts, add_special_tokens=False)["input_ids"]]
        outputs = [None] * len(prompts)
        order = sorted((i for i in range(len(prompts)) if lengths[i] <= self.max_prompt_tokens), key=lambda i: lengths[i])
        tokenizer.padding_side = "left"
        position = 0
        while position < len(order):
            size = batch_size
            while True:
                chunk = order[position:position + size]
                try:
                    batch = tokenizer([prompts[i] for i in chunk], return_tensors="pt", padding=True, add_special_tokens=False)
                    batch = {k: v.to(self.device) for k, v in batch.items()}
                    with torch.inference_mode():
                        generated = self.model.generate(**batch, max_new_tokens=max_new_tokens, do_sample=False,
                                                        pad_token_id=tokenizer.pad_token_id)
                    break
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    if size == 1:
                        raise
                    size = max(1, size // 2)
            width = batch["input_ids"].shape[1]
            for row, index in enumerate(chunk):
                outputs[index] = tokenizer.decode(generated[row, width:], skip_special_tokens=True)
            position += len(chunk)
        return outputs

    def describe(self):
        return {"backend": self.backend, "model": self.model_id, "revision": self.revision, "four_bit": self.four_bit,
                "dtype": str(self.dtype).replace("torch.", ""), "adapter": self.adapter, "thinking": self.thinking,
                "max_prompt_tokens": self.max_prompt_tokens}


class LlamaCppStudent:
    """A quantised GGUF, optionally with a GGUF LoRA adapter: the engine Ollama embeds.

    Prompts are rendered by the caller (same chat template as the Transformers
    student), so both backends answer exactly the same text.
    """

    backend = "llama_cpp"

    def __init__(self, gguf, *, render, adapter=None, context=4096, threads=None, max_prompt_tokens=3072):
        from llama_cpp import Llama
        self.gguf, self.adapter, self.render, self.max_prompt_tokens = str(gguf), adapter and str(adapter), render, max_prompt_tokens
        self.llama = Llama(model_path=self.gguf, lora_path=self.adapter, n_ctx=context, n_threads=threads, seed=0, verbose=False)

    def generate(self, conversations, max_new_tokens, batch_size=1):
        outputs = []
        for messages in conversations:
            tokens = self.llama.tokenize(self.render(messages).encode("utf-8"), add_bos=False, special=True)
            if len(tokens) > self.max_prompt_tokens or len(tokens) + max_new_tokens > self.llama.n_ctx():
                outputs.append(None)
                continue
            self.llama.reset()
            answer = self.llama.create_completion(prompt=tokens, max_tokens=max_new_tokens, temperature=0.0)
            outputs.append(answer["choices"][0]["text"])
        return outputs

    def describe(self):
        from .records import file_hash
        return {"backend": self.backend, "gguf": self.gguf, "gguf_sha256": file_hash(self.gguf),
                "adapter": self.adapter, "adapter_sha256": file_hash(self.adapter) if self.adapter else None,
                "context": self.llama.n_ctx()}


class OllamaStudent:
    """The model exactly as the application calls it: an Ollama tag over HTTP."""

    backend = "ollama"

    def __init__(self, tag, *, url="http://127.0.0.1:11434", context=8192, timeout=600, thinking=False):
        self.tag, self.url, self.context, self.timeout, self.thinking = tag, url.rstrip("/"), context, timeout, thinking

    def _post(self, path, payload):
        request = urllib.request.Request(self.url + path, data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def digest(self):
        """Content digest of the served weights, so a verdict names what was really examined."""
        for model in self._get("/api/tags").get("models", []):
            if model.get("name") == self.tag or model.get("model") == self.tag:
                return model.get("digest")
        return None

    def _get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=self.timeout) as response:
            return json.load(response)

    def generate(self, conversations, max_new_tokens, batch_size=1):
        outputs = []
        for messages in conversations:
            payload = {"model": self.tag, "messages": messages, "stream": False, "think": self.thinking,
                       "options": {"temperature": 0, "seed": 0, "num_predict": max_new_tokens, "num_ctx": self.context}}
            for attempt in range(3):
                try:
                    answer = self._post("/api/chat", payload)
                    break
                except OSError:
                    if attempt == 2:
                        raise
                    time.sleep(2 + 3 * attempt)
            if answer.get("done_reason") == "length" and not answer.get("message", {}).get("content"):
                outputs.append("")          # the budget was spent without an answer: graded as wrong
            else:
                outputs.append(answer.get("message", {}).get("content", ""))
        return outputs

    def describe(self):
        return {"backend": self.backend, "model": self.tag, "digest": self.digest(), "context": self.context,
                "thinking": self.thinking}
