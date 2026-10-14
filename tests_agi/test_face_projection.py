"""Run the actual numerical decoder embedded in the Blender projection script."""
import ast
from pathlib import Path
import numpy as np


def decoder():
    source=Path(__file__).resolve().parents[1]/'application/python-services/face_refine.py'
    module=ast.parse(source.read_text())
    script=next(node.value.value for node in module.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_BPY_PROJECT' for t in node.targets))
    function=next(node for node in ast.parse(script).body if isinstance(node,ast.FunctionDef) and node.name=='decode_weighted_delta')
    scope={'np':np}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),scope)
    return scope['decode_weighted_delta']


def test_neutral_detail_stays_neutral_at_low_coverage_uv_edges():
    weights=np.array([0,1e-12,1e-8,1e-7,1e-6,1],dtype=np.float32).reshape(1,6,1)
    colors=np.repeat(weights*.5,3,axis=2)
    result=decoder()(colors,weights)
    np.testing.assert_allclose(result,0,atol=1e-7)
    assert np.isfinite(result).all()


def test_actual_signed_detail_is_preserved_independently_of_coverage():
    weights=np.array([1e-10,.01,1],dtype=np.float32).reshape(1,3,1)
    encoded=np.array([.25,.5,.75],dtype=np.float32).reshape(1,1,3)
    result=decoder()(weights*encoded,weights)
    np.testing.assert_allclose(result,np.broadcast_to(np.array([-.5,0,.5]),result.shape),atol=1e-6)
