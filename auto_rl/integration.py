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
    try:
        from . import control
    except Exception:
        control = None
    token=secrets.token_urlsafe(32)

    def same_origin():
        origin=request.headers.get('Origin')
        if not origin:return True
        parsed=urlsplit(origin)
        # The local Aurora UI proxies /api through Vite with changeOrigin or calls from Tauri webview.
        allowed={request.host,'127.0.0.1:1420','localhost:1420','127.0.0.1:3001','localhost:3001','localhost','tauri.localhost'}
        return parsed.scheme in {'http','https','tauri'} and parsed.netloc in allowed

    def authorized():
        return same_origin() and secrets.compare_digest(request.headers.get('X-Aurora-Control',''),token)

    @app.get('/api/training/status')
    def training_status():
        if control is None or not sys.platform.startswith('linux'):
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
        if action not in {'start','stop','stop_after_cycle','switch'}:return jsonify({'error':'Commande inconnue'}),404
        if control is None or not sys.platform.startswith('linux'):
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

    @app.get('/api/models/reinforced-status')
    def models_reinforced_status():
        from .reinforced_registry import get_reinforced_overview
        overview = get_reinforced_overview(STATE)
        cycle = read_json(STATE/'status.json', {})
        controller = control.snapshot(STATE) if control is not None else {}
        is_active = bool(
            control is not None
            and (
                controller.get('active')
                or (
                    control.alive(cycle)
                    and cycle.get('phase') not in {'accepted', 'rejected', 'error', 'cancelled', 'remote_complete'}
                )
            )
        )
        overview['training'] = {
            'active': is_active,
            'module': controller.get('module') or cycle.get('module'),
            'mode': controller.get('mode') or cycle.get('mode'),
            'phase': cycle.get('phase') or controller.get('phase'),
            'status': cycle.get('status') or controller.get('status'),
            'run_id': cycle.get('run_id') or controller.get('run_id'),
            'cycle_index': controller.get('cycle_index', 1),
            'stop_after_cycle': bool(controller.get('stop_after_cycle') or (STATE / 'stop_after_cycle.txt').exists()),
            'progress_percent': cycle.get('progress_percent', 0),
            'local_generations_done': cycle.get('local_generations_done', 0),
            'local_generations_planned': cycle.get('local_generations_planned', 0),
            'updated_at': cycle.get('updated_at') or controller.get('updated_at'),
        }
        response = jsonify(overview)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.post('/api/models/reinforced-select')
    def models_reinforced_select():
        if not same_origin():
            return jsonify({'error': 'Origine refusée'}), 403
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({'error': 'Sélection JSON requise'}), 400
        module = data.get('module')
        variant = data.get('variant') or data.get('version') or 'validated'
        try:
            result = versions.select(module, variant, STATE, allow_pending=True)
            from .reinforced_registry import get_reinforced_overview
            overview = get_reinforced_overview(STATE)
            return jsonify({**result, 'module_info': overview['modules'].get(result['module'])})
        except (ValueError, RuntimeError, OSError) as exc:
            return jsonify({'error': str(exc)}), 409

    @app.post('/api/models/training-stop')
    def models_training_stop():
        if not same_origin():
            return jsonify({'error': 'Origine refusée'}), 403
        if control is None:
            return jsonify({'supported': False, 'error': 'Contrôleur Linux requis'}), 503
        data = request.get_json(silent=True) or {}
        stop_mode = 'stop_after_cycle' if data.get('after_cycle') or data.get('action') == 'stop_after_cycle' else 'stop'
        try:
            return jsonify(control.request(stop_mode, data, STATE)), 202
        except (ValueError, RuntimeError, OSError) as exc:
            return jsonify({'error': str(exc)}), 409

    @app.post('/api/models/training-start')
    def models_training_start():
        if not same_origin():
            return jsonify({'error': 'Origine refusée'}), 403
        if control is None:
            return jsonify({'supported': False, 'error': 'Contrôleur Linux requis'}), 503
        data = request.get_json(silent=True) or {}
        try:
            return jsonify(control.start(data, STATE)), 202
        except (ValueError, RuntimeError, OSError) as exc:
            return jsonify({'error': str(exc)}), 409

    @app.route('/api/agi/prompt-director', methods=['GET', 'POST'])
    def agi_prompt_director():
        import importlib
        import agi_core.prompt_intelligence as _pi
        _pi = importlib.reload(_pi)
        if request.method == 'GET':
            raw_prompt = request.args.get('prompt', '')
            target_module = request.args.get('module') or request.args.get('target_module') or 'image'
            mode_hint = request.args.get('mode')
            requested_style = request.args.get('style')
            has_reference = request.args.get('has_reference', '').lower() in {'1', 'true', 'yes'}
            conversation_context = request.args.get('context') or request.args.get('conversation_context') or ''
            use_llm = request.args.get('use_llm', '1').lower() not in {'0', 'false', 'no'}
            open_world_grounding = request.args.get('open_world', '1').lower() not in {'0', 'false', 'no'}
        else:
            data = request.get_json(silent=True) or {}
            raw_prompt = data.get('prompt', '')
            target_module = data.get('module') or data.get('target_module') or 'image'
            mode_hint = data.get('mode')
            requested_style = data.get('style')
            has_reference = bool(data.get('has_reference', False))
            conversation_context = data.get('context') or data.get('conversation_context') or ''
            use_llm = bool(data.get('use_llm', True))
            open_world_grounding = bool(data.get('open_world_grounding', True))
        result = _pi.analyze_and_direct_prompt(
            raw_prompt=raw_prompt,
            target_module=target_module,
            mode_hint=mode_hint,
            requested_style=requested_style,
            has_reference=has_reference,
            conversation_context=conversation_context,
            use_llm=use_llm,
            open_world_grounding=open_world_grounding,
        )
        return jsonify(result)

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
        try:
            return proxy('http://127.0.0.1:11435/'+path, timeout=1800)
        except Exception:
            # In-process fallback via auto_rl.serve so reinforced models work even if :11435 daemon is stopped
            from .serve import create_app as _create_serve_app
            sub_app = _create_serve_app(STATE)
            with sub_app.test_client() as client:
                resp = client.open(
                    '/' + path,
                    method=request.method,
                    data=request.get_data(),
                    content_type=request.content_type or 'application/json',
                )
                from flask import Response as _FlaskResponse
                return _FlaskResponse(resp.get_data(), status=resp.status_code, content_type=resp.content_type)

    @app.get('/api/agi/council/roster')
    def agi_council_roster():
        from agi_core.flagship_council import (
            get_module_council_roster,
            list_installed_ollama_models,
            list_jules_remote_sessions,
            resolve_jules_binary,
        )
        module = request.args.get('module', 'general')
        installed = list_installed_ollama_models()
        rosters = {
            m: get_module_council_roster(m)
            for m in ('conversation', 'code', 'cyber', 'learning', 'business', 'cowork', 'simulator', '3d', 'image', 'drawing', 'video', 'animation', 'voice')
        }
        return jsonify({
            'ok': True,
            'requested_module': module,
            'active_roster': get_module_council_roster(module),
            'all_module_rosters': rosters,
            'installed_models': [m.get('name') for m in installed],
            'jules_cli_available': bool(resolve_jules_binary()),
            'jules_sessions': list_jules_remote_sessions().get('sessions', [])[:10],
        })

    @app.post('/api/agi/council')
    def agi_council_deliberate():
        from flask import Response as _FlaskResponse, stream_with_context as _swc
        from agi_core.flagship_council import run_moa_council, stream_moa_council_ollama_format
        data = request.get_json(silent=True) or {}
        module = str(data.get('module') or 'general')
        prompt = str(data.get('prompt') or '')
        system_prompt = str(data.get('system') or data.get('system_prompt') or '')
        messages = data.get('messages')
        stream = bool(data.get('stream', False))
        if stream:
            msgs = messages or ([{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt}] if system_prompt else [{'role': 'user', 'content': prompt}])
            return _FlaskResponse(
                _swc(stream_moa_council_ollama_format(msgs, requested_model=data.get('model'), module=module, options=data.get('options'))),
                mimetype='application/x-ndjson',
            )
        res = run_moa_council(
            prompt,
            system_prompt=system_prompt,
            messages=messages,
            module=module,
            depth=str(data.get('depth') or 'max'),
            require_vision=bool(data.get('require_vision', False)),
            temperature=float(data.get('temperature', 0.25)),
            num_ctx=int(data.get('num_ctx', 32768)),
            num_predict=int(data.get('num_predict', 16384)),
        )
        return jsonify(res)

    @app.route('/api/agi/jules', methods=['GET', 'POST'])
    def agi_jules_endpoint():
        from agi_core.flagship_council import launch_jules_remote_session, list_jules_remote_sessions
        if request.method == 'GET':
            return jsonify(list_jules_remote_sessions())
        data = request.get_json(silent=True) or {}
        task = str(data.get('task') or data.get('prompt') or '').strip()
        if not task:
            return jsonify({'ok': False, 'error': 'Champ `task` ou `prompt` requis.'}), 400
        repo = str(data.get('repo') or 'juancodepyandc/juan-of-bike-ia-linux').strip()
        parallel = int(data.get('parallel') or 1)
        return jsonify(launch_jules_remote_session(task, repo=repo, parallel=parallel))

    def _resolve_local_glb_path(raw_ref: str) -> Path | None:
        if not raw_ref:
            return None
        ref = str(raw_ref).strip()
        if 'path=' in ref:
            import urllib.parse as _up
            q = _up.parse_qs(_up.urlsplit(ref).query)
            if q.get('path'):
                ref = q['path'][0]
        p = Path(ref)
        if p.is_file():
            return p
        cand = ROOT / 'application' / ref.lstrip('/')
        if cand.is_file():
            return cand
        return None

    @app.post('/api/3d/anchors/auto-detect')
    def anchors_3d_auto_detect():
        import sys as _sys
        svc_dir = str(ROOT / 'application' / 'python-services')
        if svc_dir not in _sys.path:
            _sys.path.insert(0, svc_dir)
        from universal_anatomical_rig_engine import detect_anatomical_anchor_points
        data = request.get_json(silent=True) or {}
        raw_path = data.get('glb_path') or data.get('model_url') or ''
        glb_p = _resolve_local_glb_path(raw_path)
        if glb_p is None:
            return jsonify({'ok': False, 'error': f'Fichier GLB introuvable: {raw_path}'}), 404
        res = detect_anatomical_anchor_points(glb_p)
        return jsonify(res), (200 if res.get('ok') else 409)

    @app.post('/api/3d/anchors/apply-rig')
    def anchors_3d_apply_rig():
        import sys as _sys
        import urllib.parse as _up
        svc_dir = str(ROOT / 'application' / 'python-services')
        if svc_dir not in _sys.path:
            _sys.path.insert(0, svc_dir)
        from universal_anatomical_rig_engine import apply_validated_anchors_and_animate
        data = request.get_json(silent=True) or {}
        raw_path = data.get('glb_path') or data.get('model_url') or ''
        glb_p = _resolve_local_glb_path(raw_path)
        if glb_p is None:
            return jsonify({'ok': False, 'error': f'Fichier GLB introuvable: {raw_path}'}), 404
        anchors = data.get('anchors')
        motion_type = str(data.get('motion_type') or 'walk_cycle')
        res = apply_validated_anchors_and_animate(glb_p, anchors=anchors, motion_type=motion_type)
        if res.get('ok') and res.get('animated_glb'):
            res['animated_model_url'] = '/api/3d-file?path=' + _up.quote(str(res['animated_glb']))
        return jsonify(res), (200 if res.get('ok') else 409)

    @app.route('/api/billing/credits', methods=['GET', 'POST'])
    def billing_credits_endpoint():
        billing_file = STATE / 'credit_billing_state.json'
        default_state = {
            'billing_mode': 'infinite',  # 'infinite' (par défaut) | 'subscription' | 'juan_of_bike_coins'
            'infinite_credits_active': True,
            'juan_of_bike_coins': 2500,
            'subscription_tier': 'aurora_ultimate_vm',
            'video_vm_only_enforced': True,
            'default_model_variant': 'validated',
        }
        current = dict(default_state)
        if billing_file.exists():
            try:
                loaded = json.loads(billing_file.read_text(encoding='utf-8'))
                if isinstance(loaded, dict):
                    current.update(loaded)
            except Exception:
                pass
        if request.method == 'POST':
            body = request.get_json(silent=True) or {}
            if isinstance(body, dict):
                for k in ('billing_mode', 'infinite_credits_active', 'juan_of_bike_coins', 'subscription_tier', 'video_vm_only_enforced'):
                    if k in body:
                        current[k] = body[k]
                current['infinite_credits_active'] = (current.get('billing_mode') == 'infinite')
                STATE.mkdir(parents=True, exist_ok=True)
                billing_file.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
        return jsonify({'ok': True, **current})


