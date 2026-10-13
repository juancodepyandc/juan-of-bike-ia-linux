"""Atomic local operation results, independent of models, transport and databases.

Hashes bind bytes and identity; these are not signed attestations or proofs of
semantic correctness. An absent receipt never permits replay of unknown effects.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

MAX_RECEIPT_BYTES = 8 * 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def receipt_path(directory, operation_id):
    root = Path(directory).resolve()
    path = root / '.aurora-receipts' / (hashlib.sha256(operation_id.encode()).hexdigest() + '.json')
    if not path.resolve().is_relative_to(root):
        raise ValueError('Receipt path escapes operation directory')
    return path


def _artifact(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Artifact is outside the operation directory or missing')
    before = path.stat()
    digest = sha256_file(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Artifact changed while computing its receipt')
    return {'path': path.relative_to(root).as_posix(), 'size_bytes': after.st_size, 'sha256': digest}


def write_receipt(directory, operation_id, request, producer_sha256, result, artifacts=()):
    if not isinstance(result, dict) or type(result.get('ok')) is not bool:
        raise ValueError('An explicit engine result is required')
    root = Path(directory).resolve()
    files = [_artifact(root, name) for name in artifacts]
    record = {'schema': 'aurora.operation-receipt.v1', 'operation_id': operation_id,
              'request_sha256': hashlib.sha256(request.encode()).hexdigest(),
              'producer_sha256': producer_sha256,
              'status': 'completed' if result['ok'] else 'failed',
              'result': result, 'artifacts': files}
    data = json.dumps(record, ensure_ascii=False, allow_nan=False).encode()
    if len(data) > MAX_RECEIPT_BYTES:
        raise ValueError('Operation receipt exceeds the configured byte limit')
    path = receipt_path(root, operation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.receipt-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == 'posix':
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return record


def read_receipt(directory, operation_id, request, producer_sha256):
    root = Path(directory).resolve()
    path = receipt_path(root, operation_id)
    if path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ValueError('Operation receipt exceeds the configured byte limit')
    with path.open('rb') as stream:
        data = stream.read(MAX_RECEIPT_BYTES + 1)
    if len(data) > MAX_RECEIPT_BYTES:
        raise ValueError('Operation receipt exceeds the configured byte limit')
    record = json.loads(data)
    expected = {'schema': 'aurora.operation-receipt.v1', 'operation_id': operation_id,
                'request_sha256': hashlib.sha256(request.encode()).hexdigest(),
                'producer_sha256': producer_sha256}
    if not isinstance(record, dict) or any(record.get(k) != v for k, v in expected.items()):
        raise ValueError('Operation receipt identity does not match the requested operation')
    result = record.get('result')
    if not isinstance(result, dict) or result.get('ok') is not True or record.get('status') != 'completed':
        raise ValueError('Operation receipt does not prove engine completion')
    files = record.get('artifacts')
    if not isinstance(files, list) or not files or len(files) > 512:
        raise ValueError('A completed artifact receipt is required')
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str) or _artifact(root, item['path']) != item:
            raise ValueError('Operation artifact bytes no longer match their receipt')
    return record
