#!/usr/bin/env python3
"""Vraies générations de vues de référence à partir d'une demande.

Service en ligne de commande : une demande JSON par ligne sur stdin
({"id": "...", "request": "un robot jaune", "seed": 7, "subject_kind": null}).
Chaque événement réel est écrit sur stdout en JSON (une ligne) avec son
horodatage : chargement du modèle, essai, début de vue, pas de diffusion k/N,
vue prête, fin. scripts/real-gen/run-live.mjs relaie ces événements à l'écran
de génération d'Aurora pour mesurer synchronisation, hologramme et temps
d'attente sur de vraies générations.

Deux producteurs :

  --backend comfy-flux2   (défaut) le producteur de références FLUX.2 du pipeline 3D serveur :
                          flux_reference_synth.synth_multiview (FLUX.2-dev via ComfyUI, mêmes
                          poids et même graphe que createFlux2Workflow du module 3D
                          frontend, contrats de vue, audit de turnaround et essais du
                          producteur). aurora_3d_pipeline.py lui passe un prompt reformulé ;
                          le banc lui passe la demande brute et le type de sujet de la
                          demande (« subject_kind », qui active l'audit et les essais des
                          personnages). Les pas de diffusion sont lus sur le websocket de
                          ComfyUI (reconnexion automatique, interruptions rapportées).
                          À lancer sur le PC où ComfyUI tourne.
  --backend sd-turbo      Remplaçant pour une machine sans GPU ni poids FLUX.2
                          (conteneur de développement) : SD-Turbo sur CPU, 4 pas.
                          Il ne remplace pas FLUX.2 dans Aurora ; il sert seulement à
                          produire de vraies images à partir d'une demande là où
                          FLUX.2 ne peut pas tourner.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

SERVICES = Path(__file__).resolve().parents[2] / "python-services"

# Vues du remplaçant CPU (le producteur FLUX.2 garde les siennes : face, dos, gauche, droite).
SD_VIEWS = (
    ("face", "full body, front view, facing the camera"),
    ("droite", "full body, side view, profile facing right"),
    ("dos", "full body, back view, seen from behind"),
)
ROLE = {"front": "face", "right": "droite", "left": "gauche", "back": "dos"}

_lock = threading.Lock()


def emit(event: str, **data) -> None:
    with _lock:
        sys.stdout.write(json.dumps({"ev": event, "t": time.time(), **data}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def jobs():
    for line in sys.stdin:
        line = line.strip()
        if line:
            yield json.loads(line)


# --------------------------------------------------------------------------- SD-Turbo (CPU)

def run_sd_turbo(args) -> int:
    import torch
    from diffusers import AutoPipelineForText2Image

    if args.threads:
        torch.set_num_threads(args.threads)
    out = Path(args.output_dir)
    pipe = None
    for job in jobs():
        jid = str(job.get("id") or int(time.time()))
        request = str(job["request"])
        seed = int(job.get("seed", 1))
        started = time.time()
        emit("start", id=jid, request=request, backend="sd-turbo")
        if pipe is None:
            emit("model_load_start", id=jid, model=args.model)
            pipe = AutoPipelineForText2Image.from_pretrained(args.model, torch_dtype=torch.float32, variant="fp16")
            pipe.set_progress_bar_config(disable=True)
            emit("model_loaded", id=jid)
        views = []
        for index, (role, framing) in enumerate(SD_VIEWS):
            prompt = f"{request}, {framing}, centered, isolated on a plain white background, studio lighting, high detail"
            emit("view_start", id=jid, view=role, index=index, total=len(SD_VIEWS), attempt=1)
            t0 = time.time()

            def on_step(_pipe, step, _timestep, kwargs, role=role, index=index):
                emit("step", id=jid, view=role, index=index, total=len(SD_VIEWS), step=step + 1, steps=args.steps)
                return kwargs

            image = pipe(
                prompt=prompt,
                num_inference_steps=args.steps,
                guidance_scale=0.0,
                height=args.size,
                width=args.size,
                generator=torch.Generator("cpu").manual_seed(seed),
                callback_on_step_end=on_step,
            ).images[0]
            path = out / f"{jid}_{role}.png"
            image.save(path)
            seconds = round(time.time() - t0, 3)
            views.append({"role": role, "path": str(path), "seconds": seconds})
            emit("view_done", id=jid, view=role, index=index, total=len(SD_VIEWS), path=str(path), seconds=seconds, attempt=1)
        emit("done", id=jid, ok=True, seconds=round(time.time() - started, 3), views=views)
    return 0


# --------------------------------------------------------------------------- FLUX.2 via ComfyUI

class ComfyProgressListener(threading.Thread):
    """Écoute minimale du websocket de ComfyUI (bibliothèque standard seulement).

    flux_reference_synth soumet ses graphes sans client_id : ComfyUI diffuse alors
    les messages « progress » (pas k/N du sampler) à tous les clients connectés.
    """

    def __init__(self, base: str, on_progress):
        super().__init__(daemon=True)
        self.base = base
        self.on_progress = on_progress
        self.stop_flag = threading.Event()
        self.connected = False
        self.ever_connected = False
        self.reconnects = 0
        self.error: str | None = None

    def run(self) -> None:
        # reconnexion avec attente croissante : un redémarrage de ComfyUI ne coupe pas la mesure
        delay = 1.0
        while not self.stop_flag.is_set():
            self._session()
            if self.stop_flag.is_set():
                break
            if self.ever_connected:
                self.reconnects += 1
            self.stop_flag.wait(delay)
            delay = min(10.0, delay * 2)

    def report(self) -> dict:
        return {"connected": self.connected, "reconnects": self.reconnects, "last_error": self.error}

    def _session(self) -> None:
        sock = None
        u = urllib.parse.urlparse(self.base)
        port = u.port or (443 if u.scheme == "https" else 80)
        try:
            sock = socket.create_connection((u.hostname, port), timeout=10)
            if u.scheme == "https":
                import ssl
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=u.hostname)
            key = base64.b64encode(os.urandom(16)).decode()
            path = u.path.rstrip("/") + f"/ws?clientId=aurora-bench-{uuid.uuid4().hex[:8]}"
            sock.sendall((
                f"GET {path} HTTP/1.1\r\nHost: {u.hostname}:{port}\r\nUpgrade: websocket\r\n"
                f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            ).encode())
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = sock.recv(4096)
                if not chunk:
                    raise OSError("websocket fermé pendant la poignée de main")
                head += chunk
            status, _, buf = head.partition(b"\r\n\r\n")
            if b" 101" not in status.split(b"\r\n", 1)[0]:
                raise OSError(status.split(b"\r\n", 1)[0].decode("latin-1"))
            self.connected = True
            self.ever_connected = True
            sock.settimeout(0.5)

            def need(n: int) -> bytes:
                nonlocal buf
                while len(buf) < n:
                    if self.stop_flag.is_set():
                        raise StopIteration
                    try:
                        chunk = sock.recv(65536)
                    except socket.timeout:
                        continue
                    if not chunk:
                        raise OSError("websocket fermé")
                    buf += chunk
                data, buf = buf[:n], buf[n:]
                return data

            while not self.stop_flag.is_set():
                b1, b2 = need(2)
                opcode = b1 & 0x0F
                length = b2 & 0x7F
                if length == 126:
                    length = int.from_bytes(need(2), "big")
                elif length == 127:
                    length = int.from_bytes(need(8), "big")
                mask = need(4) if b2 & 0x80 else None
                payload = need(length) if length else b""
                if mask:
                    payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
                if opcode == 8:
                    self.error = "websocket fermé par ComfyUI"
                    break
                if opcode == 9:  # ping -> pong (trame client masquée)
                    m = os.urandom(4)
                    sock.sendall(bytes([0x8A, 0x80 | len(payload)]) + m + bytes(c ^ m[i % 4] for i, c in enumerate(payload)))
                    continue
                if opcode != 1:
                    continue  # aperçus binaires
                try:
                    msg = json.loads(payload.decode("utf-8"))
                except ValueError:
                    continue
                if msg.get("type") == "progress":
                    d = msg.get("data") or {}
                    self.on_progress(int(d.get("value") or 0), int(d.get("max") or 0), d.get("prompt_id"))
        except StopIteration:
            pass
        except Exception as exc:  # pragma: no cover - dépend du serveur
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.connected = False
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


def run_comfy_flux2(args) -> int:
    sys.path.insert(0, str(SERVICES))
    import flux_reference_synth as frs  # producteur réel du module 3D

    base = args.comfy_base.rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/system_stats", timeout=10) as r:
            stats = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        emit("error", message=f"ComfyUI injoignable sur {base} : {type(exc).__name__}: {exc}")
        return 2
    models = frs.check_models_present(args.comfy_models_dir or None)
    if not models.get("ok"):
        emit("error", message="poids FLUX.2 absents ou tronqués", models=models)
        return 2
    devices = [d.get("name") for d in (stats.get("devices") or [])]
    emit("backend_ready", backend="comfy-flux2", unet=frs.DEFAULT_UNET, clip=frs.DEFAULT_CLIP,
         vae=frs.DEFAULT_VAE, devices=devices, models_checked=not models.get("skipped"))

    order = list(frs.MULTIVIEW_SUFFIXES)
    current: dict = {"jid": None, "view": None, "index": 0, "attempt": 0, "seconds": {}}

    def on_progress(value: int, maximum: int, prompt_id) -> None:
        if current["jid"] and current["view"] and maximum > 0:
            emit("step", id=current["jid"], view=ROLE.get(current["view"], current["view"]), index=current["index"],
                 total=len(order), step=value, steps=maximum, prompt_id=prompt_id)

    listener = ComfyProgressListener(base, on_progress)
    listener.start()
    deadline = time.time() + 5
    while not listener.connected and listener.error is None and time.time() < deadline:
        time.sleep(0.05)

    real_synth = frs.synth

    def traced_synth(prompt, run_id, **kw):
        jid = current["jid"]
        view = "front" if run_id == jid else run_id[len(jid) + 1:]
        index = order.index(view) if view in order else 0
        if index == 0:
            current["attempt"] += 1
            if current["attempt"] > 1:
                emit("attempt", id=jid, attempt=current["attempt"])
        current.update(view=view, index=index)
        emit("view_start", id=jid, view=ROLE.get(view, view), index=index, total=len(order), attempt=current["attempt"])
        t0 = time.time()
        try:
            res = real_synth(prompt, run_id, **kw)
        finally:
            current["view"] = None
        seconds = round(time.time() - t0, 3)
        if res.get("ok"):
            current["seconds"][view] = seconds
            emit("view_done", id=jid, view=ROLE.get(view, view), index=index, total=len(order),
                 path=res["reference_path"], seconds=seconds, attempt=current["attempt"])
        else:
            emit("view_failed", id=jid, view=ROLE.get(view, view), error=str(res.get("error"))[:300])
        return res

    frs.synth = traced_synth
    out = Path(args.output_dir)
    for job in jobs():
        jid = str(job.get("id") or int(time.time()))
        request = str(job["request"])
        current.update(jid=jid, view=None, index=0, attempt=0, seconds={})
        started = time.time()
        emit("start", id=jid, request=request, backend="comfy-flux2", websocket=listener.connected)
        result = frs.synth_multiview(
            request, jid, output_dir=out, width=args.size, height=args.size, steps=args.steps,
            seed=job.get("seed"), comfy_base=base, subject_kind=job.get("subject_kind"),
            motion_prompt=job.get("motion_prompt"),
        )
        audit = result.get("turnaround_audit") or {}
        views = [
            {"role": ROLE.get(v, v), "path": info.get("path"), "seconds": current["seconds"].get(v)}
            for v, info in (result.get("views") or {}).items()
        ]
        emit("done", id=jid, ok=bool(result.get("ok")), seconds=round(time.time() - started, 3), views=views,
             attempts=len(result.get("attempts") or []), audit_failures=(audit.get("failures") or [])[:6],
             error=result.get("error"), websocket=listener.report())
        current["jid"] = None
    listener.stop_flag.set()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--backend", choices=("comfy-flux2", "sd-turbo"), default="comfy-flux2")
    parser.add_argument("--model", default="stabilityai/sd-turbo", help="sd-turbo seulement")
    parser.add_argument("--comfy-base", default="http://127.0.0.1:8188")
    parser.add_argument("--comfy-models-dir", default="", help="dossier models de ComfyUI (contrôle des poids)")
    parser.add_argument("--steps", type=int, default=0, help="0 = défaut du producteur (4 SD-Turbo, 25 FLUX.2)")
    parser.add_argument("--size", type=int, default=0, help="0 = défaut du producteur (512 SD-Turbo, 1024 FLUX.2)")
    parser.add_argument("--threads", type=int, default=0)
    args = parser.parse_args()
    flux = args.backend == "comfy-flux2"
    args.steps = args.steps or (25 if flux else 4)
    args.size = args.size or (1024 if flux else 512)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    return run_comfy_flux2(args) if flux else run_sd_turbo(args)


if __name__ == "__main__":
    raise SystemExit(main())
