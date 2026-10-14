import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from flask import Flask, jsonify

from application.generation_cleanup import owned_run_root, remove_cancelled_run


def test_cleanup_only_removes_dedicated_run_not_sources_or_other_runs(tmp_path):
    workspace = tmp_path
    base = workspace / 'output/3d/conversations/topic'
    run = base / 'juan_bike_123'
    other = base / 'juan_bike_456'
    (run / 'models').mkdir(parents=True)
    other.mkdir()
    (run / 'models/incomplete.glb').write_bytes(b'partial')
    assert owned_run_root(workspace, str(run), ['--output-dir', str(run / 'models')]) == str(run)
    assert owned_run_root(workspace, str(base), ['--output-dir', str(base)]) is None
    assert owned_run_root(workspace, str(run), ['--output-dir', str(other)]) is None
    assert remove_cancelled_run(workspace, str(run))['removed']
    assert not run.exists() and other.exists()
    if os.name != 'nt':
        run.symlink_to(other, target_is_directory=True)
        assert not remove_cancelled_run(workspace, str(run))['removed']
        assert other.exists()


def runner_namespace(workspace):
    # Execute the actual worker and cancellation functions without starting the
    # production bridge, model loaders, GPU queues or public tunnel.
    path = Path(__file__).resolve().parents[1] / 'application/routes/python_bp_routes.py'
    tree = ast.parse(path.read_text())
    names = {'_run_python_job', '_terminate_job_process', '_cancel_video_job_response',
             '_persist_job_state', '_finalize_cancelled_job'}
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    for function in functions:
        function.decorator_list = []
    namespace = dict(os=os, sys=sys, subprocess=subprocess, threading=threading,
                     time=time, json=json, pathlib=__import__('pathlib'), jsonify=jsonify,
                     WORKSPACE=str(workspace), _python_jobs={}, _python_job_processes={},
                     _python_jobs_lock=threading.Lock(), _AURORA_3D_EN_COURS=threading.Event(),
                     _is_video_gpu_job=lambda _: False, _build_python_env=lambda: dict(os.environ),
                     _emit_progress=lambda *args, **kwargs: None, _clean_stderr=lambda value: value)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def test_cancel_real_nonvideo_worker_stays_cancelled_and_removes_run(tmp_path):
    n = runner_namespace(tmp_path)
    run = tmp_path / 'output/3d/conversations/topic/juan_bike_123'
    (run / 'models').mkdir(parents=True)
    script = tmp_path / 'slow.py'
    script.write_text("import time\nprint('PROGRESS:running', flush=True)\ntime.sleep(60)\n")
    (run / 'models/partial.glb').write_bytes(b'partial')
    n['_python_jobs']['test'] = {'status': 'running', 'cleanupRoot': str(run)}
    thread = threading.Thread(target=n['_run_python_job'], args=('test', str(script), []))
    thread.start()
    deadline = time.monotonic() + 10
    while 'test' not in n['_python_job_processes'] and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(.02)
    app = Flask(__name__)
    with app.app_context():
        response = n['_cancel_video_job_response']('test')
        assert response.json['ok']
    thread.join(10)
    assert not thread.is_alive()
    job = n['_python_jobs']['test']
    assert job['status'] == 'cancelled'
    assert job['exitCode'] == -15
    assert job['cleanup']['removed']
    assert not run.exists() and script.exists()


def test_cancel_before_spawn_never_starts_process_and_cleans_run(tmp_path):
    n = runner_namespace(tmp_path)
    run = tmp_path / 'output/3d/conversations/topic/juan_bike_123'
    run.mkdir(parents=True)
    n['_python_jobs']['test'] = {'status': 'cancelled', 'cancelRequested': True, 'cleanupRoot': str(run)}
    n['_run_python_job']('test', 'does-not-exist.py', [])
    assert not n['_python_job_processes']
    assert n['_python_jobs']['test']['status'] == 'cancelled'
    assert not run.exists()


def test_cleanup_removes_empty_conversation_parent_but_preserves_other_contents(tmp_path):
    parent=tmp_path/'output/3d/conversations/topic'
    run=parent/'juan_bike_123';run.mkdir(parents=True)
    result=remove_cancelled_run(tmp_path,str(run))
    assert result['removed'] and result['conversationRemoved']
    assert not parent.exists()
    assert remove_cancelled_run(tmp_path,str(run))['conversationRemoved']
    run.mkdir(parents=True);evidence=parent/'retained.json';evidence.write_text('preserved')
    result=remove_cancelled_run(tmp_path,str(run))
    assert result['removed'] and not result['conversationRemoved']
    assert evidence.read_text()=='preserved'


def test_missing_conversation_is_not_inferred_from_unavailable_storage(tmp_path):
    from application.generation_cleanup import conversation_presence
    base=tmp_path/'output/3d/conversations';missing=base/'deleted'
    assert conversation_presence(tmp_path,str(missing)) is None
    base.mkdir(parents=True)
    assert conversation_presence(tmp_path,str(missing)) is False
    missing.mkdir()
    assert conversation_presence(tmp_path,str(missing)) is True
    assert conversation_presence(tmp_path,str(tmp_path)) is None
    if os.name!='nt':
        linked=base/'linked';linked.symlink_to(missing,target_is_directory=True)
        assert conversation_presence(tmp_path,str(linked)) is None
