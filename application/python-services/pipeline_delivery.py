"""Preserve a produced mesh after failed validation without declaring success."""
from pathlib import Path
import json
import struct


def valid_mesh(path):
    try:
        with Path(path).open('rb') as stream:
            magic,version,size=struct.unpack('<4sII',stream.read(12))
            if magic!=b'glTF' or version!=2 or size!=Path(path).stat().st_size:return False
            doc=None;binary=0
            while stream.tell()<size:
                length,kind=struct.unpack('<II',stream.read(8))
                if length%4 or stream.tell()+length>size:return False
                if kind==0x4E4F534A:doc=json.loads(stream.read(length))
                else:
                    if kind==0x004E4942:binary=length
                    stream.seek(length,1)
            if not doc or not binary:return False
            accessors=doc.get('accessors',[])
            return any(p.get('mode',4) in {4,5,6} and isinstance(p.get('attributes',{}).get('POSITION'),int) and
                       0<=p['attributes']['POSITION']<len(accessors) and
                       accessors[p['attributes']['POSITION']].get('count',0)>=3
                       for m in doc.get('meshes',[]) for p in m.get('primitives',[]))
    except (OSError,ValueError,TypeError,struct.error):return False


def preserve_failed_mesh(result, output_dir, run_id):
    if result.get('ok'):return result
    output_dir=Path(output_dir)
    root=output_dir.parent if output_dir.name in {'work','models'} and output_dir.parent.name==run_id else output_dir
    candidates=[Path(result[k]) for k in ('final_mesh','rejected_mesh','raw_mesh') if isinstance(result.get(k),str)]
    candidates+=sorted(output_dir.glob(run_id+'_*.glb'),key=lambda p:p.stat().st_mtime,reverse=True)
    candidate=next((p for p in candidates if p.resolve().is_relative_to(root.resolve()) and valid_mesh(p)),None)
    if candidate is None:return {**result,'mesh_produced':False}
    result={**result,'mesh_produced':True,'final_mesh':str(candidate),'validation_status':'failed'}
    try:
        from livraison_organisee import organiser
        reference=Path(result.get('front_reference') or output_dir/(run_id+'_reference.png'))
        if not reference.resolve().is_relative_to(root.resolve()) or not reference.is_file():reference=None
        packaged=organiser(root,run_id,final_mesh=str(candidate),front_reference=str(reference) if reference else None)
        result['livraison']=packaged.get('livraison') or {}
        result['final_mesh']=result['livraison'].get('modele_couleurs',str(candidate))
        if not packaged.get('ok'):result['delivery_error']=packaged.get('error','Packaging incomplete')
    except Exception as exc:result['delivery_error']=str(exc)
    return result
