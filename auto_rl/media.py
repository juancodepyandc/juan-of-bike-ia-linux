"""CLI and service entry point for audited video and animation models."""
import argparse
import json
import time
import uuid
from pathlib import Path
from .config import STATE,defaults,validate,LABELS,TEXT_MODULES
from .runtime import validated_record
from .storage import exclusive_lock,atomic_json


def export_mp4(source,target,fps):
    """Encode the measured lossless frames without asking the model to rerender."""
    import subprocess
    from PIL import Image,ImageSequence
    with Image.open(source) as image:
        width,height=image.size
        frames=b''.join(frame.convert('RGB').tobytes() for frame in ImageSequence.Iterator(image))
    process=subprocess.run(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
                            '-s',f'{width}x{height}','-r',str(fps),'-i','pipe:0','-an',
                            '-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],
                           input=frames,capture_output=True,timeout=60)
    if process.returncode:raise RuntimeError('Export MP4 : '+process.stderr.decode(errors='replace')[-1000:])


def generate(module,prompt,use_base=None,reference_id=None,candidate_id=None):
    if module not in LABELS or not isinstance(prompt,str) or not 1<=len(prompt.strip())<=6000:
        raise ValueError('Module ou description invalide')
    with exclusive_lock(STATE/'cycle.lock'):
        if use_base is None:
            from .versions import preference
            use_base=preference(module)=='base'
        experimental=False
        if candidate_id:
            from .lineage import candidate_record
            record=candidate_record(module,candidate_id)
            record['name']='Expérimental · '+candidate_id
            experimental=True;use_base=False
        else:record=validated_record(module) if not use_base else None
        if not use_base and not record:
            raise ValueError('Ce module ne possède pas encore de candidat validé. Attendre son audit ou demander explicitement la base.')
        c=record['config'] if record and not use_base else defaults(module)
        c={**c,'generation':dict(c['generation'])}
        reference=None
        if module=='3d':
            import re
            if not isinstance(reference_id,str) or not re.fullmatch('[a-f0-9]{64}',reference_id):
                raise ValueError('La génération 3D demande une image de référence PNG ou JPEG')
            reference=STATE/'generated/references'/(reference_id+'.png')
            if not reference.is_file():raise ValueError('Image de référence introuvable')
        from .backends import resolve_paths,make_backend
        from .resources import release_idle_comfy
        if not release_idle_comfy():raise RuntimeError('Une génération ComfyUI est déjà en cours')
        if module not in {'image','video'}:
            from .resources import reclaim_comfy_ram
            reclaim_comfy_ram()
        backend=None
        try:
            backend=make_backend(c,resolve_paths(c))
            if record and not use_base:backend.adapter.load(record['adapter'])
            else:backend.adapter.enabled=False
            folder=STATE/'generated'/(module+'-'+uuid.uuid4().hex);folder.mkdir(parents=True)
            artifact=folder/('result'+backend.suffix)
            task={'prompt':prompt,'duration':c['generation']['duration']}
            if reference:task['image']=str(reference)
            started=time.monotonic()
            if module in TEXT_MODULES:
                answer=backend.chat([{'role':'user','content':prompt}],41)
                artifact.write_text(answer)
            else:backend.generate(task,41,artifact)
            backend.close();backend=None
            result={'module':module,'artifact':str(artifact),'model':record['name'] if record and not use_base else c['models'][module],
                    'validated':bool(record and not use_base and not experimental),'experimental':experimental,
                    'seconds':time.monotonic()-started}
            if module=='animation':
                from .motion_viewer import write_viewer
                result['viewer']=str(write_viewer(artifact))
            elif module=='video':
                video=artifact.with_suffix('.mp4')
                export_mp4(artifact,video,c['generation']['fps'])
                result.update(artifact=str(video),lossless_artifact=str(artifact))
            elif module in TEXT_MODULES:result['text']=artifact.read_text()
            elif module=='3d':
                import subprocess,shutil
                view_dir=folder/'views';view_dir.mkdir()
                blender=shutil.which('blender') or str(Path.home()/'.local/bin/blender')
                with (view_dir/'blender.log').open('w') as log:
                    process=subprocess.run([blender,'-b','--factory-startup','--disable-autoexec','-t','4',
                                            '--python',str(Path(__file__).with_name('render_mesh.py')),'--',str(artifact),str(view_dir),'4','384'],
                                           stdout=log,stderr=subprocess.STDOUT,timeout=240)
                if process.returncode:raise RuntimeError('La 3D est sauvegardée, mais le rendu des vues a échoué')
                result['views']=[str(p) for p in sorted(view_dir.glob('view_*.png'))]
            atomic_json(folder/'result.json',result)
            return result
        finally:
            if backend:backend.close()


def main():
    p=argparse.ArgumentParser(description='Aurora : test de génération pour les dix modules')
    p.add_argument('module',choices=LABELS);p.add_argument('prompt');p.add_argument('--base',action='store_true')
    p.add_argument('--reference-id');p.add_argument('--candidate')
    a=p.parse_args();print(json.dumps(generate(a.module,a.prompt,True if a.base else None,a.reference_id,a.candidate),ensure_ascii=False))

if __name__=='__main__':main()
