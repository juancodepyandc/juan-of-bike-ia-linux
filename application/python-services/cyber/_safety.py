"""Shared safety helpers for the cyber lab.

This module is the single backend gate for cyber Python ops:

- active network probes stay on loopback / private networks;
- file reads and writes stay inside the ``application/`` workspace;
- expensive operations get bounded inputs before they can freeze the UI.

The goal is not to make the cyber module timid. It is to make it useful in the
right place: local, educational, owned-client work with clear limits.
"""
from __future__ import annotations

import ipaddress
import os
import socket
import time
from pathlib import Path
from typing import Iterable, Sequence


APP_ROOT = Path(__file__).resolve().parents[2]
MAX_READ_BYTES = int(os.environ.get("AURORA_CYBER_MAX_READ_BYTES", str(32 * 1024 * 1024)))
MAX_TEXT_PAYLOAD_BYTES = int(os.environ.get("AURORA_CYBER_MAX_TEXT_BYTES", str(64 * 1024)))
MAX_PORTS_PER_SCAN = int(os.environ.get("AURORA_CYBER_MAX_PORTS", "256"))
MAX_PORT_SCAN_SECONDS = float(os.environ.get("AURORA_CYBER_PORT_SCAN_SECONDS", "20"))

RFC1918_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_workspace_path(path: str | os.PathLike[str], *, must_exist: bool = True) -> Path:
    """Resolve a user supplied path and ensure it remains under application/."""
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("missing path")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = APP_ROOT / candidate
    resolved = candidate.resolve()
    if not _is_relative_to(resolved, APP_ROOT):
        raise PermissionError(f"Path escapes Aurora application workspace: {raw}")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(str(resolved))
    return resolved


def validate(
    action: str,
    target: str | os.PathLike[str] | None = None,
    *,
    max_bytes: int = MAX_READ_BYTES,
    create_parent: bool = True,
) -> Path | str:
    """Central validation entry point used by public cyber ops."""
    action = (action or "").strip().lower()
    if action in {"read", "read-file", "file-read"}:
        if target is None:
            raise ValueError("read validation requires a path")
        return validate_read_file(target, max_bytes=max_bytes)
    if action in {"write", "write-file", "file-write"}:
        if target is None:
            raise ValueError("write validation requires a path")
        return validate_output_path(target, create_parent=create_parent)
    if action in {"network-private", "private-network"}:
        if target is None:
            raise ValueError("network validation requires a target")
        return assert_private(str(target))
    raise ValueError(f"unknown cyber safety validation action: {action}")


def validate_read_file(path: str | os.PathLike[str], *, max_bytes: int = MAX_READ_BYTES) -> Path:
    p = resolve_workspace_path(path, must_exist=True)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    size = p.stat().st_size
    if size > max_bytes:
        raise ValueError(f"File too large for cyber lab ({size} bytes > {max_bytes} bytes): {p}")
    return p


def validate_output_path(path: str | os.PathLike[str], *, create_parent: bool = True) -> Path:
    p = resolve_workspace_path(path, must_exist=False)
    if p.exists() and p.is_dir():
        raise IsADirectoryError(str(p))
    if create_parent:
        p.parent.mkdir(parents=True, exist_ok=True)
    return p


def safe_read_bytes(path: str | os.PathLike[str], *, max_bytes: int = MAX_READ_BYTES) -> bytes:
    p = validate("read", path, max_bytes=max_bytes)
    assert isinstance(p, Path)
    return p.read_bytes()


def safe_read_text(
    path: str | os.PathLike[str],
    *,
    encoding: str = "utf-8",
    max_bytes: int = MAX_READ_BYTES,
) -> str:
    p = validate("read", path, max_bytes=max_bytes)
    assert isinstance(p, Path)
    return p.read_text(encoding=encoding)


def validate_text_payload(name: str, value: str, *, max_bytes: int = MAX_TEXT_PAYLOAD_BYTES) -> str:
    data = (value or "").encode("utf-8")
    if len(data) > max_bytes:
        raise ValueError(f"{name} payload too large ({len(data)} bytes > {max_bytes} bytes)")
    return value


def require_int_range(name: str, value: int, min_value: int, max_value: int) -> int:
    ivalue = int(value)
    if ivalue < min_value or ivalue > max_value:
        raise ValueError(f"{name} must be between {min_value} and {max_value}")
    return ivalue


def sanitize_ports(ports: Sequence[int] | None) -> list[int]:
    clean: list[int] = []
    seen: set[int] = set()
    for raw in ports or []:
        port = int(raw)
        if port < 1 or port > 65535:
            raise ValueError(f"Port out of range: {port}")
        if port not in seen:
            seen.add(port)
            clean.append(port)
    if len(clean) > MAX_PORTS_PER_SCAN:
        raise ValueError(f"Too many ports for one scan ({len(clean)} > {MAX_PORTS_PER_SCAN})")
    return clean


def check_time_budget(start: float, max_seconds: float, label: str) -> None:
    if time.monotonic() - start > max_seconds:
        raise TimeoutError(f"{label} exceeded {max_seconds:.1f}s time cap")


def resolve_target(target: str) -> str:
    """Resolve hostname to IP. Raises if resolution fails."""
    try:
        ipaddress.ip_address(target)
        return target
    except ValueError:
        pass
    infos = socket.getaddrinfo(target, None)
    if not infos:
        raise ValueError(f"Cannot resolve target: {target}")
    return infos[0][4][0]


def assert_private(target: str) -> str:
    """Resolve ``target`` then ensure its IP is loopback or RFC1918.

    Returns the resolved IP string so callers can reuse it.
    """
    ip_str = resolve_target(target)
    ip = ipaddress.ip_address(ip_str)
    if not any(ip in net for net in RFC1918_NETS):
        raise PermissionError(
            f"Target {target} ({ip_str}) is NOT in loopback/RFC1918. "
            "Cyber lab refuses to scan public hosts."
        )
    return ip_str


def iter_private_ips(targets: Iterable[str]) -> Iterable[str]:
    for t in targets:
        ip = validate("network-private", t)
        assert isinstance(ip, str)
        yield ip
