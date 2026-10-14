import importlib.util
import pytest
from pathlib import Path

PATH=Path(__file__).resolve().parents[1]/'application/python-services/faithful_scene_prompt.py'
spec=importlib.util.spec_from_file_location('scene_exclusions',PATH)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.fixture(autouse=True)
def no_identity_lookup(monkeypatch):
    monkeypatch.setattr(module, '_detect_identity', lambda _: None)



def test_excluded_facets_do_not_become_required_scene_objects():
    result=module.detect_facets('robot avec néons, sans moteur ni fumée')
    assert 'mechanical' not in result['families']
    assert 'fluids' not in result['families']
    assert 'luminous' in result['families']


def test_positive_clause_after_exclusion_remains_present():
    result=module.detect_facets('robot sans moteur mais avec vapeur et néons')
    assert 'mechanical' not in result['families']
    assert 'fluids' in result['families']
    assert 'luminous' in result['families']


def test_real_requested_props_are_not_replaced_by_surface_styling():
    result=module.compose_faithful_prompt('robot avec moteur et vapeur',subject_kind='character')
    assert result['mode']=='scene'
    assert 'not as separate animated geometry' not in result['prompt']
