import ast,os,sys,types
from pathlib import Path

def test_reconstruction_does_not_require_animation_before_motion_stage(monkeypatch):
    source=Path(__file__).resolve().parents[1]/'application/python-services/aurora_3d_pipeline.py'
    fn=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run_final_acceptance')
    scope={'Path':Path,'os':os};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),scope)
    observed=[]
    def evaluate(*args,**kwargs):
        observed.append(kwargs['require_motion'])
        return {'acceptance_ok':False,'hard_failures':['geometry mismatch']}
    monkeypatch.setitem(sys.modules,'mesh_acceptance_gate',types.SimpleNamespace(evaluate_acceptance=evaluate))
    monkeypatch.setenv('AURORA_MOTION_LOCALE','0')
    assert scope['run_final_acceptance']('model.glb','move requested','generic')['hard_failures']==['geometry mismatch']
    monkeypatch.delenv('AURORA_MOTION_LOCALE')
    scope['run_final_acceptance']('model.glb','move requested','generic')
    assert observed==[False,None]
