"""Articulated motion: a part moves relative to the rest of the object, on a real joint.

The request « coffre avec une animation d'ouverture » used to rock the whole mesh ±15° about a
world axis. These tests build FUSED single-surface objects with UVs and a texture, like an
image-to-3D reconstruction, and check the contract with numbers: the cut lands on the seam, the
parts are closed, the hinge is on the right edge, the opening is one-way and collision-limited,
the base stays still, and the verification gate refuses broken files.
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
trimesh = pytest.importorskip("trimesh")
manifold3d = pytest.importorskip("manifold3d")
pytest.importorskip("shapely")      # cut outlines and their triangulation
pytest.importorskip("scipy")        # filled occupancy grids for collisions
from PIL import Image  # noqa: E402

SERVICES = Path(__file__).resolve().parents[1] / "application" / "python-services"
if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))
import articulated_motion as am  # noqa: E402
import glb_io  # noqa: E402


def fused(boxes, colour_of_height, *, subdivisions=2):
    """Union of boxes as ONE surface, UV by height, texture whose colour depends on height."""
    solid = None
    for extents, centre in boxes:
        box = trimesh.creation.box(extents=extents)
        box.apply_translation(centre)
        piece = manifold3d.Manifold(manifold3d.Mesh(np.asarray(box.vertices, np.float32), np.asarray(box.faces, np.uint32)))
        solid = piece if solid is None else solid + piece
    out = solid.to_mesh()
    mesh = trimesh.Trimesh(np.asarray(out.vert_properties)[:, :3], np.asarray(out.tri_verts), process=True)
    for _ in range(subdivisions):
        mesh = mesh.subdivide()
    top = float(mesh.bounds[1, 1])
    uv = np.column_stack([(mesh.vertices[:, 0] - mesh.bounds[0, 0]) / mesh.extents[0], mesh.vertices[:, 1] / top])
    texture = np.zeros((256, 64, 3), np.uint8)
    for row in range(256):
        texture[row] = colour_of_height((1.0 - row / 255.0) * top)
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, image=Image.fromarray(texture))
    return mesh


def chest():
    """Body 1.0 x 0.60 x 0.60, lid 1.04 x 0.25 x 0.64 overhanging it: seam at y = 0.60."""
    return fused([((1.0, 0.60, 0.60), (0, 0.30, 0)), ((1.04, 0.25, 0.64), (0, 0.725, 0))],
                 lambda y: (150, 95, 45) if y < 0.60 else (110, 45, 30))


def plan(**overrides):
    base = {"mouvement_de_piece": True, "piece_mobile": "couvercle", "piece_fixe": "corps",
            "position_piece_mobile": "top", "piece_couvre_toute_la_face": True, "articulation": "charniere",
            "cote_attache": "back", "fraction_estimee": 0.35, "amplitude_deg": 110, "course_relative": 0.6,
            "base_contenant": True, "duree_s": 2.0, "maintien_s": 1.0, "retour": False, "boucle": False}
    base.update(overrides)
    return am.valider_plan(base, "coffre avec une animation d'ouverture")


class Plan(unittest.TestCase):
    def test_a_valid_plan_is_normalised_and_bounded(self):
        p = plan(amplitude_deg=400, fraction_estimee=-1, duree_s="lent")
        self.assertTrue(p["ok"])
        self.assertEqual(p["amplitude_deg"], 180.0)
        self.assertEqual(p["fraction_estimee"], 0.05)
        self.assertEqual(p["duree_s"], 2.0)

    def test_a_hinge_on_the_moving_side_itself_is_unknown(self):
        self.assertEqual(plan(cote_attache="top")["cote_attache"], "inconnu")
        self.assertEqual(plan(cote_attache="bottom")["cote_attache"], "inconnu")

    def test_answers_outside_the_contract_are_refused(self):
        for raw in (None, [], {"mouvement_de_piece": "oui"}, {"mouvement_de_piece": True, "position_piece_mobile": "dessus",
                                                              "articulation": "charniere"},
                    {"mouvement_de_piece": True, "position_piece_mobile": "top", "articulation": "teleport"}):
            with self.subTest(raw=str(raw)[:40]):
                self.assertFalse(am.valider_plan(raw, "x")["ok"])

    def test_an_unreachable_model_is_reported(self):
        def offline(_request):
            raise ConnectionError("refused")
        p = am.planifier("ouvre le coffre", interroger=offline)
        self.assertFalse(p["ok"])
        self.assertIn("injoignable", p["raison"])


class Chest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.source = root / "coffre.glb"
        cls.mesh = chest()
        cls.mesh.export(cls.source)
        cls.output = root / "coffre_anime.glb"
        cls.result = am.animer(cls.source, "coffre avec une animation d'ouverture", cls.output, plan=plan())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_chest_opens_and_the_written_file_passes_the_gate(self):
        self.assertTrue(self.result["ok"], self.result.get("raison"))
        checks = self.result["verification"]["controles"]
        self.assertEqual(checks["noeuds_animes"], ["partie_mobile"])
        self.assertGreater(checks["deplacement_relatif"], am.MIN_DEPLACEMENT_RELATIF)
        self.assertLess(checks["derive_axe_relative"], am.TOLERANCE_AXE_RELATIVE)
        self.assertLessEqual(checks["penetration_max"], am.MAX_PENETRATION)
        self.assertTrue(checks["base_etanche"] and checks["mobile_etanche"])
        self.assertGreaterEqual(checks["materiaux_textures"], 1)

    def test_the_cut_lands_on_the_real_seam(self):
        seam = self.result["couture"]
        height = seam["fraction"] * seam["etendue"]
        self.assertEqual(seam["accroche"], "arete_vive")
        self.assertAlmostEqual(height, 0.60, delta=0.004)

    def test_the_hinge_is_the_back_edge_of_the_cut(self):
        joint = self.result["liaison"]
        self.assertEqual(joint["type"], "charniere")
        pivot, axis = np.asarray(joint["pivot"]), np.asarray(joint["axe"])
        self.assertAlmostEqual(abs(axis[0]), 1.0, places=3)           # along the chest's width
        self.assertAlmostEqual(pivot[2], -0.30, delta=0.01)             # back face of the body
        self.assertAlmostEqual(pivot[1], 0.60, delta=0.005)             # at the seam
        self.assertAlmostEqual(joint["amplitude_retenue_deg"], 110.0, places=1)

    def test_the_opening_is_one_way_and_the_lid_ends_up_raised(self):
        doc, blob = glb_io.load(self.output)
        sampler = doc["animations"][0]["samplers"][0]
        times = glb_io.accessor(doc, blob, sampler["input"]).reshape(-1)
        quats = glb_io.accessor(doc, blob, sampler["output"])
        angles = np.degrees(2 * np.arctan2(np.linalg.norm(quats[:, :3], axis=1), quats[:, 3]))
        self.assertTrue(np.all(np.diff(angles) >= -1e-4))
        self.assertAlmostEqual(float(angles[-1]), 110.0, delta=0.5)
        self.assertAlmostEqual(float(times[-1]), 3.0, places=3)        # 2 s opening + 1 s hold
        lid = am.charger(self.source)[1]
        top_before = float(lid.bounds[1, 1])
        self.assertGreater(top_before, 0.8)

    def test_a_wrong_estimate_from_the_plan_does_not_move_the_cut(self):
        with tempfile.TemporaryDirectory() as root:
            result = am.animer(self.source, "ouvre le coffre", Path(root) / "out.glb", plan=plan(fraction_estimee=0.45))
        self.assertTrue(result["ok"], result.get("raison"))
        height = result["couture"]["fraction"] * result["couture"]["etendue"]
        self.assertAlmostEqual(height, 0.60, delta=0.004)

    def test_an_unknown_hinge_side_is_decided_by_trying_every_edge(self):
        with tempfile.TemporaryDirectory() as root:
            result = am.animer(self.source, "ouvre le coffre", Path(root) / "out.glb", plan=plan(cote_attache="inconnu"))
        self.assertTrue(result["ok"], result.get("raison"))
        tried = {e["cote"] for e in result["essais_charniere"]}
        self.assertEqual(tried, {"front", "back", "left", "right"})
        self.assertEqual(result["liaison"]["cote"], "back")             # symmetric box: tie goes to the back

    def test_the_gate_refuses_a_file_where_the_base_moves(self):
        doc, blob = glb_io.load(self.output)
        names = [n.get("name") for n in doc["nodes"]]
        doc["animations"][0]["channels"][0]["target"]["node"] = names.index("base")
        with tempfile.TemporaryDirectory() as root:
            broken = Path(root) / "base_moves.glb"
            glb_io.save(broken, doc, blob)
            verdict = am.verifier(broken)
        self.assertFalse(verdict["ok"])
        self.assertTrue(any("seule la pièce mobile" in reason for reason in verdict["raisons"]))

    def test_the_gate_refuses_a_rotation_that_does_not_follow_the_announced_hinge(self):
        doc, blob = glb_io.load(self.output)
        names = [n.get("name") for n in doc["nodes"]]
        joint = doc["nodes"][names.index("partie_mobile")]["extras"]["aurora_liaison"]
        joint["axe"] = [0.0, 0.0, 1.0]                                   # claims a hinge it does not rotate about
        with tempfile.TemporaryDirectory() as root:
            broken = Path(root) / "wrong_axis.glb"
            glb_io.save(broken, doc, blob)
            verdict = am.verifier(broken)
        self.assertFalse(verdict["ok"])
        self.assertTrue(any("charnière" in reason for reason in verdict["raisons"]))


class OtherObjects(unittest.TestCase):
    def test_a_full_face_door_swings_about_its_side_edge(self):
        cabinet = fused([((0.8, 1.2, 0.5), (0, 0.6, 0)), ((0.84, 1.24, 0.06), (0, 0.6, 0.28))],
                        lambda y: (180, 170, 150))
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "armoire.glb"
            cabinet.export(source)
            result = am.animer(source, "ouvre la porte de l'armoire", Path(root) / "out.glb",
                               plan=plan(position_piece_mobile="front", cote_attache="left", fraction_estimee=0.12,
                                         amplitude_deg=95, base_contenant=True))
        self.assertTrue(result["ok"], result.get("raison"))
        axis, pivot = np.asarray(result["liaison"]["axe"]), np.asarray(result["liaison"]["pivot"])
        self.assertAlmostEqual(abs(axis[1]), 1.0, places=3)             # vertical hinge
        self.assertAlmostEqual(pivot[0], -0.40, delta=0.02)             # on the left edge seen from the front

    def test_a_drawer_slides_out_along_the_face_normal(self):
        box = fused([((0.6, 0.3, 0.5), (0, 0.15, 0)), ((0.62, 0.32, 0.05), (0, 0.15, 0.27))],
                    lambda y: (90, 120, 160))
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "boite.glb"
            box.export(source)
            output = Path(root) / "out.glb"
            result = am.animer(source, "ouvre le tiroir", output,
                               plan=plan(position_piece_mobile="front", articulation="glissiere", cote_attache=None,
                                         fraction_estimee=0.12, course_relative=0.5, base_contenant=False))
            self.assertTrue(result["ok"], result.get("raison"))
            doc, blob = glb_io.load(output)
            sampler = doc["animations"][0]["samplers"][0]
            self.assertEqual(doc["animations"][0]["channels"][0]["target"]["path"], "translation")
            values = glb_io.accessor(doc, blob, sampler["output"])
        travel = values[-1] - values[0]
        self.assertGreater(travel[2], 0.2)                               # outward, toward the front
        self.assertLess(abs(travel[0]) + abs(travel[1]), 1e-6)

    def test_a_partial_part_is_refused_instead_of_moving_the_whole_object(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "coffre.glb"
            chest().export(source)
            result = am.animer(source, "appuie sur le bouton", Path(root) / "out.glb",
                               plan=plan(piece_couvre_toute_la_face=False))
            self.assertFalse(result["ok"])
            self.assertTrue(result.get("hors_portee"))
            self.assertFalse((Path(root) / "out.glb").exists())

    def test_the_free_range_stops_where_the_part_would_enter_the_base(self):
        ceiling = trimesh.creation.box(extents=(2.0, 0.1, 1.0))
        ceiling.apply_translation((0.5, 0.55, 0.0))                      # its underside is the plane y = 0.5
        occupation = am.Occupation(ceiling, 0.01)
        plank = np.column_stack([np.linspace(0.0, 1.0, 200), np.zeros(200), np.zeros(200)])
        # the plank rises about the z axis at the origin; its tip reaches the ceiling at 30 degrees
        free, _ = am.amplitude_libre(plank, occupation, pivot=[0, 0, 0], axe=[0, 0, 1], signe=1, amplitude_deg=90)
        expected = math.degrees(math.asin(0.5 / 1.0))
        self.assertLess(free, 90.0)
        self.assertAlmostEqual(free, expected, delta=6.0)
        # rotating the other way, nothing stands in the way
        free_down, _ = am.amplitude_libre(plank, occupation, pivot=[0, 0, 0], axe=[0, 0, 1], signe=-1, amplitude_deg=90)
        self.assertEqual(free_down, 90.0)


class BakerRouting(unittest.TestCase):
    def test_a_whole_object_motion_keeps_the_existing_bakers(self):
        import motion_intent_baker as baker
        original = am.planifier
        am.planifier = lambda request, **kwargs: am.valider_plan({"mouvement_de_piece": False}, request)
        try:
            self.assertIsNone(baker._bake_part_motion("le ventilateur tourne", "in.glb", "out.glb", "fan_pwm"))
        finally:
            am.planifier = original

    def test_a_part_motion_without_a_plan_fails_instead_of_rocking_the_mesh(self):
        import motion_intent_baker as baker
        original = am.planifier
        am.planifier = lambda request, **kwargs: {"ok": False, "raison": "modèle injoignable"}
        try:
            result = baker._bake_part_motion("ouvre le coffre", "in.glb", "out.glb", "mechanical_simple")
        finally:
            am.planifier = original
        self.assertFalse(result["ok"])
        self.assertEqual(result["engine"], "articulated_motion")


if __name__ == "__main__":
    unittest.main()
