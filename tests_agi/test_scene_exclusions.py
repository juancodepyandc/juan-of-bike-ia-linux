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


def test_studio_backdrop_is_not_treated_as_decor_facet():
    result=module.detect_facets('un chat noir assis sur fond blanc')
    assert 'decor' not in result['families']
    assert result['compound'] is False


def test_piece_mecanique_and_french_conjunction_or_do_not_trigger_false_facets():
    res_piece=module.detect_facets('une pièce mécanique simple')
    assert 'decor' not in res_piece['families']
    res_conj=module.detect_facets('un vase simple, or il doit rester sobre')
    assert 'materials' not in res_conj['families']
    res_gold=module.detect_facets('une couronne en or ciselé')
    assert 'materials' in res_gold['families']


def test_single_subject_with_material_and_motion_is_not_compound_scene():
    composed=module.compose_faithful_prompt('un guerrier en acier brossé qui court', subject_kind='character')
    assert composed['analysis']['compound'] is False
    assert 'MULTI-ELEMENT FIDELITY CONTRACT' not in composed['prompt']


def test_aurora_3d_pipeline_strips_ui_diagnostics_and_reaches_isolated_contract():
    pipe_path=Path(__file__).resolve().parents[1]/'application/python-services/aurora_3d_pipeline.py'
    pipe_spec=importlib.util.spec_from_file_location('aurora_3d_pipeline_test', pipe_path)
    pipe_mod=importlib.util.module_from_spec(pipe_spec)
    pipe_spec.loader.exec_module(pipe_mod)

    bloated = (
        "un loup gris debout\n"
        "Animation is explicitly OFF: render the requested pose/action as a STATIC result.\n\n"
        "Intent 3D detecte: Creature 3D\n"
        "Contraintes 3D prioritaires:\n"
        "- Garder la silhouette lisible\n"
        "Sous-ensembles mobiles a rendre lisibles:\n"
        "- pattes, machoire\n"
        "Risques a respecter:\n"
        "- pas de socle"
    )
    cleaned = pipe_mod._strip_internal_ui_diagnostics(bloated)
    assert cleaned == "un loup gris debout"

    enhanced = pipe_mod.enhance_flux_prompt(bloated, subject_kind="character", objet_isole=True)
    assert "Intent 3D detecte" not in enhanced
    assert "UN SEUL objet dans l'image" in enhanced


def test_scene_orchestrator_strips_diagnostics_and_debout_defaults_to_attente():
    orch_path=Path(__file__).resolve().parents[1]/'application/python-services/scene_orchestrator.py'
    orch_spec=importlib.util.spec_from_file_location('scene_orchestrator_test', orch_path)
    orch_mod=importlib.util.module_from_spec(orch_spec)
    orch_spec.loader.exec_module(orch_mod)

    assert orch_mod.ACTIONS_PAR_POSE['debout'] == 'attente'
    cleaned = orch_mod._strip_ui_diagnostics(
        "un chevalier debout\nIntent 3D detecte: Personnage\nContraintes 3D prioritaires:\n- test"
    )
    assert cleaned == "un chevalier debout"


def test_open_vocabulary_multi_entity_scene_and_single_subject_preservation():
    # Open-vocabulary multi-object requests outside fixed dictionary lists must be recognized as compound scenes
    table_scene = module.compose_faithful_prompt(
        "une table en bois avec deux chaises et une théière posée sur un plateau",
        subject_kind="object",
    )
    assert table_scene["analysis"]["compound"] is True
    assert "secondary_subjects" in table_scene["analysis"]["families"]
    assert "MULTI-ELEMENT FIDELITY CONTRACT" in table_scene["prompt"]

    warrior_scene = module.compose_faithful_prompt(
        "un guerrier tenant une épée à côté d'un coffre",
        subject_kind="character",
    )
    assert warrior_scene["analysis"]["compound"] is True

    # Single-object requests with abstract attributes or studio backdrops remain non-compound
    single_attr = module.compose_faithful_prompt(
        "une lampe design avec finition mate et silhouette épurée sur fond neutre",
        subject_kind="product",
    )
    assert single_attr["analysis"]["compound"] is False


def test_motion_parser_supports_open_custom_actions():
    mp_path = Path(__file__).resolve().parents[1] / "application/python-services/motion_parser.py"
    mp_spec = importlib.util.spec_from_file_location("motion_parser_test", mp_path)
    mp_mod = importlib.util.module_from_spec(mp_spec)
    mp_spec.loader.exec_module(mp_mod)

    # Open-ended French reflexive/progressive action outside hardcoded VERB_TO_PRESET
    drawbridge = mp_mod.parse_custom_motion_prompt("un pont-levis qui s'abaisse lentement")
    assert drawbridge is not None
    assert drawbridge["primitives"][0]["kind"] == "custom_pose"
    assert drawbridge["primitives"][0]["modifiers"]["speedMul"] < 1.0

    # Open-ended English participle action outside hardcoded VERB_TO_PRESET
    chest = mp_mod.parse_custom_motion_prompt("a treasure chest opening slowly")
    assert chest is not None
    assert chest["primitives"][0]["kind"] == "custom_pose"

    # Pure static noun phrase without action remains None
    assert mp_mod.parse_custom_motion_prompt("une chaise en bois") is None




