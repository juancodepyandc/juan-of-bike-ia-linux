"""Bounded subprocess jobs for engineering mesh exports, shared by web/native/CLI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from uuid import uuid4

from flask import jsonify, request, send_file


def register_engineering_routes(bp, workspace):
    jobs = {}
    lock = threading.Lock()
    root = Path(workspace)/'output'/'engineering'
    receipts = Path(workspace)/'.aurora'/'engineering-receipts'
    receipts.mkdir(parents=True,exist_ok=True,mode=0o700)

    def owner():
        # Requests arrive through the bridge's existing sensitive-route guard.
        # Retained jobs are additionally separated by the supplied credential.
        from application.device_pairing import request_identity
        return hashlib.sha256(request_identity(workspace).encode()).hexdigest()

    def save_receipt(job_id, job):
        receipt = {k:v for k,v in job.items() if k != 'directory'}
        path = receipts/(job_id+'.json')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(receipt),encoding='utf-8')
        temporary.chmod(0o600)
        temporary.replace(path)

    def run(job_id, source, config, directory):
        result = {'ok': False, 'error': 'Export interrompu.'}
        try:
            process = subprocess.run([sys.executable, str(Path(__file__).with_name('engineering_mesh.py')),
                                      '--source', str(source), '--settings', str(config), '--output', str(directory/'package')],
                                     capture_output=True, text=True, encoding='utf-8', timeout=180)
            lines = process.stdout.strip().splitlines()
            if lines:
                result = json.loads(lines[-1])
            if process.returncode != 0:
                result['ok'] = False
                result.setdefault('error', 'Le moteur de découpe a échoué.')
            if result.get('ok'):
                digest = hashlib.sha256()
                with (directory/'package.zip').open('rb') as archive:
                    for chunk in iter(lambda: archive.read(1024*1024), b''):
                        digest.update(chunk)
                result['archive_sha256'] = digest.hexdigest()
        except subprocess.TimeoutExpired:
            result = {'ok': False, 'error': 'Export supérieur à 180 secondes. Réduire le nombre de faces ou de coupes.'}
        except Exception:
            result = {'ok': False, 'error': 'Le moteur d’export n’a pas renvoyé de résultat valide.'}
        finally:
            source.unlink(missing_ok=True)
            config.unlink(missing_ok=True)
        with lock:
            jobs[job_id].update(state='done' if result.get('ok') else 'error', result=result)
            save_receipt(job_id,jobs[job_id])

    @bp.route('/api/3d/engineering', methods=['POST'])
    def create_export():
        upload = request.files.get('mesh')
        suffix = Path(upload.filename or '').suffix.lower() if upload else ''
        if not upload or suffix not in {'.glb', '.stl', '.obj'}:
            return jsonify(ok=False, error='Joindre un maillage GLB, STL ou OBJ.'), 400
        try:
            from application.engineering_mesh import settings
            options = settings(json.loads(request.form.get('settings', '{}')))
        except (ValueError, TypeError) as exc:
            return jsonify(ok=False, error=f'Paramètres invalides : {exc}'), 400
        job_id = 'eng_' + uuid4().hex
        directory = root/job_id
        with lock:
            if any(j['state'] == 'running' for j in jobs.values()):
                return jsonify(ok=False, error='Un export est déjà en cours. Attendre sa fin.'), 409
            # Keep bounded in-memory receipts; files remain on disk.
            for key in list(jobs):
                if time.time() - jobs[key]['created'] > 86400:
                    del jobs[key]
            if len(jobs) >= 100:
                return jsonify(ok=False, error='Limite quotidienne d’exports atteinte.'), 429
            jobs[job_id] = {'owner': owner(), 'created': time.time(), 'state': 'running', 'directory': directory}
        try:
            directory.mkdir(parents=True, exist_ok=False)
            save_receipt(job_id,jobs[job_id])
            source = directory/('source'+suffix)
            data = upload.stream.read(120*1024*1024+1)
            if not data or len(data) > 120*1024*1024:
                raise ValueError('Maillage vide ou supérieur à 120 Mo.')
            source.write_bytes(data)
            config = directory/'settings.json'
            config.write_text(json.dumps(options), encoding='utf-8')
            threading.Thread(target=run, args=(job_id, source, config, directory), daemon=True).start()
        except Exception as exc:
            with lock:
                jobs.pop(job_id, None)
            (receipts/(job_id+'.json')).unlink(missing_ok=True)
            return jsonify(ok=False, error=str(exc)), 400
        return jsonify(ok=True, job_id=job_id), 202

    def get_job(job_id):
        import re
        if not re.fullmatch(r'eng_[0-9a-f]{32}',job_id): return None
        with lock:
            job = jobs.get(job_id)
            if job is None:
                directory = root/job_id
                try:
                    job = json.loads((receipts/(job_id+'.json')).read_text(encoding='utf-8'))
                    if not isinstance(job,dict): return None
                    if job.get('owner') != owner(): return None
                    job['directory'] = directory
                    # A complete package can survive a lost in-memory receipt.
                    if job.get('state') == 'running':
                        archive = directory/'package.zip'; manifest = directory/'package'/'assembly.json'
                        if archive.is_file() and manifest.is_file():
                            job.update(state='done',result={'ok':True,'report':json.loads(manifest.read_text()),
                                'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
                        else:
                            job.update(state='error',result={'ok':False,'error':'Le bridge a été interrompu pendant la préparation. Aucun export n’a été relancé.'})
                        save_receipt(job_id,job)
                except (OSError,ValueError,TypeError): return None
            return dict(job) if job and job['owner'] == owner() else None

    @bp.route('/api/3d/engineering/<job_id>', methods=['GET'])
    def job_status(job_id):
        job = get_job(job_id)
        if not job:
            return jsonify(ok=False, error='Export introuvable ou bridge redémarré.'), 404
        response = {'ok': True, 'state': job['state'], **job.get('result', {})}
        if job['state'] == 'done':
            response['download_url'] = f'/api/3d/engineering/{job_id}/download'
        return jsonify(response)

    @bp.route('/api/3d/engineering/<job_id>/download', methods=['GET'])
    def download(job_id):
        job = get_job(job_id)
        if not job or job['state'] != 'done':
            return jsonify(ok=False, error='Archive non disponible.'), 404
        return send_file(job['directory']/'package.zip', as_attachment=True, download_name=f'aurora-{job_id}.zip')
