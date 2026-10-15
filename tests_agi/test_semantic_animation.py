"""Real glTF skin and channels, without downloading weights or calling a model."""
from pathlib import Path
import copy
import hashlib
import numpy as np
import pytest

@pytest.fixture
def motion(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'application/python-services'))
    import semantic_animation
    return semantic_animation


def skin(motion):
    doc={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0,2]}],
         'nodes':[{'name':'root','children':[1]}, {'name':'tip','translation':[0,1,0]}, {'mesh':0,'skin':0}],
         'skins':[{'joints':[0,1],'inverseBindMatrices':3}],
         'meshes':[{'primitives':[{'attributes':{'POSITION':0,'JOINTS_0':1,'WEIGHTS_0':2},'material':0}]}],
         'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[.1,.3,.7,1]}}], 'bufferViews':[],'accessors':[]}
    binary=bytearray()
    matrices=np.tile(np.eye(4),(2,1,1));matrices[1,1,3]=-1
    for array,kind,component in [(np.array([[0,0,0],[.1,1,0],[0,2,0]],'<f4'),'VEC3',5126),
                                (np.array([[0,0,0,0],[1,0,0,0],[1,0,0,0]],'<u2'),'VEC4',5123),
                                (np.array([[1,0,0,0]]*3,'<f4'),'VEC4',5126),
                                (matrices.transpose(0,2,1).astype('<f4'),'MAT4',5126)]:
        binary.extend(b'\0'*((-len(binary))%4));index=len(doc['bufferViews'])
        doc['bufferViews'].append({'buffer':0,'byteOffset':len(binary),'byteLength':array.nbytes})
        doc['accessors'].append({'bufferView':index,'componentType':component,'count':len(array),'type':kind})
        binary.extend(array.tobytes())
    doc['buffers']=[{'byteLength':len(binary)}]
    return doc,binary


def plan():
    return {'schema':'aurora.joint-plan.v1','duration_seconds':2,'loop':True,'requirements':['held root and independent tip'],
            'tracks':[{'node':0,'path':'translation','samples':[[0,[0,-.2,0]],[2,[0,-.2,0]]]},
                      {'node':1,'path':'rotation','samples':[[0,[0,0,0]],[1,[0,0,.5]],[2,[0,0,0]]]}]}


def test_compiles_simultaneous_held_pose_and_real_skin_motion(motion,tmp_path):
    doc,binary=skin(motion);before=copy.deepcopy(doc)
    out,blob,proof=motion.compile_plan(doc,binary,plan())
    assert doc==before and bytes(blob[:len(binary)])==bytes(binary)
    assert proof['pose_displacement']==pytest.approx(.2)
    assert proof['temporal_displacement']>.4 and not proof['physical_validation']
    for key in ('meshes','materials','skins'):assert out[key]==doc[key]
    assert len(out['animations'][0]['channels'])==2
    destination=tmp_path/'compiled.glb';motion.glb_io.save(destination,out,blob)
    loaded,data=motion.glb_io.load(destination)
    assert loaded['animations']==out['animations']
    channel=loaded['animations'][0]['samplers'][1]
    quats=motion.glb_io.accessor(loaded,data,channel['output'])
    assert np.allclose(np.linalg.norm(quats,axis=1),1)
    assert not np.allclose(quats[0],quats[1])


def test_static_pose_and_rejected_fake_animation(motion):
    doc,binary=skin(motion);p=plan();p['tracks']=p['tracks'][:1]
    out,_,proof=motion.compile_plan(doc,binary,p,'static_pose')
    assert out['nodes'][0]['translation']==[0,-.2,0] and 'animations' not in out
    with pytest.raises(ValueError,match='does not animate'):motion.compile_plan(doc,binary,p)
    with pytest.raises(ValueError,match='hold its posture'):motion.compile_plan(doc,binary,plan(),'static_pose')


@pytest.mark.parametrize('fault',['node','nan','time','duplicate'])
def test_invalid_plan_never_changes_original(motion,fault):
    doc,binary=skin(motion);before=copy.deepcopy(doc);p=plan()
    if fault=='node':p['tracks'][1]['node']=999
    elif fault=='nan':p['tracks'][1]['samples'][1][1][0]=float('nan')
    elif fault=='time':p['tracks'][1]['samples'][1][0]=0
    else:p['tracks'].append(copy.deepcopy(p['tracks'][0]))
    with pytest.raises(ValueError):motion.compile_plan(doc,binary,p)
    assert doc==before


def test_derived_delivery_keeps_source_and_receipt(motion,tmp_path,monkeypatch):
    doc,binary=skin(motion);source=tmp_path/'source.glb';motion.glb_io.save(source,doc,binary)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    # Rendering is outside the joint compiler contract; no mock visual quality claim.
    import livraison_organisee
    monkeypatch.setenv('AURORA_LIVRAISON_PREVIEWS','0')
    result=motion.deliver_existing(source,tmp_path/'juan_bike_1','juan_bike_1','compose joints','fixture','animation',planner=lambda *a:plan())
    assert result['ok'] and Path(result['final_mesh']).parent.name=='mouvement'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    assert (tmp_path/'juan_bike_1/journal/joint-plan.json').is_file()
    assert len(list((tmp_path/'juan_bike_1/.aurora-receipts').glob('*.json')))==1


def test_semantic_rejection_revises_before_publishing(motion,tmp_path):
    doc,binary=skin(motion);source=tmp_path/'source.glb';motion.glb_io.save(source,doc,binary)
    attempts=[];reviews=[]
    def planner(prompt,*args):attempts.append(prompt);return plan()
    def reviewer(*args):
        reviews.append(args)
        if len(reviews)==1:raise ValueError('Requested part was not covered')
        return {'conforms':True,'defects':[],'missing_requirements':[]}
    result=motion.animate_existing(source,tmp_path/'derived.glb','full request','fixture',planner=planner,reviewer=reviewer)
    assert len(attempts)==2 and 'Requested part was not covered' in attempts[1]
    assert result['semantic_review']['conforms']
    assert result['measurements']['checked_times']==[0.,1.,2.]


def test_orphan_skin_is_not_accepted_as_animated_geometry(motion):
    doc,binary=skin(motion);del doc['nodes'][2]['skin']
    with pytest.raises(ValueError,match='actually bound'):motion.compile_plan(doc,binary,plan())


def test_provider_error_is_reported_without_fake_motion_retry(motion,monkeypatch):
    import io,json
    payload={'response':json.dumps({'error':{'type':'llm_call_failed','message':'Operation not allowed'}})}
    monkeypatch.setattr(motion.urllib.request,'urlopen',lambda *a,**kw:io.StringIO(json.dumps(payload)))
    with pytest.raises(RuntimeError,match='Operation not allowed'):motion.model_json('fixture','system',{})


def test_rigid_object_without_skin_has_measured_animation(motion,tmp_path):
    doc,binary=skin(motion)
    doc.pop('skins');doc['nodes']=[{'name':'rigid-object','mesh':0}];doc['scenes']=[{'nodes':[0]}]
    primitive=doc['meshes'][0]['primitives'][0]
    primitive['attributes'].pop('JOINTS_0');primitive['attributes'].pop('WEIGHTS_0')
    p=plan();p['tracks']=[{'node':0,'path':'translation','samples':[[0,[0,0,0]],[2,[.3,0,0]]]}]
    source=tmp_path/'rigid.glb';motion.glb_io.save(source,doc,binary)
    result=motion.animate_existing(source,tmp_path/'rigid-motion.glb','translate existing object','fixture',subject='none',planner=lambda *a:p)
    assert result['measurements']['temporal_displacement']==pytest.approx(.3)
    out,blob=motion.glb_io.load(result['path'])
    assert out['meshes']==doc['meshes'] and out['materials']==doc['materials']
    assert bytes(blob[:len(binary)])==bytes(binary)


def test_auto_anatomy_reads_original_description_not_posture(motion,tmp_path,monkeypatch):
    doc,binary=skin(motion);doc.pop('skins');doc['nodes']=[{'name':'object','mesh':0}];doc['scenes']=[{'nodes':[0]}]
    source=tmp_path/'object.glb';motion.glb_io.save(source,doc,binary);calls=[]
    def classify(model,system,data):
        calls.append(data)
        return {'rig_subject':'rigid'}
    monkeypatch.setattr(motion,'model_json',classify)
    p=plan();p['tracks']=[{'node':0,'path':'translation','samples':[[0,[0,0,0]],[2,[.3,0,0]]]}]
    motion.animate_existing(source,tmp_path/'object-motion.glb','new requested movement','fixture',subject='auto',planner=lambda *a:p,source_description='mechanical test object')
    assert calls==[{'source_description':'mechanical test object','mesh_nodes':1}]


@pytest.mark.parametrize('angles',[[0,0,1.57079632679],[3.14159265359,0,0],[.2,-.4,.3]])
def test_imported_matrix_transform_remains_equivalent(motion,angles):
    node={'translation':[1,2,3],'scale':[2,1,-3],'rotation':motion.delta_quat(angles).tolist()}
    matrix=motion.transform(node)
    original={'nodes':[{'matrix':matrix.T.ravel().tolist()}]}
    converted=motion.canonical_trs(original)
    assert 'matrix' in original['nodes'][0] and 'matrix' not in converted['nodes'][0]
    assert np.allclose(motion.transform(converted['nodes'][0]),matrix,atol=1e-7)
