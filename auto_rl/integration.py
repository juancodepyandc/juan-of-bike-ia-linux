"""Training control and version selection through Aurora's existing bridge."""
from .config import STATE, LABELS
from .runtime import catalog,validated_record
from .storage import read_json


def register_routes(app, proxy):
    from flask import jsonify, request, send_file
    from pathlib import Path
    import secrets
    import time
    from urllib.parse import urlsplit
    import sys
    from . import versions
    # The controller depends on /proc, flock and systemd. Its import must not
    # prevent unrelated bridge modules from loading on Windows or macOS.
    control = None
    if sys.platform.startswith('linux'):
        from . import control
    token=secrets.token_urlsafe(32)

    def same_origin():
        origin=request.headers.get('Origin')
        if not origin:return True
        parsed=urlsplit(origin)
        # The local Aurora UI proxies /api through Vite with changeOrigin.
        # Trust its known origins, never a client-supplied forwarded-host header.
        allowed={request.host,'127.0.0.1:1420','localhost:1420','127.0.0.1:3001','localhost:3001'}
        return parsed.scheme in {'http','https'} and parsed.netloc in allowed

    def authorized():
        return same_origin() and secrets.compare_digest(request.headers.get('X-Aurora-Control',''),token)

    @app.get('/api/training/status')
    def training_status():
        if control is None:
            return jsonify({'supported': False, 'error': 'Le contrôleur d’entraînement local nécessite Linux.'}), 503
        cycle=read_json(STATE/'status.json',{})
        controller=control.snapshot(STATE)
        # When the child is SIGKILLed, its last status file can still say
        # ``self_play``. Prefer the supervisor's durable diagnostic so the
        # dashboard reports the actual terminal cause immediately.
        if controller.get('phase')=='error' and controller.get('diagnostic'):
            diagnostic=controller['diagnostic']
            cycle={**cycle,'phase':'error','status':diagnostic.get('message',controller.get('error')),
                   'diagnostic':diagnostic,'updated_at':controller.get('finished_at',cycle.get('updated_at'))}
        cycle['active']=control.alive(cycle) and cycle.get('phase') not in {'accepted','rejected','error','cancelled','remote_complete'}
        response=jsonify({'server_time':time.time(),'controller':controller,'cycle':cycle,
                        'campaign':read_json(STATE/'campaign.json',{}),
                        'autonomous':read_json(STATE/'autonomous_3d.json',{}),'modules':versions.modules(STATE)})
        response.headers['Cache-Control']='no-store'
        return response

    @app.get('/api/training/ui')
    def training_ui():
        if not same_origin():return jsonify({'error':'Origine du navigateur refusée'}),403
        return Path(__file__).with_name('dashboard.html').read_text().replace('__CONTROL_TOKEN__',token),200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}

    @app.get('/api/training/dashboard-extras.js')
    def training_dashboard_extras():
        return send_file(Path(__file__).with_name('dashboard_extras.js'),mimetype='text/javascript',max_age=0)

    @app.post('/api/training/control/<action>')
    def training_control(action):
        if not authorized():return jsonify({'error':'Actualiser cette page avant de commander l’entraînement'}),403
        if action not in {'start','stop','switch'}:return jsonify({'error':'Commande inconnue'}),404
        if control is None:
            return jsonify({'supported': False, 'error': 'Le contrôleur d’entraînement local nécessite Linux.'}), 503
        data=request.get_json(silent=True)
        try:
            result=control.start(data,STATE) if action=='start' else control.request(action,data,STATE)
            return jsonify(result),202
        except ValueError as exc:return jsonify({'error':str(exc)}),400
        except (RuntimeError,OSError) as exc:return jsonify({'error':str(exc)}),409

    @app.post('/api/training/selection')
    def training_selection():
        if not authorized():return jsonify({'error':'Actualiser cette page avant de changer de version'}),403
        data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify({'error':'Sélection JSON requise'}),400
        try:return jsonify(versions.select(data.get('module'),data.get('version'),STATE))
        except (ValueError,RuntimeError,OSError) as exc:return jsonify({'error':str(exc)}),409

    @app.get('/api/training/samples/<run_id>')
    def training_samples(run_id):
        from .previews import samples
        try:return jsonify({'samples':samples(STATE,run_id)})
        except (ValueError,OSError) as exc:return jsonify({'error':str(exc)}),404

    @app.get('/api/training/samples/<run_id>/asset')
    def training_sample(run_id):
        from .previews import sample_path,mesh_page
        try:
            path=sample_path(STATE,run_id,request.args.get('name',''))
            if request.args.get('viewer')=='1':
                if path.suffix=='.npz':
                    from .motion_viewer import write_viewer
                    return send_file(write_viewer(path))
                if path.suffix=='.glb':
                    from urllib.parse import quote
                    return mesh_page('/api/training/samples/'+quote(run_id,safe='')+'/asset?name='+quote(request.args['name'],safe=''))
            return send_file(path,mimetype='text/plain' if path.suffix in {'.py','.txt'} else None)
        except (ValueError,OSError) as exc:return jsonify({'error':str(exc)}),404

    @app.get('/api/training/viewer-lib/<path:name>')
    def training_viewer_lib(name):
        from .config import ROOT
        allowed={'build/three.module.js','build/three.core.js',
                 'examples/jsm/loaders/GLTFLoader.js','examples/jsm/controls/OrbitControls.js',
                 'examples/jsm/utils/BufferGeometryUtils.js'}
        if name not in allowed:return jsonify({'error':'Bibliothèque inconnue'}),404
        return send_file(ROOT/'application/node_modules/three'/name)

    @app.get('/api/training/diagnostic/<run_id>')
    def training_diagnostic(run_id):
        from .previews import run_folder
        try:
            run=run_folder(STATE,run_id)
            saved=read_json(run/'diagnostic.json',{})
            if saved:
                return jsonify(saved)
            status=read_json(run/'status.json',{})
            # A Linux OOM kill can terminate the cycle child before Python gets
            # a chance to write diagnostic.json.  Recover the signal from the
            # controller history so the UI explains the real failure instead
            # of leaving only the last self-play label visible.
            history_row=None
            current=read_json(STATE/'control.json',{})
            sources=[current]
            sources.extend(read_json(p,{}) for p in (STATE/'control_history').glob('*.json'))
            for control_record in sources:
                for row in control_record.get('history',[]):
                    if row.get('run_id')==run_id:
                        history_row=row
                        break
                if history_row:break
            if history_row and int(history_row.get('exit_code',0))<0:
                code=int(history_row['exit_code'])
                message=f"Processus interrompu par le système (signal {-code})."
                if code==-9:
                    message="Mémoire RAM épuisée : Linux a arrêté le processus (OOM killer, SIGKILL)."
                return jsonify({'message':message,'exit_code':code,
                                'last_step':status.get('status'),'traceback':'',
                                'recovered_from_controller':True})
            return jsonify({'message':status.get('status'),
                            'traceback':(run/'error.log').read_text()[-12000:] if (run/'error.log').is_file() else ''})
        except (ValueError,OSError) as exc:return jsonify({'error':str(exc)}),404

    @app.get('/api/training/runs/<run_id>/<artifact>')
    def training_run_artifact(run_id,artifact):
        names={'report':'report.json','candidate':'candidate.safetensors'}
        root=(STATE/'runs').resolve();folder=(root/run_id).resolve()
        if folder.parent!=root or artifact not in names:
            return jsonify({'error':'Résultat inconnu'}),404
        path=(folder/names[artifact]).resolve()
        if not path.is_relative_to(folder) or not path.is_file():return jsonify({'error':'Résultat absent'}),404
        return send_file(path,as_attachment=artifact=='candidate',download_name=run_id+'.safetensors' if artifact=='candidate' else None)

    @app.post('/api/training/media')
    def training_media():return proxy('http://127.0.0.1:11435/api/media/generate')

    @app.get('/api/training/parents/<module>')
    def training_parents(module):
        if module not in LABELS:return jsonify({'error':'Module inconnu'}),404
        from .lineage import choices,choose
        try:
            values=choices(module,STATE);best=choose(module,'best',STATE)
            return jsonify({'best':best['run_id'] if best else None,
                            'method':best.get('selection_reason') if best else 'original',
                            'candidates':[{k:r.get(k) for k in ('run_id','eligible','base_gain_points','validation_loss')} for r in values]})
        except (ValueError,RuntimeError,OSError) as exc:return jsonify({'error':str(exc)}),409

    @app.post('/api/training/reference')
    def training_reference():
        if not authorized():return jsonify({'error':'Actualiser la page'}),403
        file=request.files.get('image')
        if not file:return jsonify({'error':'Image manquante'}),400
        data=file.read(10*2**20+1)
        if len(data)>10*2**20:return jsonify({'error':'Image limitée à 10 Mo'}),413
        try:
            from PIL import Image
            import io,hashlib
            with Image.open(io.BytesIO(data)) as source:
                if source.width*source.height>20_000_000:raise ValueError('Image trop grande')
                source.load();source=source.convert('RGBA');source.thumbnail((2048,2048))
                buffer=io.BytesIO();source.save(buffer,format='PNG');data=buffer.getvalue()
            identifier=hashlib.sha256(data).hexdigest()
            folder=STATE/'generated/references';folder.mkdir(parents=True,exist_ok=True)
            destination=folder/(identifier+'.png')
            if not destination.exists():destination.write_bytes(data)
            return jsonify({'reference_id':identifier})
        except (OSError,ValueError) as exc:return jsonify({'error':str(exc)}),400

    def review_report(run_id):
        root=(STATE/'runs').resolve();run=(root/run_id).resolve()
        if run.parent!=root:raise ValueError('Cycle invalide')
        report=read_json(run/'report.json')
        if not report:raise ValueError('Audit non disponible')
        return run,report

    @app.get('/api/training/review/<run_id>')
    def training_review(run_id):
        try:
            from urllib.parse import quote
            from .evaluation import write_html
            run,report=review_report(run_id)
            url=lambda path:'/api/training/review/'+quote(run_id,safe='')+'/asset?path='+quote(path,safe='')
            page=write_html(run,report,web_asset=url,return_html=True)
            page=page.replace('href="report.json"','href="/api/training/runs/'+quote(run_id,safe='')+'/report"')
            page=page.replace(' · <a href="config.json">Paramètres</a>','')
            return page,200,{'Content-Type':'text/html; charset=utf-8'}
        except (OSError,ValueError,KeyError) as exc:return jsonify({'error':str(exc)}),404

    @app.get('/api/training/review/<run_id>/asset')
    def training_review_asset(run_id):
        try:
            from .storage import file_hash
            _,report=review_report(run_id)
            permitted={}
            for branch in ('base','champion','candidate','parent'):
                for row in report.get(branch) or []:
                    artifact=Path(row['artifact']).resolve();permitted[artifact]=row.get('sha256')
                    for view in row['judge'].get('metrics',{}).get('views',[]):permitted[Path(view).resolve()]=None
                    if artifact.suffix=='.npz':permitted[artifact.with_suffix('.motion.html')]=None
            path=Path(request.args.get('path','')).resolve()
            if path not in permitted or not path.is_relative_to((STATE/'runs').resolve()) or not path.is_file():
                raise ValueError('Fichier hors de cet audit')
            if permitted[path] and file_hash(path)!=permitted[path]:raise ValueError('Le fichier de l’audit a changé')
            return send_file(path)
        except (ValueError,OSError,KeyError) as exc:return jsonify({'error':str(exc)}),404

    @app.get('/api/training/artifact/<path:name>')
    def training_artifact(name):
        root=(STATE/'generated').resolve();path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.suffix not in {'.png','.jpg','.webp','.mp4','.npz','.html','.json','.txt','.py','.wav','.glb'}:
            return jsonify({'error':'Fichier introuvable'}),404
        if path.suffix=='.glb' and request.args.get('viewer')=='1':
            from .previews import mesh_page
            return mesh_page(request.path)
        return send_file(path,mimetype='text/plain' if path.suffix in {'.py','.txt'} else None)

    @app.get('/api/training/models')
    def training_models():return jsonify({'models':catalog(include_base=True)})

    @app.post('/api/training/image-workflow')
    def image_workflow():
        from .image_runtime import apply_validated_workflow
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict) or not isinstance(data.get('workflow'), dict):
            return jsonify({'error':'Workflow ComfyUI manquant'}),400
        try:
            return jsonify({'workflow':apply_validated_workflow(apply_validated_workflow(data['workflow']), 'video')})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            return jsonify({'error':str(exc)}),409

    @app.route('/proxy/trained/<path:path>',methods=['GET','POST'])
    def trained_proxy(path):
        if path not in {'api/tags','api/show','api/chat','api/generate','health'}:
            return jsonify({'error':'Route de modèle inconnue'}),404
        return proxy('http://127.0.0.1:11435/'+path)
