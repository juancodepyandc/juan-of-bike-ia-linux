"""Desktop control for Aurora's agent: XTest actions, vision grounding and the safety gate.

The Cowork desktop screenshot needed scrot, gnome-screenshot or ImageMagick (none installed:
it always failed) and nothing could move the mouse or type. These tests drive the action layer
against a recording fake X server, so they run anywhere, including the CI without a display.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
import desktop_control as dc  # noqa: E402

KEYSYMS = {"a": 0x61, "A": 0x41, "s": 0x73, "Control_L": 0xFFE3, "Shift_L": 0xFFE1, "Return": 0xFF0D,
           "space": 0x20, "U00E9": 0x10000E9, "U2603": 0x1002603}
KEYCODES = {0x61: 38, 0x41: 38, 0x73: 39, 0xFFE3: 37, 0xFFE1: 50, 0xFF0D: 36, 0x20: 65}


class FakeX11:
    """Records every XTest call; a keyboard with letters, Return, space; no é, no snowman."""

    def __init__(self):
        self.calls = []
        self.pointer = (0, 0)
        self.mapping = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def position(self):
        return self.pointer

    def deplacer(self, x, y):
        self.pointer = (x, y)
        self.calls.append(("move", x, y))

    def bouton(self, numero, appuye):
        self.calls.append(("button", numero, appuye))

    def keysym(self, nom):
        return KEYSYMS.get(nom, 0)

    def keycode(self, keysym):
        if keysym in self.mapping.values():
            return next(code for code, ks in self.mapping.items() if ks == keysym)
        return KEYCODES.get(keysym, 0)

    def touche(self, code, appuye):
        self.calls.append(("key", code, appuye))

    def niveau(self, code, keysym):
        if self.mapping.get(code) == keysym:
            return 0
        return 1 if keysym == 0x41 else 0

    def code_libre(self):
        return 200

    def associer(self, code, keysym):
        self.calls.append(("map", code, keysym))
        if keysym:
            self.mapping[code] = keysym
        else:
            self.mapping.pop(code, None)


ON = {dc.ENV_ACTIVATION: "1"}


class Actions(unittest.TestCase):
    def run_action(self, action):
        fake = FakeX11()
        result = dc.agir(action, x11_factory=lambda: fake, avec_captures=False, environ=ON)
        return result, fake

    def test_nothing_acts_without_the_explicit_opt_in(self):
        fake = FakeX11()
        result = dc.agir({"type": "cliquer", "x": 10, "y": 10}, x11_factory=lambda: fake, avec_captures=False, environ={})
        self.assertFalse(result["ok"])
        self.assertIn(dc.ENV_ACTIVATION, result["raison"])
        self.assertEqual(fake.calls, [])

    def test_a_click_moves_then_presses_and_releases_the_button(self):
        result, fake = self.run_action({"type": "cliquer", "x": 300, "y": 120, "bouton": "droit"})
        self.assertTrue(result["ok"])
        self.assertEqual(fake.calls, [("move", 300, 120), ("button", 3, True), ("button", 3, False)])
        self.assertEqual(result["pointeur"], [300, 120])

    def test_typing_uses_shift_for_capitals_and_maps_missing_characters_temporarily(self):
        result, fake = self.run_action({"type": "taper", "texte": "aAé"})
        self.assertTrue(result["ok"])
        self.assertEqual(fake.calls[:2], [("key", 38, True), ("key", 38, False)])            # a
        self.assertEqual(fake.calls[2:6], [("key", 50, True), ("key", 38, True), ("key", 38, False), ("key", 50, False)])  # A
        self.assertIn(("map", 200, 0x10000E9), fake.calls)                                    # é on a free keycode
        self.assertIn(("key", 200, True), fake.calls)
        self.assertEqual(fake.calls[-1], ("map", 200, 0))                                     # mapping restored

    def test_a_key_combination_is_pressed_in_order_and_released_in_reverse(self):
        result, fake = self.run_action({"type": "touche", "touches": "ctrl+s"})
        self.assertTrue(result["ok"])
        self.assertEqual(fake.calls, [("key", 37, True), ("key", 39, True), ("key", 39, False), ("key", 37, False)])

    def test_system_combinations_and_malformed_actions_are_refused_before_any_input(self):
        for action in ({"type": "touche", "touches": "ctrl+alt+delete"}, {"type": "cliquer", "x": -1, "y": 3},
                       {"type": "cliquer", "x": True, "y": 3}, {"type": "taper", "texte": ""},
                       {"type": "defiler", "sens": "bas", "quantite": 99}, {"type": "teleporter"}, "cliquer"):
            with self.subTest(action=str(action)[:40]):
                result, fake = self.run_action(action)
                self.assertFalse(result["ok"])
                self.assertEqual(fake.calls, [])

    def test_scrolling_and_dragging(self):
        result, fake = self.run_action({"type": "defiler", "sens": "haut", "quantite": 2, "x": 5, "y": 6})
        self.assertTrue(result["ok"])
        self.assertEqual([c for c in fake.calls if c[0] == "button"],
                         [("button", 4, True), ("button", 4, False)] * 2)
        result, fake = self.run_action({"type": "glisser", "x": 0, "y": 0, "x2": 120, "y2": 60})
        self.assertTrue(result["ok"])
        self.assertEqual(fake.calls[1], ("button", 1, True))
        self.assertEqual(fake.calls[-2], ("move", 120, 60))
        self.assertEqual(fake.calls[-1], ("button", 1, False))


class Grounding(unittest.TestCase):
    def test_normalised_vision_coordinates_become_screen_pixels(self):
        self.assertEqual(dc.convertir_point({"x": 500, "y": 500}, 1920, 1080), (960, 540))
        self.assertEqual(dc.convertir_point({"x": 0, "y": 1000}, 1920, 1080), (0, 1079))
        self.assertIsNone(dc.convertir_point({"x": 1200, "y": 5}, 1920, 1080))
        self.assertIsNone(dc.convertir_point({"x": "gauche"}, 1920, 1080))

    def test_locate_reads_the_vision_answer_and_reports_absence_honestly(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            image = Path(root) / "ecran.png"
            image.write_bytes(b"\x89PNG fake")
            capture = {"chemin": str(image), "largeur": 1920, "hauteur": 1080}
            found = dc.localiser("le bouton Enregistrer", capture=capture,
                                 demander=lambda png, consigne, modele: '{"trouve": true, "x": 250, "y": 100, "confiance": 0.9}')
            self.assertEqual((found["ok"], found["x"], found["y"]), (True, 480, 108))
            missing = dc.localiser("un bouton absent", capture=capture,
                                   demander=lambda png, consigne, modele: '{"trouve": false}')
            self.assertFalse(missing["ok"])

            def offline(png, consigne, modele):
                raise ConnectionError("ollama down")
            self.assertIn("injoignable", dc.localiser("x", capture=capture, demander=offline)["raison"])


if __name__ == "__main__":
    unittest.main()
