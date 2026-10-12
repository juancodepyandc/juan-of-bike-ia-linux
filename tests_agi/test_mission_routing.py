from agi_core.mission_routing import mission_module
from agi_core.mission_protocol import tool_response_schema


def test_explicit_3d_request_and_engineering_navigate_to_3d():
    assert mission_module({'request':'générer une loutre avec un fusil en 3D dans le style animé'})=='3d'
    assert mission_module({'request':'préparer cette figurine pour imprimer'})=='3d'
    assert mission_module({'project_kind':'engineering','request':'un assemblage complexe'})=='3d'
    assert mission_module({'module':'code','request':'un viewer 3D'})=='code'
    assert mission_module({'request':'bonjour'}) is None


def test_generation_grammar_only_names_real_discovered_scripts():
    schema=tool_response_schema(allowed=['inspect_tool','run_tool','list_tools'],available_script_names=['custom.py','custom','aurora_3d_pipeline.py'])
    branches={b['properties']['tool']['const']:b['properties']['args'] for b in schema['oneOf']}
    assert set(branches['run_tool']['properties']['name']['enum'])=={'custom.py','custom','aurora_3d_pipeline.py'}
    assert 'inspect_tool' in branches['inspect_tool']['properties']['name']['enum']
    assert 'generate_river_otter_with_rifle' not in branches['inspect_tool']['properties']['name']['enum']
    assert 'run_tool' not in branches['run_tool']['properties']['name']['enum']
