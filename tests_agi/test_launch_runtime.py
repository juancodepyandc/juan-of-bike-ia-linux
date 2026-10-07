"""Launch reuse must preserve other processes and detect changed source/artifacts."""
import importlib.util
import os
import subprocess
from pathlib import Path
import pytest

MODULE = Path(__file__).resolve().parents[1] / 'scripts/launch_runtime.py'
spec = importlib.util.spec_from_file_location('launch_runtime', MODULE)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


@pytest.mark.skipif(os.name == 'nt', reason='Linux launcher process identity uses /proc and Unix ownership')
def test_process_identity_ignores_other_tunnels_and_shell_substrings(tmp_path):
    proc = tmp_path / 'proc'
    proc.mkdir()
    root = tmp_path / 'aurora'
    commands = {
        11: ['cloudflared', 'tunnel', '--url', 'http://127.0.0.1:3001'],
        12: ['cloudflared', 'tunnel', '--url', 'http://127.0.0.1:9000'],
        13: ['bash', '-c', 'cloudflared tunnel --url http://127.0.0.1:3001'],
        14: ['bash', str(root / 'scripts/aurora-status-watcher.sh')],
        15: ['bash', str(tmp_path / 'other/scripts/aurora-status-watcher.sh')],
        16: [str(root / 'application/src-tauri/target/release/juan-of-bike-ia')],
    }
    for pid, args in commands.items():
        folder = proc / str(pid)
        folder.mkdir()
        (folder / 'cmdline').write_bytes(b'\0'.join(arg.encode() for arg in args) + b'\0')
    assert runtime.process_ids('tunnel', root, proc) == [11]
    assert runtime.process_ids('watcher', root, proc) == [14]
    assert runtime.process_ids('native', root, proc) == [16]


def test_web_cache_requires_unchanged_inputs_and_actual_output(tmp_path):
    app = tmp_path / 'application'
    (app / 'src').mkdir(parents=True)
    (app / 'dist').mkdir()
    source = app / 'src/main.ts'
    source.write_text('first')
    output = app / 'dist/index.html'
    output.write_text('compiled')
    cache = tmp_path / 'web.json'
    assert not runtime.build_is_current('web', tmp_path, cache)
    runtime.mark_build('web', tmp_path, cache)
    assert runtime.build_is_current('web', tmp_path, cache)
    source.write_text('second')
    assert not runtime.build_is_current('web', tmp_path, cache)
    source.write_text('first')
    output.write_text('truncated')
    assert not runtime.build_is_current('web', tmp_path, cache)


def test_native_cache_detects_rust_and_embedded_bundle_changes(tmp_path):
    app = tmp_path / 'application'
    binary = app / 'src-tauri/target/release/juan-of-bike-ia'
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b'native')
    binary.chmod(0o700)
    source = app / 'src-tauri/src/main.rs'
    source.parent.mkdir()
    source.write_text('rust')
    (app / 'dist').mkdir()
    bundle = app / 'dist/index.html'
    bundle.write_text('web')
    cache = tmp_path / 'native.json'
    runtime.mark_build('native', tmp_path, cache)
    assert runtime.build_is_current('native', tmp_path, cache)
    source.write_text('changed rust')
    assert not runtime.build_is_current('native', tmp_path, cache)
    source.write_text('rust')
    bundle.write_text('changed web')
    assert not runtime.build_is_current('native', tmp_path, cache)


def test_web_cache_invalidates_when_embedded_git_identity_changes(tmp_path):
    app = tmp_path / 'application'
    (app / 'dist').mkdir(parents=True)
    (app / 'dist/index.html').write_text('compiled', encoding='utf-8')
    def git(*args):
        return subprocess.run(['git', '-C', str(tmp_path), *args], check=True,
                              capture_output=True, text=True)
    git('init', '--initial-branch=main')
    identity = ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid']
    git(*identity, 'commit', '--allow-empty', '-m', 'first')
    cache = tmp_path / 'web.json'
    runtime.mark_build('web', tmp_path, cache)
    assert runtime.build_is_current('web', tmp_path, cache)
    git(*identity, 'commit', '--allow-empty', '-m', 'second')
    assert not runtime.build_is_current('web', tmp_path, cache)
