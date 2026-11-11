"""Reproducible cloud preflight/validation and explicit native payload execution.

No synthetic training loop, automatic model promotion or implicit GPU job launch.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
import zipfile

from .storage import atomic_json, file_hash

ROOT = Path(__file__).resolve().parents[1]
SHARED_SUITES = (
    "tests_agi.test_mcp_transport_sessions", "tests_agi.test_browser_runtime",
    "tests_agi.test_judge_ratchet_persistence", "tests_auto_rl.test_compute_governor",
)


def _run_bounded(argv, *, log, timeout):
    process = subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=os.name != "nt")
    try:
        return process.wait(timeout=timeout), "finished"
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        return None, "timeout"


def probe_resources(*, session_seconds=None):
    """Report measurements and missing dependencies without allocating training tensors."""
    telemetry = {"worker_id": platform.node(), "last_heartbeat": time.time(), "status": "ready",
                 "gpu_name": None, "device_free_vram_gb": [], "available_ram_gb": None,
                 "remaining_seconds": session_seconds, "session_budget_source": "operator_limit_not_provider_quota",
                 "python": platform.python_version(), "bf16_supported": False}
    try:
        import psutil
        telemetry["available_ram_gb"] = psutil.virtual_memory().available / 2**30
    except ImportError:
        pass
    try:
        import torch
        telemetry["torch_version"] = torch.__version__
        if torch.cuda.is_available():
            telemetry.update(gpu_name=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
                             device_free_vram_gb=[torch.cuda.mem_get_info(i)[0] / 2**30 for i in range(torch.cuda.device_count())],
                             bf16_supported=torch.cuda.is_bf16_supported())
    except ImportError:
        telemetry["torch_version"] = None
    telemetry["dependencies"] = {name: importlib.util.find_spec(name) is not None for name in
                                  ("playwright", "psutil", "torch", "safetensors", "transformers", "peft")}
    return telemetry


def validate_native(output, *, suites=SHARED_SUITES, timeout=300):
    """Execute native software contracts; explicitly not a model quality benchmark."""
    if not suites or any(not re.fullmatch(r"tests_(?:agi|auto_rl)\.test_[a-z0-9_]+", suite) for suite in suites):
        raise ValueError("Use explicit native test module names")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_files = [ROOT / (suite.replace(".", "/") + ".py") for suite in suites]
    source_files += [p for folder in ("agi_core", "auto_rl", "mcp") for p in (ROOT / folder).glob("*.py")]
    hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in source_files}
    started = time.monotonic()
    with (output / "native_tests.log").open("wb") as log:
        code, status = _run_bounded([sys.executable, "-m", "unittest", *suites, "-v"], log=log, timeout=timeout)
    unchanged = all(file_hash(ROOT / name) == value for name, value in hashes.items())
    report = {"kind": "native_software_contracts", "model_quality_measured": False,
              "status": status, "exit_code": code, "passed": code == 0 and unchanged, "sources_unchanged": unchanged,
              "duration_seconds": time.monotonic() - started, "test_sources": hashes,
              "log_sha256": file_hash(output / "native_tests.log"), "promoted": False}
    atomic_json(output / "validation.json", report)
    return report


def run_payload(*, job_id, payload_hash, inputs, output, requirements, session_seconds):
    """Run only a hash-pinned native training package after resource admission."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", job_id):
        raise ValueError("Invalid job identifier")
    if not re.fullmatch(r"[0-9a-f]{64}", payload_hash):
        raise ValueError("Expected a SHA-256 payload digest")
    inputs, output = Path(inputs).resolve(), Path(output).resolve()
    matches = [p for p in inputs.rglob("payload.bin") if file_hash(p) == payload_hash]
    if len(matches) != 1:
        raise ValueError("Exactly one hash-matching native payload is required")
    with zipfile.ZipFile(matches[0]) as archive:
        info = archive.getinfo("spec.json")
        if info.file_size > 1024 * 1024:
            raise ValueError("Training specification too large")
        spec = json.loads(archive.read(info))
    if spec.get("job_id") != job_id:
        raise ValueError("Training specification belongs to another job")
    if spec.get("multi_module_testbench") or spec.get("surrogate_es"):
        raise ValueError("This notebook requires native model training, not a surrogate testbench")
    from .compute_governor import plan_compute, _number
    budget = _number(spec.get("training_seconds"))
    if budget is None or budget > requirements.get("duration_seconds", 0):
        raise ValueError("Pinned native training budget exceeds the admitted duration")
    measured = probe_resources(session_seconds=session_seconds)
    decision = plan_compute(requirements, {"current_runtime": measured})
    if not decision["selected_worker"]:
        raise RuntimeError("Resource admission refused: " + json.dumps(decision["decisions"]))
    # Every experiment owns a fresh export directory; never mix old and new receipts.
    run = output / job_id
    run.mkdir(parents=True, exist_ok=False)
    atomic_json(run / "admission.json", decision)
    with (run / "worker.log").open("wb") as log:
        code, status = _run_bounded([sys.executable, "-m", "auto_rl.cloud_worker",
            "--job-id", job_id, "--payload-sha256", payload_hash, "--work", str(run),
            "--root", str(run / "inputs"), "--search-root", str(inputs)], log=log, timeout=session_seconds)
    if code != 0 or status != "finished":
        raise RuntimeError("Native worker failed or exceeded the explicit session budget; inspect worker.log")
    result = json.loads((run / "aurora_export/result.json").read_text())
    if result.get("error"):
        raise RuntimeError("Native cloud worker failed; inspect its run-scoped error.log")
    from agi_core.judge_ratchet import judge_independent_holdout_evidence
    # Training loss and a transport receipt alone cannot pass an independent audit.
    gate = judge_independent_holdout_evidence([])
    atomic_json(run / "promotion_gate.json", gate)
    return {"kind": "native_training_receipt", "job_id": job_id, "result": result,
            "independent_audit": gate, "promoted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("probe", "validate", "run-payload"), nargs="?", default="probe")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--suite", action="append", help="Explicit native unittest module; repeat to select suites")
    parser.add_argument("--session-seconds", type=float)
    parser.add_argument("--job-id")
    parser.add_argument("--payload-sha256")
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--requirements", type=Path)
    args = parser.parse_args()
    if args.mode == "probe":
        result = probe_resources(session_seconds=args.session_seconds)
    elif args.mode == "validate":
        if args.output is None:
            parser.error("validate requires a run-scoped --output directory")
        result = validate_native(args.output, suites=tuple(args.suite) if args.suite else SHARED_SUITES)
    else:
        if any(v is None for v in (args.output, args.job_id, args.payload_sha256, args.inputs, args.requirements, args.session_seconds)):
            parser.error("run-payload requires explicit job, input, hash, requirements, output and session budget")
        result = run_payload(job_id=args.job_id, payload_hash=args.payload_sha256, inputs=args.inputs,
                             output=args.output, requirements=json.loads(args.requirements.read_text()),
                             session_seconds=args.session_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("passed") is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
