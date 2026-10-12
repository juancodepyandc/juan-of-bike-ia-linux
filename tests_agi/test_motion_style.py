import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]/'application/python-services'
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('motion_style_gate',ROOT/'mesh_acceptance_gate.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

def test_animation_style_does_not_require_real_motion_channels():
    for text in ['une loutre en 3D, style animé','une figurine, style dessin animé','a character in animated style','an object in animation style','un personnage en dessin animé','an anime character in 3D']:
        assert not gate.motion_requested(text)
        assert not gate.prompt_expectations(text)['wants_motion']

def test_visual_style_keeps_actual_movement_requests():
    assert gate.motion_requested('une loutre style animé qui marche')
    assert gate.motion_requested('a character in animated style, walking')
    assert gate.motion_requested('un personnage',motion_prompt='lever les bras de vingt degrés')
    assert gate.motion_requested('anime cette figurine')
