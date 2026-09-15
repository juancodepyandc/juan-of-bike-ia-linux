"""Release idle ComfyUI caches without interrupting queued or active jobs."""
import json
import urllib.request
import urllib.error
import subprocess
import threading
import time
from pathlib import Path

from .config import STATE
from .storage import atomic_json, read_json


INFERENCE_SERVICE = 'aurora-trained-models.service'


def configure_torch_memory():
    """Set allocator defaults before importing/loading a CUDA model.

    This does not lower model precision or cap useful memory. Expandable
    segments reduce fragmentation, while the split-size fallback prevents a
    long-running Comfy/serve process from leaving unusable small blocks.
    """
    import os
    os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF',
                          'expandable_segments:True,max_split_size_mb:128')
    os.environ.setdefault('TORCH_CUDNN_V8_API_LRU_CACHE_LIMIT', '0')


def suspend_inference_service(state=STATE):
    """Release the resident Aurora LLM before a local training cycle.

    Test state directories never touch the user's systemd services. The
    return value records whether the service was active so it can be restored
    exactly after the cycle.
    """
    state = Path(state).resolve()
    if state != STATE.resolve():
        return False
    try:
        probe = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', INFERENCE_SERVICE],
                               timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if probe.returncode != 0:
        return False
    atomic_json(Path(state)/'inference_lease.json', {'restore': True})
    stopped = subprocess.run(['systemctl', '--user', 'stop', INFERENCE_SERVICE],
                             capture_output=True, text=True, timeout=30)
    if stopped.returncode != 0:
        raise RuntimeError('Impossible de libérer la VRAM : arrêt de aurora-trained-models.service échoué')
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        check = subprocess.run(['systemctl', '--user', 'is-active', '--quiet', INFERENCE_SERVICE],
                               timeout=8)
        if check.returncode != 0:
            return True
        time.sleep(.25)
    raise RuntimeError('Le service d’inférence conserve la VRAM après son arrêt')


def restore_inference_service(was_active, state=STATE):
    if not was_active or Path(state).resolve() != STATE.resolve():
        return
    started = subprocess.run(['systemctl', '--user', 'start', INFERENCE_SERVICE],
                             capture_output=True, text=True, timeout=30)
    if started.returncode != 0:
        raise RuntimeError('Le service aurora-trained-models.service n’a pas pu redémarrer')
    (Path(state)/'inference_lease.json').unlink(missing_ok=True)


def recover_inference_service(state=STATE):
    """The controller can recover a lease after its worker was SIGKILLed."""
    if read_json(Path(state)/'inference_lease.json', {}).get('restore'):
        restore_inference_service(True, state)


def reclaim_comfy_ram(state=STATE):
    """Free host RAM as well as VRAM before a non-Comfy model is loaded."""
    if Path(state).resolve() != STATE.resolve():
        return
    if not release_idle_comfy():
        raise RuntimeError('ComfyUI est occupé ; attente de sa fin requise pour libérer la RAM')
    # /free unloads GPU weights but Python/native allocators may retain 15+ GiB
    # of host RAM. Restart only the idle service after rechecking its queue.
    probe = subprocess.run(['systemctl','--user','show','aurora-comfyui.service',
                            '--property=MainPID','--value'], capture_output=True,text=True,timeout=8)
    pid = probe.stdout.strip()
    if not pid.isdigit() or pid == '0':
        return
    try:
        rss = next(int(line.split()[1]) for line in Path('/proc/'+pid+'/status').read_text().splitlines()
                   if line.startswith('VmRSS:'))
    except (OSError, StopIteration):
        return
    # A few MiB is normal for a healthy idle service.  Restart only when the
    # native/allocator cache has grown into the multi-GiB range that can starve
    # the local trainer (the previous 2 MiB threshold restarted ComfyUI on
    # every cycle, even when it was already clean).
    if rss < 2*1024*1024*1024:
        return
    with urllib.request.urlopen('http://127.0.0.1:8188/queue',timeout=5) as response:
        queue=json.load(response)
    if queue.get('queue_running') or queue.get('queue_pending'):
        raise RuntimeError('Une génération ComfyUI vient de démarrer ; RAM non libérée')
    result=subprocess.run(['systemctl','--user','restart','aurora-comfyui.service'],
                          capture_output=True,text=True,timeout=45)
    if result.returncode:
        raise RuntimeError('Impossible de libérer la RAM retenue par ComfyUI')
    for _ in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8188/queue',timeout=2):
                return
        except OSError:
            time.sleep(.5)
    raise RuntimeError('ComfyUI ne répond pas après libération de la RAM')


def start_heartbeat(status, started):
    stopped = threading.Event()
    def monitor():
        while not stopped.wait(5):
            try:
                result = subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used',
                    '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=4)
                gpu, memory = map(float,result.stdout.splitlines()[0].split(','))
                status.flush(gpu_percent=gpu,gpu_memory_gb=memory/1024,
                    elapsed_seconds=time.monotonic()-started,heartbeat_at=time.time())
            except (OSError,ValueError,IndexError,subprocess.TimeoutExpired):
                pass
    thread = threading.Thread(target=monitor,daemon=True)
    thread.start()
    def stop():
        stopped.set()
        thread.join(timeout=6)
    return stop


def release_idle_comfy():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8188/queue', timeout=5) as response:
            queue = json.load(response)
        if queue.get('queue_running') or queue.get('queue_pending'):
            return False
        request = urllib.request.Request('http://127.0.0.1:8188/free',
            data=b'{"unload_models":true,"free_memory":true}',
            headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request, timeout=15):
            pass
    except (OSError, ValueError):
        pass
    return True
