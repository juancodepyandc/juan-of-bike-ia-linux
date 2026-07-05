"""
_compat.py -- Compatibility shims pour torchaudio + speechbrain sur Windows.

Doit etre importe AVANT toute utilisation de TTS, F5-TTS ou SpeechBrain.

Bugs corriges:

1. torchaudio.load casse depuis 2.9 sur Windows: il delegue tout a torchcodec,
   qui necessite les DLL "full-shared" FFmpeg (avcodec/avformat/avutil) dans
   le PATH. On les a pas. On remplace torchaudio.load par un chargeur base
   sur soundfile + libsndfile (dependances natives deja installees).

2. SpeechBrain 1.1.0 enregistre `speechbrain.integrations.k2_fsa` comme
   LazyModule. Quand inspect.stack() traverse sys.modules (cas frequent
   dans lazy_loader/scipy), il appelle hasattr(module, '__file__') ce qui
   declenche le chargement reel du LazyModule -> echoue car k2_fsa n'est
   pas installe -> propagation ImportError au consommateur.
   On patche LazyModule.ensure_module pour renvoyer un stub vide en cas
   d'echec d'import au lieu de propager l'erreur.
"""

from __future__ import annotations

import types as _types


def _patch_torchaudio_load():
    try:
        import torchaudio as _ta
        import torch as _torch
        import soundfile as _sf
    except Exception:
        return

    def _load_via_soundfile(
        uri,
        frame_offset: int = 0,
        num_frames: int = -1,
        normalize: bool = True,
        channels_first: bool = True,
        format=None,
        buffer_size: int = 4096,
        backend=None,
    ):
        audio, sr = _sf.read(str(uri), dtype="float32")
        if audio.ndim == 1:
            audio = audio[None, :]  # (1, frames)
        else:
            audio = audio.T  # (channels, frames)
        if frame_offset > 0:
            audio = audio[:, frame_offset:]
        if num_frames > 0:
            audio = audio[:, :num_frames]
        if not channels_first:
            audio = audio.T
        return _torch.from_numpy(audio.copy()), sr

    _ta.load = _load_via_soundfile


def _patch_speechbrain_lazy():
    try:
        import speechbrain.utils.importutils as _siu
    except Exception:
        return

    if getattr(_siu.LazyModule, "_aurora_safe_patched", False):
        return

    _orig_ensure = _siu.LazyModule.ensure_module

    def _safe_ensure(self, stacklevel: int = 0):
        try:
            return _orig_ensure(self, stacklevel + 1)
        except ImportError:
            target_name = getattr(self, "lazy_module", None) or getattr(self, "__name__", "stub")
            stub = _types.ModuleType(str(target_name))
            stub.__file__ = "<aurora-stub>"
            stub.__path__ = []  # type: ignore[attr-defined]
            return stub

    _siu.LazyModule.ensure_module = _safe_ensure
    _siu.LazyModule._aurora_safe_patched = True


def apply():
    """Apply all compat shims. Idempotent."""
    _patch_torchaudio_load()
    _patch_speechbrain_lazy()


# Auto-apply on import so caller just does `import cinema._compat`
apply()
