"""Turn a verified adapter into files Ollama can load, and check them in that form.

A verdict obtained on full-precision or 4-bit Transformers weights says nothing
about the quantised GGUF the application serves. This module converts the
adapter (and optionally a merged model) to GGUF with the llama.cpp tools shipped
in the ``llama-cpp-python`` source package from PyPI, so that the same paired
exam can be repeated in the deployment condition.

Nothing here installs or activates a model: see ``install.py`` for that step.
"""
from __future__ import annotations

import subprocess
import sys
import tarfile
import time
from pathlib import Path

from .records import atomic_json, file_hash

#: Quantisation of the tags Aurora pulls from the Ollama library.
DEFAULT_QUANTIZATION = "Q4_K_M"


def llama_tools(folder):
    """Locate (or fetch from PyPI) the llama.cpp conversion scripts matching the installed engine.

    The scripts come from the ``llama-cpp-python`` source distribution, i.e. from
    the package index, never from an arbitrary URL.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    found = sorted(folder.rglob("convert_lora_to_gguf.py"))
    if not found:
        archive = next(iter(sorted(folder.glob("llama_cpp_python-*.tar.gz"))), None)
        if archive is None:                      # reuse a source package already present, else fetch one from PyPI
            from importlib.metadata import PackageNotFoundError, version
            try:                                 # same version as the installed engine when there is one
                wanted = "llama-cpp-python==" + version("llama-cpp-python")
            except PackageNotFoundError:         # converting an adapter needs the scripts only, not the compiled engine
                wanted = "llama-cpp-python"
            subprocess.run([sys.executable, "-m", "pip", "download", "--quiet", "--no-deps", "--no-binary", ":all:",
                            "--dest", str(folder), wanted], check=True, timeout=1800)
            archive = next(folder.glob("llama_cpp_python-*.tar.gz"))
        with tarfile.open(archive) as bundle:
            # The converters import their sibling ``conversion`` package and ``gguf-py``; nothing else is unpacked.
            members = [m for m in bundle.getmembers()
                       if "/vendor/llama.cpp/" in m.name and (m.name.endswith(("convert_lora_to_gguf.py", "convert_hf_to_gguf.py"))
                                                              or "/vendor/llama.cpp/conversion/" in m.name
                                                              or "/vendor/llama.cpp/gguf-py/" in m.name
                                                              or "/vendor/llama.cpp/models/templates/" in m.name)]
            bundle.extractall(folder, members=members, filter="data")
        found = sorted(folder.rglob("convert_lora_to_gguf.py"))
    if not found:
        raise RuntimeError("llama.cpp conversion scripts not found in the llama-cpp-python source package")
    root = found[0].parent
    package = next((part for part in root.parts if part.startswith("llama_cpp_python-")), None)
    return {"root": root, "lora": root / "convert_lora_to_gguf.py", "model": root / "convert_hf_to_gguf.py", "package": package,
            "sha256": {"convert_lora_to_gguf.py": file_hash(root / "convert_lora_to_gguf.py"),
                       "convert_hf_to_gguf.py": file_hash(root / "convert_hf_to_gguf.py")}}


def _run(argv, log, timeout):
    with Path(log).open("ab") as stream:
        done = subprocess.run([str(a) for a in argv], stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    if done.returncode:
        tail = Path(log).read_text(encoding="utf-8", errors="replace")[-1500:]
        raise RuntimeError(f"{Path(str(argv[1])).name} failed ({done.returncode}):\n{tail}")


def adapter_to_gguf(adapter, base, output, tools, *, timeout=3600):
    """PEFT LoRA adapter -> GGUF LoRA. ``base`` is a local snapshot folder or a Hub id (configuration only)."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    source = ["--base", str(base)] if Path(str(base)).is_dir() else ["--base-model-id", str(base)]
    _run([sys.executable, tools["lora"], *source, "--outfile", output, "--outtype", "f16", adapter],
         output.with_suffix(".log"), timeout)
    return output


def model_to_gguf(model, output, tools, *, timeout=7200):
    """Transformers model folder -> full-precision GGUF (F16)."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    _run([sys.executable, tools["model"], model, "--outfile", output, "--outtype", "f16"], output.with_suffix(".log"), timeout)
    return output


def quantize(source, output, quantization=DEFAULT_QUANTIZATION):
    """Quantise a GGUF with the llama.cpp library bundled in llama-cpp-python."""
    import llama_cpp
    kinds = {"Q4_K_M": llama_cpp.LLAMA_FTYPE_MOSTLY_Q4_K_M, "Q5_K_M": llama_cpp.LLAMA_FTYPE_MOSTLY_Q5_K_M,
             "Q8_0": llama_cpp.LLAMA_FTYPE_MOSTLY_Q8_0}
    if quantization not in kinds:
        raise ValueError(f"Unsupported quantisation {quantization}; known: {sorted(kinds)}")
    parameters = llama_cpp.llama_model_quantize_default_params()
    parameters.ftype = kinds[quantization]
    status = llama_cpp.llama_model_quantize(str(source).encode(), str(output).encode(), parameters)
    if status != 0 or not Path(output).is_file():
        raise RuntimeError(f"llama.cpp quantisation failed with status {status}")
    return Path(output)


def merge(student, adapter, output):
    """Fold the adapter into full-precision base weights (needs RAM for the whole model)."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    kwargs = {"revision": student.get("revision"), "low_cpu_mem_usage": True}
    try:
        base = AutoModelForCausalLM.from_pretrained(student["hf"], dtype=torch.float16, **kwargs)
    except TypeError:
        base = AutoModelForCausalLM.from_pretrained(student["hf"], torch_dtype=torch.float16, **kwargs)
    merged = PeftModel.from_pretrained(base, str(adapter)).merge_and_unload()
    merged.save_pretrained(str(output), safe_serialization=True)
    AutoTokenizer.from_pretrained(student["hf"], revision=student.get("revision")).save_pretrained(str(output))
    return Path(output)


def export(student, adapter, folder, *, base_snapshot=None, merged=False, quantization=DEFAULT_QUANTIZATION, tools_folder=None):
    """Write ``adapter.gguf`` (always) and a merged quantised model (on request) with a hashed receipt."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    tools = llama_tools(tools_folder or folder / "llama_tools")
    receipt = {"kind": "aurora_professor_export", "student": {k: student.get(k) for k in ("tag", "hf", "revision")},
               "adapter_sha256": file_hash(next(Path(adapter).glob("adapter_model.*"))), "tools_sha256": tools["sha256"],
               "tools_package": tools["package"],
               "files": {}, "errors": {}}
    try:
        lora = adapter_to_gguf(adapter, base_snapshot or student["hf"], folder / "adapter.gguf", tools)
        receipt["files"]["adapter.gguf"] = {"sha256": file_hash(lora), "bytes": lora.stat().st_size}
    except Exception as exc:                       # reported, never hidden: the installer needs to know
        receipt["errors"]["adapter.gguf"] = f"{type(exc).__name__}: {str(exc)[:600]}"
    if merged:
        try:
            weights = merge(student, adapter, folder / "merged_model")
            full = model_to_gguf(weights, folder / "merged-F16.gguf", tools)
            small = quantize(full, folder / f"merged-{quantization}.gguf", quantization)
            full.unlink()
            receipt["files"][small.name] = {"sha256": file_hash(small), "bytes": small.stat().st_size, "quantization": quantization}
        except Exception as exc:
            receipt["errors"]["merged"] = f"{type(exc).__name__}: {str(exc)[:600]}"
    receipt["elapsed_seconds"] = round(time.monotonic() - started, 1)
    atomic_json(folder / "export_receipt.json", receipt)
    return receipt
