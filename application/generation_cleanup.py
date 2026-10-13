"""Deletion limited to the explicitly cancelled, dedicated 3D run directory."""
from pathlib import Path
import re
import shutil


def owned_run_root(workspace, candidate, args):
    if not candidate:
        return None
    root = Path(workspace).resolve() / 'output' / '3d' / 'conversations'
    path = Path(candidate)
    try:
        relative = path.relative_to(root)
        if len(relative.parts) != 2 or not re.fullmatch(r'juan_bike_\d+', relative.name):
            return None
        if path.resolve() != path.absolute() or any(p.is_symlink() for p in (root, path.parent, path)):
            return None
        outputs = ([args[args.index('--output-dir') + 1]] if '--output-dir' in args
                   else [arg for arg in args if isinstance(arg, str) and Path(arg).is_absolute()])
        if not any(Path(output).resolve().is_relative_to(path.resolve()) for output in outputs):
            return None
        return str(path)
    except (ValueError, IndexError, TypeError, OSError):
        return None


def remove_cancelled_run(workspace, candidate):
    # Repeat confinement checks at deletion time, after workers have exited.
    root = owned_run_root(workspace, candidate, ['--output-dir', candidate])
    if root is None:
        return {'removed': False, 'error': 'Run directory no longer safely confined.'}
    try:
        if Path(root).exists():
            shutil.rmtree(root)
        return {'removed': True}
    except OSError as exc:
        return {'removed': False, 'error': str(exc)}
