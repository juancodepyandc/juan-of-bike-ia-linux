import asyncio,json
from pathlib import Path
import pytest,trimesh
from agi_core.mission_agent import AutonomousMissionAgent
from agi_core.generation_3d import execute_generation
from agi_core.mission_protocol import tool_response_schema

def agent(tmp_path):
    a=AutonomousMissionAgent('mis_fixture','générer un objet 3D stylisé',str(tmp_path),'fixture')
    a.state['plan']=['Generate actual geometry'];a.state['criteria']=['Actual mesh saved']
    async def save():pass
    a._save=save
    return a

def test_typed_generation_has_exact_prompt_and_reuses_actual_file(tmp_path):
    a=agent(tmp_path);script=tmp_path/'engine.py';script.write_text('# controlled engine boundary')
    a.tools.script=lambda name:script;calls=[]
    async def run(argv,**kwargs):
        calls.append(argv);target=Path(argv[argv.index('--output-dir')+1]);path=target/'actual.glb'
        trimesh.creation.icosphere().export(path)
        record={'run_id':argv[argv.index('--run-id')+1],'schema':'aurora.pipeline.v1','final_mesh':str(path),'acceptance':{'scope':'fixture'}}
        (target/'audit.json').write_text(json.dumps(record))
        return {'output':json.dumps(record)}
    a._run_process=run
    async def scenario():
        first=await execute_generation(a,{'prompt':a.request_text})
        second=await execute_generation(a,{'prompt':a.request_text})
        assert Path(first['path']).is_file() and second['reused']
        assert len(calls)==1 and calls[0][calls[0].index('--prompt')+1]==a.request_text
        assert not first['physical_fit_validated']
    asyncio.run(scenario())
    schema=tool_response_schema(allowed=['generate_3d'],generation_prompt=a.request_text)
    assert schema['oneOf'][0]['properties']['args']['properties']['prompt']['const']==a.request_text

def test_unknown_generation_never_replays_even_after_engine_changes(tmp_path):
    a=agent(tmp_path);script=tmp_path/'engine.py';script.write_text('changed engine')
    a.tools.script=lambda name:script
    a.state['generation_3d_attempts']={'old_signature':{'status':'outcome_unknown'}}
    with pytest.raises(RuntimeError,match='unknown outcome'):
        asyncio.run(execute_generation(a,{'prompt':a.request_text}))

def test_visual_generation_dispatch_is_not_a_software_or_cad_override(tmp_path):
    from agi_core.mission_routing import direct_3d_generation
    a=agent(tmp_path);assert a._available_tools()==['generate_3d']
    assert direct_3d_generation('générer une loutre avec un fusil en 3D dans le style animé')
    assert not direct_3d_generation('Créer un viewer 3D en React')
    assert not direct_3d_generation('Créer une pièce 3D dans FreeCAD')


def test_entity_mesh_cannot_be_delivered_as_complete_scene(tmp_path):
    a=agent(tmp_path); script=tmp_path/'engine.py';script.write_text('# boundary')
    a.tools.script=lambda name:script
    async def run(argv,**kwargs):
        target=Path(argv[argv.index('--output-dir')+1]);path=target/'entity.glb'
        trimesh.creation.icosphere().export(path)
        return {'output':json.dumps({'run_id':'other_entity','final_mesh':str(path)})}
    a._run_process=run
    with pytest.raises(RuntimeError,match='matches this scene'):
        asyncio.run(execute_generation(a,{'prompt':a.request_text}))
    assert next(iter(a.state['generation_3d_attempts'].values()))['status']=='failed'
