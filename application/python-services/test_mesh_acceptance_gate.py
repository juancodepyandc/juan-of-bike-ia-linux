from __future__ import annotations

import unittest
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mesh_acceptance_gate import (
    _animation_markers,
    _strimer_plus_v2_markers,
    evaluate_acceptance,
    prompt_expectations,
)

try:
    import numpy as np
    import trimesh
    from PIL import Image
    from pygltflib import (
        Accessor,
        Animation,
        AnimationChannel,
        AnimationChannelTarget,
        AnimationSampler,
        Buffer,
        BufferView,
        GLTF2,
    )

    HAS_GLB_FIXTURE_DEPS = True
except Exception:
    HAS_GLB_FIXTURE_DEPS = False


FLOAT = 5126


def _uv_for(mesh):
    vertices = np.asarray(mesh.vertices).copy()
    x_vals, y_vals, z_vals = vertices[:, 0], vertices[:, 1], vertices[:, 2]
    u_vals = (np.arctan2(z_vals, x_vals) / (2 * np.pi) + 0.5) % 1.0
    radius = np.linalg.norm(vertices, axis=1)
    radius[radius == 0] = 1
    v_vals = np.clip(y_vals / radius, -1, 1)
    t_vals = 0.5 - np.arcsin(v_vals) / np.pi
    return np.column_stack([u_vals, t_vals])


def _make_texture(color):
    arr = np.asarray(Image.new("RGB", (64, 64), tuple(color))).copy()
    for y_val in range(64):
        for x_val in range(64):
            arr[y_val, x_val, 0] = (int(arr[y_val, x_val, 0]) + x_val * 3 + y_val) % 255
            arr[y_val, x_val, 1] = (int(arr[y_val, x_val, 1]) + y_val * 4) % 255
            arr[y_val, x_val, 2] = (int(arr[y_val, x_val, 2]) + x_val * y_val) % 255
    return Image.fromarray(arr)


def _textured_part(name, scale, translation, color):
    mesh = trimesh.creation.icosphere(subdivisions=5, radius=1.0)
    mesh.apply_scale(scale)
    mesh.apply_translation(translation)
    texture = _make_texture(color)
    material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=texture,
        metallicFactor=0.1,
        roughnessFactor=0.65,
    )
    mesh.visual = trimesh.visual.TextureVisuals(
        uv=_uv_for(mesh),
        material=material,
        image=texture,
    )
    mesh.metadata["name"] = name
    return mesh


def _add_animation(glb_path: Path, *, root_only: bool = False):
    gltf = GLTF2().load_binary(str(glb_path))
    mesh_nodes = [index for index, node in enumerate(gltf.nodes or []) if node.mesh is not None]
    if not root_only and len(mesh_nodes) < 2:
        raise AssertionError("fixture needs at least two mesh nodes for real part animation")

    blob = gltf.binary_blob() or b""

    def padded(raw: bytes) -> bytes:
        return raw + (b"\x00" * ((4 - len(raw) % 4) % 4))

    blob = padded(blob)
    if not gltf.buffers:
        gltf.buffers = [Buffer(byteLength=0)]

    def append_accessor(data, accessor_type, count, mins=None, maxs=None):
        nonlocal blob
        blob = padded(blob)
        offset = len(blob)
        raw = np.asarray(data, dtype=np.float32).tobytes()
        blob += raw
        if gltf.bufferViews is None:
            gltf.bufferViews = []
        view_index = len(gltf.bufferViews)
        gltf.bufferViews.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(raw)))
        if gltf.accessors is None:
            gltf.accessors = []
        accessor_index = len(gltf.accessors)
        gltf.accessors.append(
            Accessor(
                bufferView=view_index,
                byteOffset=0,
                componentType=FLOAT,
                count=count,
                type=accessor_type,
                min=mins,
                max=maxs,
            )
        )
        return accessor_index

    time_accessor = append_accessor([0.0, 1.0, 2.0], "SCALAR", 3, [0.0], [2.0])
    rotation_a = append_accessor(
        [[0, 0, 0, 1], [0, 0.382683, 0, 0.92388], [0, 0, 0, 1]],
        "VEC4",
        3,
    )
    samplers = [AnimationSampler(input=time_accessor, output=rotation_a, interpolation="LINEAR")]
    channels = [
        AnimationChannel(
            sampler=0,
            target=AnimationChannelTarget(node=0 if root_only else mesh_nodes[0], path="rotation"),
        )
    ]
    if not root_only:
        rotation_b = append_accessor(
            [[0, 0, 0, 1], [0.258819, 0, 0, 0.965926], [0, 0, 0, 1]],
            "VEC4",
            3,
        )
        samplers.append(AnimationSampler(input=time_accessor, output=rotation_b, interpolation="LINEAR"))
        channels.append(
            AnimationChannel(
                sampler=1,
                target=AnimationChannelTarget(node=mesh_nodes[1], path="rotation"),
            )
        )

    if gltf.animations is None:
        gltf.animations = []
    gltf.animations.append(Animation(name="fixture_motion", samplers=samplers, channels=channels))
    gltf.buffers[0].byteLength = len(blob)
    gltf.set_binary_blob(blob)
    gltf.save_binary(str(glb_path))


def _build_textured_multipart_glb(glb_path: Path, *, root_only: bool = False):
    scene = trimesh.Scene()
    scene.add_geometry(
        _textured_part("body", [1.8, 0.7, 0.45], [0, 0, 0], [160, 80, 40]),
        node_name="body",
    )
    scene.add_geometry(
        _textured_part("fan", [0.35, 0.35, 0.12], [1.1, 0.0, 0.15], [40, 120, 210]),
        node_name="fan",
    )
    scene.export(glb_path)
    _add_animation(glb_path, root_only=root_only)


def _flat_material_part(name, scale, translation, color):
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    mesh.apply_scale(scale)
    mesh.apply_translation(translation)
    material = trimesh.visual.material.PBRMaterial(
        baseColorFactor=[color[0] / 255, color[1] / 255, color[2] / 255, 1.0],
        metallicFactor=0.0,
        roughnessFactor=0.8,
    )
    mesh.visual = trimesh.visual.TextureVisuals(
        uv=_uv_for(mesh),
        material=material,
    )
    mesh.metadata["name"] = name
    return mesh


def _build_flat_humanoid_glb(glb_path: Path):
    scene = trimesh.Scene()
    parts = [
        ("Head_Simple", [0.16, 0.18, 0.16], [0, 1.55, 0], [220, 170, 140]),
        ("Torso_Simple", [0.34, 0.55, 0.18], [0, 0.95, 0], [210, 50, 40]),
        ("Hand_L_Simple", [0.055, 0.055, 0.045], [-0.46, 0.78, 0], [220, 170, 140]),
        ("Hand_R_Simple", [0.055, 0.055, 0.045], [0.46, 0.78, 0], [220, 170, 140]),
        ("Leg_L_Simple", [0.08, 0.42, 0.08], [-0.12, 0.28, 0], [40, 60, 130]),
        ("Leg_R_Simple", [0.08, 0.42, 0.08], [0.12, 0.28, 0], [40, 60, 130]),
    ]
    for name, scale, translation, color in parts:
        scene.add_geometry(
            _flat_material_part(name, scale, translation, color),
            node_name=name,
        )
    scene.export(glb_path)


class PromptExpectationTests(unittest.TestCase):
    def test_realistic_texture_and_motion_are_detected(self):
        exp = prompt_expectations(
            "modele 3D realiste avec texture cuir, ventilateur qui tourne",
            expected_kind="product",
        )
        self.assertTrue(exp["wants_realism"])
        self.assertTrue(exp["wants_texture"])
        self.assertTrue(exp["wants_motion"])

    def test_user_rejecting_basic_shapes_does_not_allow_cube(self):
        exp = prompt_expectations(
            "pas de cube ou forme basique, je veux un vrai modele 3D",
            expected_kind="product",
        )
        self.assertFalse(exp["allows_basic_primitive"])
        self.assertTrue(exp["wants_realism"])

    def test_explicit_primitive_stays_allowed_when_not_realism_request(self):
        exp = prompt_expectations("un cube lowpoly rouge", expected_kind="generic")
        self.assertTrue(exp["allows_basic_primitive"])
        self.assertFalse(exp["wants_texture"])

    def test_printable_cad_without_material_stays_texture_optional(self):
        exp = prompt_expectations("piece CAD imprimable STL 3D", expected_kind="product")
        self.assertTrue(exp["printable_only"])
        self.assertFalse(exp["wants_texture"])


class MotionMarkerTests(unittest.TestCase):
    def test_root_only_animation_is_not_real_motion(self):
        gltf = {
            "nodes": [{"name": "Root"}],
            "animations": [
                {
                    "channels": [
                        {"target": {"node": 0, "path": "rotation"}},
                    ],
                },
            ],
        }
        out = _animation_markers(gltf)
        self.assertTrue(out["has_animations"])
        self.assertTrue(out["root_only"])
        self.assertFalse(out["has_real_motion"])

    def test_aurora_runtime_material_extras_count_as_motion(self):
        gltf = {
            "materials": [
                {"extras": {"aurora_led_emission": {"schema": "aurora.led-emission.v1"}}},
            ],
        }
        out = _animation_markers(gltf)
        self.assertFalse(out["has_animations"])
        self.assertTrue(out["has_runtime_motion_extras"])
        self.assertTrue(out["has_real_motion"])

    def test_belt_scroll_runtime_extras_count_as_motion(self):
        gltf = {
            "materials": [
                {"extras": {"aurora_belt_scroll": {"schema": "aurora.belt-scroll.v1"}}},
            ],
        }
        out = _animation_markers(gltf)
        self.assertFalse(out["has_animations"])
        self.assertTrue(out["has_runtime_motion_extras"])
        self.assertTrue(out["has_real_motion"])

    def test_single_body_animation_is_not_articulated_locomotion(self):
        gltf = {
            "nodes": [{"name": "Root"}, {"name": "Body"}],
            "animations": [
                {
                    "channels": [
                        {"target": {"node": 1, "path": "translation"}},
                        {"target": {"node": 1, "path": "rotation"}},
                    ],
                },
            ],
        }
        out = _animation_markers(gltf)
        self.assertTrue(out["has_real_motion"])
        self.assertFalse(out["has_limb_targets"])
        self.assertFalse(out["has_articulated_locomotion"])

    def test_limb_animation_counts_as_articulated_locomotion(self):
        gltf = {
            "nodes": [
                {"name": "Root"},
                {"name": "pelvis"},
                {"name": "foot_ik.L"},
                {"name": "foot_ik.R"},
                {"name": "hand_ik.L"},
            ],
            "animations": [
                {
                    "channels": [
                        {"target": {"node": 1, "path": "translation"}},
                        {"target": {"node": 2, "path": "translation"}},
                        {"target": {"node": 3, "path": "translation"}},
                        {"target": {"node": 4, "path": "rotation"}},
                    ],
                },
            ],
        }
        out = _animation_markers(gltf)
        self.assertTrue(out["has_limb_targets"])
        self.assertTrue(out["has_articulated_locomotion"])

    def test_macarena_marker_rejects_incomplete_body_coverage(self):
        gltf = {
            "nodes": [
                {"name": "Performer_Rig_Root"},
                {"name": "spine_chest_dance_pivot"},
                {"name": "upper_arm_L_macarena_pivot"},
                {"name": "upper_arm_R_macarena_pivot"},
                {"name": "forearm_L_macarena_pivot"},
                {"name": "forearm_R_macarena_pivot"},
            ],
            "accessors": [{"count": 13}],
            "animations": [
                {
                    "samplers": [{"input": 0, "interpolation": "CUBICSPLINE"}],
                    "channels": [
                        {"sampler": 0, "target": {"node": i, "path": "rotation"}}
                        for i in range(6)
                    ],
                },
            ],
        }
        out = _animation_markers(gltf)
        self.assertFalse(out["macarena_ready"])
        self.assertFalse(out["floss_ready"])
        self.assertIn("head", out["macarena_missing_parts"])
        self.assertIn("shoulders", out["macarena_missing_parts"])
        self.assertIn("hands", out["macarena_missing_parts"])
        self.assertIn("legs", out["macarena_missing_parts"])
        self.assertIn("shoulders", out["floss_missing_parts"])
        self.assertIn("hands", out["floss_missing_parts"])
        self.assertIn("legs", out["floss_missing_parts"])

    def test_macarena_marker_requires_full_body_single_clip(self):
        nodes = [
            "Performer_Rig_Root",
            "spine_chest_dance_pivot",
            "head_neck_macarena_pivot",
            "shoulder_L_macarena_pivot",
            "shoulder_R_macarena_pivot",
            "upper_arm_L_macarena_pivot",
            "upper_arm_R_macarena_pivot",
            "forearm_L_macarena_pivot",
            "forearm_R_macarena_pivot",
            "Hand_L_Separated_Fingers_Mitten",
            "Hand_R_Separated_Fingers_Mitten",
            "thigh_L_dance_pivot",
            "thigh_R_dance_pivot",
            "shin_L_dance_pivot",
            "shin_R_dance_pivot",
        ]
        gltf = {
            "nodes": [{"name": name} for name in nodes],
            "accessors": [{"count": 13}],
            "animations": [
                {
                    "samplers": [{"input": 0, "interpolation": "CUBICSPLINE"}],
                    "channels": [
                        {"sampler": 0, "target": {"node": 0, "path": "translation"}},
                        *(
                            {"sampler": 0, "target": {"node": i, "path": "rotation"}}
                            for i in range(1, len(nodes))
                        ),
                    ],
                },
            ],
        }
        out = _animation_markers(gltf)
        self.assertTrue(out["macarena_ready"], out)
        self.assertTrue(out["floss_ready"], out)
        self.assertFalse(out["macarena_missing_parts"])
        self.assertFalse(out["floss_missing_parts"])
        self.assertEqual(out["animation_count"], 1)
        self.assertGreaterEqual(out["max_keyframes_per_sampler"], 10)


class ProductMarkerTests(unittest.TestCase):
    def test_strimer_markers_detect_reference_parts(self):
        gltf = {
            "nodes": [
                {"name": "StrimerV2_reference_root", "extras": {"aurora_product_reference": {"product": "Lian Li Strimer Plus V2"}}},
                {"name": "StrimerV2_BondedSiliconeCore_guides_and_cables_fused"},
                *({"name": f"StrimerV2_LightGuide_{i:02d}_continuous_diffuser_channel_0"} for i in range(12)),
                *({"name": f"StrimerV2_LED_{i:02d}_00_emit_channel_0"} for i in range(120)),
                *({"name": f"StrimerV2_LowerCable_{i:02d}_single_row_TPE"} for i in range(24)),
                {"name": "StrimerV2_Connector_PSU_black_input_block"},
                {"name": "StrimerV2_Connector_Motherboard_24pin_black_output_block"},
                *({"name": f"StrimerV2_24pin_socket_recess_r0_c{i:02d}"} for i in range(24)),
                *({"name": f"StrimerV2_24pin_input_contact_pin_r0_c{i:02d}"} for i in range(24)),
                *({"name": f"StrimerV2_StableClip_{i:02d}_black_bridge"} for i in range(6)),
                {"name": "StrimerV2_SideLightStrip_front_multi_direction_emit"},
                {"name": "StrimerV2_SideLightStrip_back_multi_direction_emit"},
                {"name": "StrimerV2_LIAN_LI_logo_text_mesh"},
            ],
            "materials": [
                {"name": "Mat_StrimerV2_translucent_diffuser_texture", "extras": {"aurora_surface_texture": {"schema": "aurora.surface-texture.v1"}}},
                *(
                    {
                        "name": f"StrimerV2_LEDMat_{i:02d}",
                        "extras": {"aurora_led_emission": {"schema": "aurora.led-emission.v1", "channel_index": i % 6}},
                    }
                    for i in range(120)
                ),
            ],
        }
        out = _strimer_plus_v2_markers(gltf)
        self.assertEqual(out["light_guides"], 12)
        self.assertEqual(out["addressable_led_cells"], 120)
        self.assertEqual(out["lower_cables"], 24)
        self.assertEqual(out["connector_blocks"], 2)
        self.assertEqual(out["bonded_core"], 1)
        self.assertEqual(out["runtime_channels"], 6)
        self.assertEqual(out["input_contact_pins"], 24)
        self.assertEqual(out["free_tail_cables"], 0)
        self.assertTrue(out["product_reference"])
        self.assertTrue(out["has_surface_texture_extras"])


@unittest.skipUnless(HAS_GLB_FIXTURE_DEPS, "GLB fixture dependencies are unavailable")
class FullAcceptanceGateTests(unittest.TestCase):
    def test_accepts_textured_multipart_glb_with_real_part_animation(self):
        with TemporaryDirectory() as tmp_dir:
            glb_path = Path(tmp_dir) / "real_textured_motion.glb"
            _build_textured_multipart_glb(glb_path)

            report = evaluate_acceptance(
                glb_path,
                "vrai modele 3D realiste avec texture metal brosse et ventilateur qui tourne",
                expected_kind="product",
            )

        self.assertTrue(report["acceptance_ok"], report["hard_failures"])
        self.assertGreaterEqual(report["engineer_grade"], report["threshold"])
        self.assertEqual(report["visual_audit"]["visual_grade"], 100)
        self.assertGreaterEqual(report["visual_audit"]["n_materials"], 2)
        self.assertGreaterEqual(report["visual_audit"]["n_textures"], 2)
        self.assertGreaterEqual(report["visual_audit"]["parts_count"], 2)
        self.assertTrue(report["visual_audit"]["has_uv_map"])
        self.assertTrue(report["motion_audit"]["has_real_motion"])
        self.assertFalse(report["suggested_fixes"])
        if report["quality_score"].get("retry_reasons"):
            self.assertTrue(
                any("color_richness" in reason for reason in report["suppressed_quality_reasons"]),
                report["suppressed_quality_reasons"],
            )

    def test_rejects_realistic_untextured_cube_placeholder(self):
        with TemporaryDirectory() as tmp_dir:
            glb_path = Path(tmp_dir) / "cube_placeholder.glb"
            trimesh.creation.box(extents=(1.0, 1.0, 1.0)).export(glb_path)

            report = evaluate_acceptance(
                glb_path,
                "pas de cube ou forme basique, je veux un vrai modele 3D avec texture cuir",
                expected_kind="product",
            )

        failures = " | ".join(report["hard_failures"])
        self.assertFalse(report["acceptance_ok"])
        self.assertIn("cube-like", failures)
        self.assertIn("texture required", failures)

    def test_rejects_root_only_animation_when_motion_is_requested(self):
        with TemporaryDirectory() as tmp_dir:
            glb_path = Path(tmp_dir) / "root_only_motion.glb"
            _build_textured_multipart_glb(glb_path, root_only=True)

            report = evaluate_acceptance(
                glb_path,
                "vrai modele 3D realiste avec texture metal et ventilateur qui tourne",
                expected_kind="product",
            )

        failures = " | ".join(report["hard_failures"])
        self.assertFalse(report["acceptance_ok"])
        self.assertTrue(report["motion_audit"]["root_only"])
        self.assertIn("root object", failures)

    def test_rejects_non_articulated_body_motion_for_walk_prompt(self):
        with TemporaryDirectory() as tmp_dir:
            glb_path = Path(tmp_dir) / "body_motion_not_walk.glb"
            _build_textured_multipart_glb(glb_path)

            report = evaluate_acceptance(
                glb_path,
                "personnage realiste texture tissu qui marche",
                expected_kind="character",
            )

        failures = " | ".join(report["hard_failures"])
        self.assertFalse(report["acceptance_ok"])
        self.assertFalse(report["motion_audit"]["has_articulated_locomotion"])
        self.assertIn("locomotion requested", failures)

    def test_rejects_incomplete_animation_for_macarena_prompt(self):
        with TemporaryDirectory() as tmp_dir:
            glb_path = Path(tmp_dir) / "body_motion_not_macarena.glb"
            _build_textured_multipart_glb(glb_path)

            report = evaluate_acceptance(
                glb_path,
                "personnage colore qui danse la Macarena",
                expected_kind="character",
                motion_prompt="danse la Macarena avec tete epaules bras jambes",
            )

        failures = " | ".join(report["hard_failures"])
        self.assertFalse(report["acceptance_ok"])
        self.assertFalse(report["motion_audit"]["macarena_ready"])
        self.assertIn("Macarena requested", failures)

    def test_rejects_incomplete_animation_for_floss_prompt(self):
        with TemporaryDirectory() as tmp_dir:
            glb_path = Path(tmp_dir) / "body_motion_not_floss.glb"
            _build_textured_multipart_glb(glb_path)

            report = evaluate_acceptance(
                glb_path,
                "Emmanuel Macron realiste qui fait le floss avec mains et doigts visibles",
                expected_kind="character",
                motion_prompt=(
                    "floss dance complet: bras devant derriere, poings fermes, "
                    "hanches en opposition aux bras, une seule animation fluide"
                ),
            )

        failures = " | ".join(report["hard_failures"])
        self.assertFalse(report["acceptance_ok"])
        self.assertFalse(report["motion_audit"]["floss_ready"])
        self.assertIn("Floss requested", failures)

    def test_rejects_flat_material_humanoid_for_real_character_request(self):
        with TemporaryDirectory() as tmp_dir:
            glb_path = Path(tmp_dir) / "flat_humanoid.glb"
            _build_flat_humanoid_glb(glb_path)

            report = evaluate_acceptance(
                glb_path,
                "vraie personne personnage realiste avec visage net et texture peau cheveux vetements",
                expected_kind="character",
            )

        failures = " | ".join(report["hard_failures"])
        self.assertFalse(report["acceptance_ok"])
        self.assertFalse(report["human_fidelity_audit"]["pbr_texture_signal"])
        self.assertIn("human/character fidelity requested", failures)

    def test_rejects_hand_critical_motion_without_finger_detail(self):
        with TemporaryDirectory() as tmp_dir:
            glb_path = Path(tmp_dir) / "flat_humanoid_hands.glb"
            _build_flat_humanoid_glb(glb_path)

            report = evaluate_acceptance(
                glb_path,
                "personnage qui danse la Macarena avec mains retournees",
                expected_kind="character",
                motion_prompt="Macarena complete avec paumes et doigts visibles",
            )

        failures = " | ".join(report["hard_failures"])
        self.assertFalse(report["acceptance_ok"])
        self.assertFalse(report["human_fidelity_audit"]["has_named_fingers"])
        self.assertIn("hand-critical motion requested", failures)


if __name__ == "__main__":
    unittest.main(verbosity=2)
