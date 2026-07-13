"""mia_rig.py — headless runner for Make-It-Animatable (MIA).

Usage:
    python mia_rig.py IN.glb [rest_pose_type] [reset_to_rest] [no_fingers]

Args:
    rest_pose_type  T-pose | A-pose | 大-pose | No   (default: A-pose)
    reset_to_rest   0 | 1                            (default: 1)
    no_fingers      0 | 1                            (default: 1 — humain=arms down, hands closed)

Output:
    <input_basename>/<input_basename>.fbx  (MIA anim_path)
    <input_basename>/<input_basename>.glb  (MIA anim_vis_path, converted with FBX2glTF native)

Requires the conda env `mia` (torch 2.11+cu128, pytorch3d CPU-only, trimesh, etc.).
"""
from __future__ import annotations

import os
import sys
import types


def _stub_dataset_mixamo_additional(mia_root: str) -> None:
    """Stub `util.dataset_mixamo_additional` — it references `bones_vroid.fbx` (VRoid
    dataset) which we do NOT have. MIA imports it eagerly from `app.py`, but
    ADDITIONAL_BONES=False in our path so its symbols are never actually used.

    Stub MUST be registered in sys.modules BEFORE `import app`."""
    for name in ("util.dataset_mixamo_additional", "dataset_mixamo_additional"):
        if name in sys.modules and hasattr(sys.modules[name], "BONES_IDX_DICT"):
            return
    # Make sure the `util` package is discoverable — MIA has no util/__init__.py,
    # so python 3 treats `util` as an implicit namespace package as long as its
    # parent dir is on sys.path (mia_root is inserted in main()).
    if mia_root not in sys.path:
        sys.path.insert(0, mia_root)
    m = types.ModuleType("util.dataset_mixamo_additional")
    # Dummies with the right types; app.py only reads them under `if ADDITIONAL_BONES`.
    m.BONES_IDX_DICT = {}
    m.JOINTS_NUM = 0
    m.KINEMATIC_TREE = []
    m.TEMPLATE_PATH = os.path.join(mia_root, "data/Mixamo/bones.fbx")
    m.MIXAMO_PREFIX = "mixamorig:"
    sys.modules["util.dataset_mixamo_additional"] = m
    sys.modules["dataset_mixamo_additional"] = m


def _stub_gradio() -> None:
    """MIA imports gradio and monkey-patches `gr.Checkbox.postprocess`, uses
    `gradio.helpers.log_message`, and needs `gr.Info`/`gr.Warning`/`gr.Error` at
    runtime. Real gradio is installed (>=6.x) in the `mia` env so just let it
    load. If for some reason it's not importable, fall back to a stub."""
    try:
        import gradio as _gr  # type: ignore
        _ = _gr.Info, _gr.Warning, _gr.Error  # sanity
        import gradio.helpers  # noqa: F401
        return
    except Exception as e:
        print(f"[mia_rig] Real gradio unavailable ({e!r}); using stub.", flush=True)
    gr = types.ModuleType("gradio")

    def _info(msg, *a, **kw):
        print(f"[gr.Info] {msg}")

    def _warn(msg, *a, **kw):
        print(f"[gr.Warning] {msg}")

    class _Err(Exception):
        pass

    class _Noop:
        # `postprocess` is monkey-patched by MIA's app.py at import time
        # (`Checkbox_postprocess = gr.Checkbox.postprocess`), so we need it
        # to exist on the class object.
        @staticmethod
        def postprocess(*a, **kw):
            return None

        def __init__(self, *a, **kw):
            pass

        def __call__(self, *a, **kw):
            return self

        def __getattr__(self, name):
            # Return a no-op callable for anything the pipeline queries
            def _f(*a, **kw):
                return None
            return _f

    gr.Info = _info
    gr.Warning = _warn
    gr.Error = _Err
    gr.State = _Noop
    gr.Blocks = _Noop
    gr.Row = _Noop
    gr.Column = _Noop
    gr.Group = _Noop
    gr.Accordion = _Noop
    gr.Checkbox = _Noop
    gr.Dropdown = _Noop
    gr.Slider = _Noop
    gr.Radio = _Noop
    gr.Markdown = _Noop
    gr.Button = _Noop
    gr.Model3D = _Noop
    gr.File = _Noop
    gr.CheckboxGroup = _Noop
    gr.Textbox = _Noop
    gr.Number = _Noop
    gr.Image = _Noop
    gr.Video = _Noop
    gr.Gallery = _Noop
    gr.HTML = _Noop

    def skip():
        return None

    gr.skip = skip
    sys.modules["gradio"] = gr


def _tame_gradio_logging() -> None:
    """MIA replaces `gradio.helpers.log_message` with one that reads
    `LocalContext.blocks.get()` — this raises LookupError outside a Blocks
    context. Replace with plain prints so `gr.Info`/`gr.Warning` don't crash."""
    try:
        import gradio as gr  # type: ignore
        import gradio.helpers  # type: ignore

        def _print_msg(msg, *a, level="info", **kw):
            print(f"[gr.{level}] {msg}", flush=True)

        gradio.helpers.log_message = _print_msg
        gr.Info = lambda msg, *a, **kw: print(f"[gr.Info] {msg}", flush=True)
        gr.Warning = lambda msg, *a, **kw: print(f"[gr.Warning] {msg}", flush=True)
    except Exception as e:
        print(f"[mia_rig] tame_gradio_logging skipped: {e!r}", flush=True)


def _install_ui_sentinels() -> None:
    """MIA's `_pipeline` yields dicts keyed by module-level gr components (`state`,
    `output_joints_coarse`, `output_normed_input`, `output_sample`, `output_joints`,
    `output_bw`, `output_rest_vis`, `output_rest_lbs`, `output_anim_vis`, `output_anim`)
    that only exist after init_blocks() runs. We install unique object sentinels for
    them so `{state: db}` literals don't crash — the dicts are discarded anyway."""
    import app  # type: ignore

    def _noop(*a, **kw):
        return None

    if hasattr(app, "change_Model3D"):
        app.change_Model3D = _noop
    for name in (
        "state",
        "output_joints_coarse",
        "output_normed_input",
        "output_sample",
        "output_joints",
        "output_bw",
        "output_rest_vis",
        "output_rest_lbs",
        "output_anim_vis",
        "output_anim",
    ):
        if not hasattr(app, name):
            setattr(app, name, object())


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    inp = os.path.abspath(sys.argv[1])
    rest_pose_type = sys.argv[2] if len(sys.argv) > 2 else "A-pose"
    reset_to_rest = bool(int(sys.argv[3])) if len(sys.argv) > 3 else True
    no_fingers = bool(int(sys.argv[4])) if len(sys.argv) > 4 else True
    if not os.path.isfile(inp):
        print(f"MIA_ERROR: input not found: {inp}", flush=True)
        return 2

    MIA_ROOT = os.environ.get(
        "MIA_ROOT",
        os.path.expanduser("~/.local/share/auroraia/external/Make-It-Animatable"),
    )
    if not os.path.isdir(MIA_ROOT):
        print(f"MIA_ERROR: MIA not installed at {MIA_ROOT}", flush=True)
        return 3

    # MIA uses cwd-relative paths (output/, data/, util/FBX2glTF)
    prev_cwd = os.getcwd()
    os.chdir(MIA_ROOT)
    if MIA_ROOT not in sys.path:
        sys.path.insert(0, MIA_ROOT)

    _stub_gradio()
    _stub_dataset_mixamo_additional(MIA_ROOT)

    # Import MIA app
    import app  # type: ignore

    _install_ui_sentinels()
    _tame_gradio_logging()

    print(f"[mia] init_models() ...", flush=True)
    app.init_models()
    print(f"[mia] init_models done. Running pipeline on {inp}", flush=True)

    db = app.DB()
    # export_temp=True avoids polluting the input's parent directory; we resolve out paths below.
    # inplace=True: keep the animation baked in the rest T-pose (no NLA push).
    # retarget=True but animation_file=None → just rig, no animation applied.
    gen = app._pipeline(
        input_path=inp,
        is_gs=False,
        opacity_threshold=0.0,
        no_fingers=no_fingers,
        rest_pose_type=rest_pose_type if rest_pose_type != "No" else None,
        ignore_pose_parts=None,
        input_normal=False,
        bw_fix=True,
        bw_vis_bone="LeftArm",
        reset_to_rest=reset_to_rest,
        animation_file=None,
        retarget=True,
        inplace=True,
        db=db,
        export_temp=False,
    )
    for i, step in enumerate(gen):
        print(f"[mia] step {i} yielded", flush=True)

    fbx_path = db.anim_path
    glb_path = db.anim_vis_path
    print(f"MIA_OK fbx={fbx_path} glb={glb_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
