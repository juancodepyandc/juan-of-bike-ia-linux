"""Public media roots; project sources and the PC filesystem require approval."""
from pathlib import Path


def public_generated_asset(candidate,workspace,comfy=None,cold=None):
    path=Path(candidate).resolve();base=Path(workspace).resolve()
    if path.is_relative_to((base/'output'/'engineering-design').resolve()):
        return False
    roots=[base/'output',base/'temp',base/'public',base/'dist',base/'aurora-models'/'outputs']
    if comfy:roots.append(Path(comfy)/'output')
    if cold:roots.append(Path(cold)/'outputs')
    return any(path.is_relative_to(root.resolve()) for root in roots)
