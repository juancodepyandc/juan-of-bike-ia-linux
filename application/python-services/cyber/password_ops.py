"""Password hashing demos: Argon2id, bcrypt, scrypt — explains cost factors."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _safety import require_int_range, validate_text_payload  # noqa: E402


REQUIRED = {"argon2": "argon2-cffi", "bcrypt": "bcrypt"}


def ensure_deps() -> None:
    missing = []
    for imp, pip in REQUIRED.items():
        try:
            __import__(imp)
        except ImportError:
            missing.append(pip)
    if missing:
        print(f"PROGRESS:install:Installing {', '.join(missing)}", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *missing],
            stdout=subprocess.DEVNULL,
        )


ensure_deps()


def argon2_hash(password: str, time_cost: int = 3, memory_kib: int = 65536, parallelism: int = 4) -> dict:
    from argon2 import PasswordHasher, Type

    password = validate_text_payload("password", password, max_bytes=4096)
    time_cost = require_int_range("argon2 time_cost", time_cost, 1, 8)
    memory_kib = require_int_range("argon2 memory_kib", memory_kib, 8192, 262144)
    parallelism = require_int_range("argon2 parallelism", parallelism, 1, 8)
    ph = PasswordHasher(time_cost=time_cost, memory_cost=memory_kib, parallelism=parallelism, hash_len=32, type=Type.ID)
    t0 = time.perf_counter()
    h = ph.hash(password)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "algo": "argon2id",
        "hash": h,
        "elapsed_ms": elapsed_ms,
        "params": {"time_cost": time_cost, "memory_kib": memory_kib, "parallelism": parallelism},
    }


def bcrypt_hash(password: str, rounds: int = 12) -> dict:
    import bcrypt as bc

    password = validate_text_payload("password", password, max_bytes=4096)
    rounds = require_int_range("bcrypt rounds", rounds, 4, 15)
    t0 = time.perf_counter()
    salt = bc.gensalt(rounds=rounds)
    h = bc.hashpw(password.encode(), salt).decode()
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {"algo": "bcrypt", "hash": h, "elapsed_ms": elapsed_ms, "rounds": rounds}


def scrypt_hash(password: str, n: int = 2 ** 17, r: int = 8, p: int = 1) -> dict:
    # Defaut N=2**17 : minimum OWASP 2025 pour scrypt (r=8, p=1). Reste dans la
    # plage validee ci-dessous (2**10..2**18). L'analyseur TS (kdfCostAnalyzer)
    # utilise deja 2**17 comme reference — on aligne le backend Python.
    password = validate_text_payload("password", password, max_bytes=4096)
    n = require_int_range("scrypt N", n, 2 ** 10, 2 ** 18)
    if n & (n - 1):
        raise ValueError("scrypt N must be a power of two")
    r = require_int_range("scrypt r", r, 1, 16)
    p = require_int_range("scrypt p", p, 1, 8)
    salt = os.urandom(16)
    t0 = time.perf_counter()
    dk = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "algo": "scrypt",
        "hash": dk.hex(),
        "salt": salt.hex(),
        "params": {"N": n, "r": r, "p": p},
        "elapsed_ms": elapsed_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_a = sub.add_parser("argon2")
    p_a.add_argument("password")
    p_a.add_argument("--time", type=int, default=3)
    p_a.add_argument("--mem", type=int, default=65536)
    p_a.add_argument("--par", type=int, default=4)

    p_b = sub.add_parser("bcrypt")
    p_b.add_argument("password")
    p_b.add_argument("--rounds", type=int, default=12)

    p_s = sub.add_parser("scrypt")
    p_s.add_argument("password")
    p_s.add_argument("--n", type=int, default=2 ** 15)

    args = parser.parse_args()
    try:
        if args.cmd == "argon2":
            out = argon2_hash(args.password, args.time, args.mem, args.par)
        elif args.cmd == "bcrypt":
            out = bcrypt_hash(args.password, args.rounds)
        elif args.cmd == "scrypt":
            out = scrypt_hash(args.password, args.n)
        else:
            raise SystemExit(2)
        print(json.dumps(out))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
