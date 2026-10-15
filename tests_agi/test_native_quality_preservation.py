from pathlib import Path

def test_native_gate_judges_without_rewriting(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'application/python-services'))
    import perfection_gate as gate
    source=tmp_path/'source.glb';source.write_bytes(b'original byte content')
    calls=[]
    def forbidden(*a,**kw):raise AssertionError('Native gate must not rewrite geometry or atlas')
    monkeypatch.setattr(gate,'audit_trous',lambda p:{'bords_ouverts':999})
    monkeypatch.setattr(gate,'reparer_trous_sans_perte',forbidden)
    monkeypatch.setattr(gate,'orienter_face_viewer',forbidden)
    monkeypatch.setattr(gate,'_reparation_texture_sure',forbidden)
    monkeypatch.setattr(gate,'preuves',lambda *a:{'faces':1})
    monkeypatch.setattr(gate,'juger',lambda *a:calls.append(a) or {'parfait':False,'defauts':['pose non conforme']})
    result=gate.porte(str(source),'reference.png',preserve_native=True)
    assert not result['parfait'] and calls
    assert source.read_bytes()==b'original byte content'
