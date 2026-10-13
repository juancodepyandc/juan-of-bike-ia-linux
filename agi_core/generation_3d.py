"""Typed local 3D dispatch with durable receipts and unknown-effect fencing."""
from pathlib import Path
import hashlib,json,asyncio,io
import trimesh
from agi_core.mission_tools import digest_file
from agi_core.operation_receipts import read_receipt


async def validate_mesh_report(agent, report, target, run_id, *, recovered=False):
    if report.get('run_id') != run_id:
        raise RuntimeError('No final audit matches this scene run; an entity mesh cannot certify the whole requested scene.')
    if report.get('ok') is not True:
        raise RuntimeError('The engine rejected or did not validate this scene: '+str(report.get('error','no positive engine verdict')))
    file = Path(report['final_mesh']).resolve()
    if not file.is_relative_to(target) or not file.is_file() or file.suffix.lower() != '.glb':
        raise ValueError('Final mesh is outside this mission delivery directory.')
    before=file.stat();payload=await asyncio.to_thread(file.read_bytes)
    scene = await asyncio.to_thread(trimesh.load_scene, io.BytesIO(payload), file_type='glb', resolver=None)
    import numpy as np
    if not scene.geometry or any(not isinstance(m,trimesh.Trimesh) or not len(m.faces) or not np.isfinite(m.vertices).all() for m in scene.geometry.values()):
        raise ValueError('Final mesh has no finite actual surface geometry.')
    after=file.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('Final mesh changed during validation.')
    receipt = {'status':'completed','path':str(file),'sha256':hashlib.sha256(payload).hexdigest(),
               'size_bytes':len(payload),'engine_acceptance':report.get('acceptance'),
               'physical_fit_validated':False,'recovered':recovered}
    return receipt

async def execute_generation(agent,args):
    prompt=args.get('prompt','').strip()
    if not prompt:raise ValueError('An actual subject prompt is required.')
    engine=agent.tools.script('aurora_3d_pipeline.py')
    producer_sha256=digest_file(engine)
    signature=hashlib.sha256(json.dumps([prompt,producer_sha256],ensure_ascii=False).encode()).hexdigest()
    base=(Path(agent.workspace)/'.transfer_to_client'/agent.mission_id).resolve()
    target=base/('generation_'+signature[:16]);target.mkdir(parents=True,exist_ok=True)
    attempts=agent.state.setdefault('generation_3d_attempts',{})
    for attempt in attempts.values():
        if attempt.get('status') == 'completed' and attempt.get('prompt') == prompt:
            file=Path(attempt['path']).resolve()
            if file.is_relative_to(base) and file.is_file() and digest_file(file)==attempt['sha256']:
                agent._remember_resource('mesh',str(file),attempt)
                return {**attempt,'reused':True,'changed':False,'scope':'Unchanged accepted scene reused for the same immutable goal, even after a software update. Request a distinct mission for a new generation; quality and physical fit remain separate.'}
    # Reconcile only a matching positive terminal receipt; never infer success
    # from a dead PID, an empty queue or the presence of a partial GLB.
    for key, attempt in list(attempts.items()):
        if attempt.get('status') not in {'started','outcome_unknown','failed'} or attempt.get('prompt') != prompt:
            continue
        if not attempt.get('producer_sha256') or not attempt.get('run_id'):
            continue  # Legacy unknown outcomes retain their original fence.
        previous_target=Path(attempt['directory']).resolve()
        if not previous_target.is_relative_to(base):
            continue
        try:
            terminal=await asyncio.to_thread(read_receipt,previous_target,attempt['run_id'],prompt,attempt['producer_sha256'])
            report=terminal['result']
            final=Path(report['final_mesh']).resolve()
            if final.relative_to(previous_target).as_posix() not in {a['path'] for a in terminal['artifacts']}:
                raise ValueError('The final scene is not bound by this operation receipt')
            recovered=await validate_mesh_report(agent,report,previous_target,attempt['run_id'],recovered=True)
            expected=next(a['sha256'] for a in terminal['artifacts'] if a['path']==final.relative_to(previous_target).as_posix())
            if recovered['sha256']!=expected:raise ValueError('Recovered mesh changed after its terminal receipt was read')
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):
            continue
        attempts[key]={**recovered,'prompt':prompt,'run_id':attempt['run_id'],'producer_sha256':attempt['producer_sha256']}
        agent._remember_resource('mesh',recovered['path'],recovered)
        await agent._save()
        return {**attempts[key],'reused':True,'changed':False,'scope':'Verified persisted engine result recovered without restarting generation; semantic and physical validation remain separate.'}
    if any(a['status'] in {'started','outcome_unknown'} for a in attempts.values()):
        raise RuntimeError('An earlier 3D generation has an unknown outcome; inspect that run before creating another one.')
    previous=attempts.get(signature)
    if previous and previous['status']=='completed':
        file=Path(previous['path']).resolve()
        if file.is_relative_to(base) and file.is_file() and digest_file(file)==previous['sha256']:
            return {**previous,'reused':True,'changed':False,'scope':'Unchanged generated bytes reused; visual and physical quality not certified.'}
    if previous and previous['status'] in {'started','outcome_unknown'}:
        raise RuntimeError('This 3D generation has an unknown outcome. Inspect existing engine outputs before any replay: '+str(target))
    run_id=agent.mission_id+'_'+signature[:12]
    attempts[signature]={'status':'started','directory':str(target),'prompt':prompt,'run_id':run_id,'producer_sha256':producer_sha256}
    await agent._save()
    from agi_core.mission_agent import PYTHON_BIN
    try:
        output=await agent._run_process([PYTHON_BIN,str(engine),'--prompt',prompt,'--run-id',agent.mission_id+'_'+signature[:12],'--output-dir',str(target)],return_details=True)
    except asyncio.CancelledError:
        attempts[signature]['status']='outcome_unknown'
        raise
    except Exception:
        observations=agent.state.get('process_observations',[])
        unknown=agent.state.get('pending_process') or (observations and observations[-1]['result']['status'] in {'timed_out','interrupted_outcome_unknown'})
        attempts[signature]['status']='outcome_unknown' if unknown else 'failed'
        raise
    records=[];terminal=None
    try:
        terminal=await asyncio.to_thread(read_receipt,target,run_id,prompt,producer_sha256)
        records.append(terminal['result'])
    except FileNotFoundError:
        pass
    except (OSError,ValueError,KeyError,TypeError) as exc:
        attempts[signature]['status']='failed'
        raise RuntimeError('Persisted engine receipt is invalid; preserve the files and diagnose it before accepting this delivery') from exc
    for file in target.rglob('*.json'):
        if file.stat().st_size>8*1024*1024:continue
        try:
            data=json.loads(file.read_text(encoding='utf-8'))
            if isinstance(data,dict) and data.get('schema')=='aurora.pipeline.v1' and data.get('final_mesh'):records.append(data)
        except (OSError,ValueError):continue
    text=output.get('output','') if isinstance(output,dict) else str(output)
    for line in reversed(text.splitlines()):
        try:
            data=json.loads(line)
            if isinstance(data,dict) and data.get('final_mesh'):records.append(data);break
        except ValueError:continue
    if not records:
        attempts[signature]['status']='failed'
        raise RuntimeError('The engine produced no coherent final mesh audit; preserve its outputs and diagnose the actual error.')
    report=terminal['result'] if terminal else next((r for r in reversed(records) if r.get('run_id')==run_id),None)
    if report is None:
        attempts[signature]['status']='failed'
        raise RuntimeError('No final audit matches this scene run; an entity mesh cannot certify the whole requested scene.')
    try:
        receipt=await validate_mesh_report(agent,report,target,run_id)
        if terminal:
            relative=Path(receipt['path']).relative_to(target).as_posix()
            artifact=next((a for a in terminal['artifacts'] if a['path']==relative),None)
            if not artifact or artifact['sha256']!=receipt['sha256'] or artifact['size_bytes']!=receipt['size_bytes']:
                raise ValueError('The validated final mesh is not bound by the terminal engine receipt')
    except Exception:
        attempts[signature]['status']='failed'
        raise
    attempts[signature]={**receipt,'prompt':prompt,'run_id':run_id,'producer_sha256':producer_sha256}
    agent._remember_resource('mesh',receipt['path'],receipt)
    return {**receipt,'reused':False,'changed':True,'scope':'Readable generated geometry and byte integrity. Compare multiple views with the request; manufacturing requires separate engineering tests.'}
