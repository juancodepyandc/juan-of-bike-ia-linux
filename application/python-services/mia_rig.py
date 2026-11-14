"""mia_rig.py — headless runner for Make-It-Animatable (MIA).

Usage:
    python mia_rig.py IN.glb [rest_pose_type] [reset_to_rest] [no_fingers]

Args:
    rest_pose_type  T-pose | A-pose | 大-pose | No   (default: A-pose)
    reset_to_rest   0 | 1                            (default: 1)
    no_fingers      0 | 1                            (default: 0 — 52 Mixamo bones with fingers)

Output:
    <input_basename>/<input_basename>.fbx  (MIA anim_path)
    <input_basename>/<input_basename>.glb  (MIA anim_vis_path, converted with FBX2glTF native + PBR sanitized)

Requires the conda env `mia` (torch 2.11+cu128, pytorch3d CPU-only, trimesh, etc.).
"""
from __future__ import annotations

import os
import shutil
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
    if mia_root not in sys.path:
        sys.path.insert(0, mia_root)
    m = types.ModuleType("util.dataset_mixamo_additional")
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
        @staticmethod
        def postprocess(*a, **kw):
            return None

        def __init__(self, *a, **kw):
            pass

        def __call__(self, *a, **kw):
            return self

        def __getattr__(self, name):
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
    """Install unique object sentinels for module-level gr components."""
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


def _sanitize_glb_pbr(glb_path: str) -> None:
    """FBX2glTF sets metallicFactor=0.40, roughnessFactor=0.3746 and Armature.scale=0.01
    on FBX exports, causing shiny PVC materials and a 100x camera zoom/clipping bug in F3D.
    Restore natural matte PBR, normalize scale=(1,1,1) and ground Z=0.0 while preserving
    MIA's neural T-pose."""
    if not glb_path or not os.path.isfile(glb_path):
        return
    try:
        import bpy  # type: ignore
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=glb_path)
        for o in list(bpy.context.scene.objects):
            if o.type == "MESH" and o.data.vertices and not any(v.groups for v in o.data.vertices):
                bpy.data.objects.remove(o, do_unlink=True)
        for mat in bpy.data.materials:
            if not getattr(mat, "node_tree", None):
                continue
            for node in mat.node_tree.nodes:
                if node.type == "BSDF_PRINCIPLED":
                    if "Metallic" in node.inputs:
                        inp_m = node.inputs["Metallic"]
                        if not inp_m.is_linked and float(inp_m.default_value) > 0.05:
                            inp_m.default_value = 0.0
                    if "Roughness" in node.inputs:
                        inp_r = node.inputs["Roughness"]
                        if not inp_r.is_linked and float(inp_r.default_value) < 0.55:
                            inp_r.default_value = 0.72
                    if "Specular IOR Level" in node.inputs and not node.inputs["Specular IOR Level"].is_linked:
                        node.inputs["Specular IOR Level"].default_value = 0.35
        arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        rig = arms[0] if arms else None
        if rig is not None:
            bpy.context.scene.frame_set(1)
            bpy.context.view_layer.update()
            saved_rot = {}
            for pb in rig.pose.bones:
                pb.rotation_mode = "QUATERNION"
                saved_rot[pb.name] = pb.rotation_quaternion.copy()
            if rig.animation_data:
                rig.animation_data_clear()
            for pb in rig.pose.bones:
                pb.location = (0.0, 0.0, 0.0)
                pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                pb.scale = (1.0, 1.0, 1.0)
            bpy.context.view_layer.update()
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")
            rig.select_set(True)
            for m in meshes:
                m.select_set(True)
            bpy.context.view_layer.objects.active = rig
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            bpy.context.view_layer.update()
            min_z = min(
                ((m.matrix_world @ v.co).z for m in meshes for v in m.data.vertices),
                default=0.0,
            )
            if abs(min_z) > 1e-5:
                rig.location.z -= min_z
                bpy.context.view_layer.update()
                bpy.ops.object.select_all(action="DESELECT")
                rig.select_set(True)
                for m in meshes:
                    m.select_set(True)
                bpy.context.view_layer.objects.active = rig
                bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
                bpy.context.view_layer.update()
            rig.animation_data_create()
            act = bpy.data.actions.new(name="MIA_TPose")
            rig.animation_data.action = act
            for f in (1, 2):
                bpy.context.scene.frame_set(f)
                for bname, q in saved_rot.items():
                    pb = rig.pose.bones.get(bname)
                    if pb:
                        pb.rotation_mode = "QUATERNION"
                        pb.rotation_quaternion = q
                        pb.keyframe_insert(data_path="rotation_quaternion", frame=f)
        bpy.ops.export_scene.gltf(
            filepath=glb_path,
            check_existing=False,
            use_selection=False,
            export_animations=True,
            export_animation_mode="ACTIONS",
        )
    except Exception as exc:
        print(f"[mia_rig] PBR sanitize warning: {exc!r}", flush=True)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    inp = os.path.abspath(sys.argv[1])
    rest_pose_type = sys.argv[2] if len(sys.argv) > 2 else "A-pose"
    reset_to_rest = bool(int(sys.argv[3])) if len(sys.argv) > 3 else True
    no_fingers = bool(int(sys.argv[4])) if len(sys.argv) > 4 else False
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

    os.chdir(MIA_ROOT)
    if MIA_ROOT not in sys.path:
        sys.path.insert(0, MIA_ROOT)

    _stub_gradio()
    _stub_dataset_mixamo_additional(MIA_ROOT)

    import app  # type: ignore

    _install_ui_sentinels()
    _tame_gradio_logging()

    print("[mia] init_models() ...", flush=True)
    app.init_models()
    print(f"[mia] init_models done. Running pipeline on {inp}", flush=True)

    db = app.DB()
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
    for i, _step in enumerate(gen):
        print(f"[mia] step {i} yielded", flush=True)

    fbx_path = db.anim_path
    glb_path = db.anim_vis_path
    # Prefer rest_vis_path (direct Blender glTF export with intact PBR materials) if available
    if getattr(db, "rest_vis_path", None) and os.path.isfile(db.rest_vis_path) and glb_path:
        try:
            shutil.copyfile(db.rest_vis_path, glb_path)
        except Exception:
            pass
    _sanitize_glb_pbr(glb_path)
    try:
        _svc_dir = os.path.dirname(os.path.abspath(__file__))
        if _svc_dir not in sys.path:
            sys.path.insert(0, _svc_dir)
        from pbr_cartography import transfer_pbr_from_source_glb
        transfer_pbr_from_source_glb(inp, glb_path)
    except Exception as _pbr_exc:
        print(f"[mia_rig] PBR transfer warning: {_pbr_exc!r}", flush=True)
    print(f"MIA_OK fbx={fbx_path} glb={glb_path}", flush=True)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
