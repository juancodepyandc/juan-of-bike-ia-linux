"""Private launch state and process identities for the Linux desktop launcher."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def process_ids(kind: str, root: Path, proc_root: Path = Path('/proc')) -> list[int]:
    """Match owned processes by argv, never by a substring of a shell command."""
    found = []
    for proc in proc_root.iterdir():
        if not proc.name.isdecimal():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            args = [part.decode(errors='replace') for part in (proc / 'cmdline').read_bytes().split(b'\0') if part]
            if not args:
                continue
            name = Path(args[0]).name
            match = False
            if kind == 'tunnel' and name == 'cloudflared' and 'tunnel' in args[1:]:
                match = any(arg == '--url=http://127.0.0.1:3001' or
                            (arg == '--url' and i + 1 < len(args) and args[i + 1] == 'http://127.0.0.1:3001')
                            for i, arg in enumerate(args))
            elif kind == 'watcher':
                match = name in ('bash', 'sh') and len(args) > 1 and args[1] == str(root / 'scripts/aurora-status-watcher.sh')
            elif kind == 'native':
                match = args[0] == str(root / 'application/src-tauri/target/release/juan-of-bike-ia')
            if match:
                found.append(int(proc.name))
        except (OSError, ValueError):
            continue
    return sorted(found)


def fingerprint(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    entries = []
    for path in paths:
        if path.is_dir():
            entries.extend(p for p in path.rglob('*') if p.is_file() or p.is_symlink())
        else:
            entries.append(path)
    for path in sorted(set(entries)):
        digest.update(str(path.relative_to(root)).encode() + b'\0')
        if path.is_symlink():
            digest.update(b'link:' + os.readlink(path).encode())
        elif path.is_file():
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
        else:
            digest.update(b'missing')
        digest.update(b'\0')
    return digest.hexdigest()


def build_state(kind: str, root: Path) -> dict:
    app = root / 'application'
    web_inputs = [app / name for name in ('src', 'public', 'index.html', 'package.json', 'package-lock.json',
                                         'vite.config.ts', 'tsconfig.json', 'tsconfig.app.json', 'tsconfig.node.json')]
    if kind == 'web':
        return {'inputs': fingerprint(web_inputs, root), 'output': fingerprint([app / 'dist'], root),
                'present': (app / 'dist/index.html').is_file()}
    native_inputs = [app / 'src-tauri' / name for name in ('src', 'capabilities', 'Cargo.toml', 'Cargo.lock',
                                                         'build.rs', 'tauri.conf.json')]
    binary = app / 'src-tauri/target/release/juan-of-bike-ia'
    return {'inputs': fingerprint(native_inputs + [app / 'dist'], root),
            'output': fingerprint([binary], root), 'present': binary.is_file() and os.access(binary, os.X_OK)}


def build_is_current(kind: str, root: Path, cache: Path) -> bool:
    try:
        current = build_state(kind, root)
        return current['present'] and json.loads(cache.read_text()) == current
    except (OSError, ValueError):
        return False


def mark_build(kind: str, root: Path, cache: Path) -> None:
    state = build_state(kind, root)
    if not state['present']:
        raise RuntimeError(f'Missing {kind} build output')
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=cache.parent, prefix=cache.name + '.', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, cache)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['process-ids', 'build-current', 'mark-build'])
    parser.add_argument('kind')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--cache', type=Path)
    args = parser.parse_args()
    if args.operation == 'process-ids':
        if args.kind not in ('tunnel', 'watcher', 'native'):
            parser.error('Unknown process kind')
        print('\n'.join(map(str, process_ids(args.kind, args.root))))
        return 0
    if args.kind not in ('web', 'native') or args.cache is None:
        parser.error('A build kind and cache path are required')
    if args.operation == 'build-current':
        return 0 if build_is_current(args.kind, args.root, args.cache) else 1
    mark_build(args.kind, args.root, args.cache)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
