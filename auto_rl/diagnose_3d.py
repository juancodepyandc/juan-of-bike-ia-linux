"""One real baseline mesh, without changing the training registry or status."""
import gc
import json
import time
from pathlib import Path
import torch
from .config import defaults, STATE
from .backends import resolve_paths, make_backend, visual_tasks
from .judges import make_judge
from .storage import atomic_json, file_hash


def main():
    root=STATE/'diagnostics/3d-inference-check';root.mkdir(parents=True,exist_ok=True)
    c=defaults('3d');c.update(train_tasks=3,eval_tasks=8,auto_refill=False)
    paths=resolve_paths(c)
    tasks=visual_tasks(c,root/'tasks',lambda:None,paths)
    task=next((t for t in tasks if 'scorpion' in t['prompt'].lower()),tasks[0])
    print('Loading actual TRELLIS baseline',flush=True)
    backend=make_backend(c,paths)
    try:
        backend.adapter.enabled=False
        torch.cuda.reset_peak_memory_stats()
        started=time.monotonic()
        artifact=root/'base.glb'
        backend.generate(task,41,artifact)
        peak=torch.cuda.max_memory_allocated()/2**30
        print('Mesh exported; inspecting its geometry and four views',flush=True)
        score=make_judge(c,paths).score(artifact,task)
        atomic_json(root/'result.json',{'probe':True,'task':task,'artifact':str(artifact),
            'sha256':file_hash(artifact),'peak_vram_gb':peak,'seconds':time.monotonic()-started,
            'generation':c['generation'],'judge':score})
        print(json.dumps({'mesh_bytes':artifact.stat().st_size,'peak_vram_gb':peak,'judge':score}),flush=True)
    finally:
        backend.close()
        del backend
        gc.collect();torch.cuda.empty_cache()


if __name__=='__main__':main()
