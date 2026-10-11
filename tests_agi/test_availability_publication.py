"""Exercise the actual Bash publisher against an isolated Git remote on Linux."""
import shutil
import subprocess
from pathlib import Path
import os
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name != 'posix' or not shutil.which('bash') or not shutil.which('git'), reason='Bash launcher integration; portable monitor tested separately on all OS')
@pytest.mark.parametrize("concurrent_update", [False, True])
def test_failed_push_is_retried_even_when_files_unchanged(tmp_path, concurrent_update):
    def git(repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
    remote = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(remote)], check=True, capture_output=True)
    live = tmp_path / 'aurora-live'
    subprocess.run(['git', 'clone', str(remote), str(live)], check=True, capture_output=True)
    git(live, 'config', 'user.name', 'test')
    git(live, 'config', 'user.email', 'test@example.invalid')
    (live / 'README.md').write_text('<!--STATUS-->old<!--/STATUS-->')
    (live / 'tunnel.txt').write_text('')
    # Minimal offline renderer avoids any network access in this Git test.
    (live / 'status_check.py').write_text("def update(repo, mode, url, checker):\n from pathlib import Path\n p=Path(repo)\n (p/'README.md').write_text('<!--STATUS-->offline<!--/STATUS-->')\n (p/'tunnel.txt').write_text('')\n (p/'status.json').write_text('{}')\n return 'offline'\n")
    git(live, 'add', '.')
    git(live, 'commit', '-m', 'initial')
    git(live, 'push', 'origin', 'main')
    project = tmp_path / 'AuroraIA'
    (project / 'scripts').mkdir(parents=True)
    publisher = project / 'scripts/publish-live-link.sh'
    shutil.copy(ROOT / 'scripts/publish-live-link.sh', publisher)
    (project / 'tunnel.txt').write_text('https://test.trycloudflare.com')
    hook = remote / 'hooks/pre-receive'
    hook.write_text('#!/bin/sh\nexit 1\n')
    hook.chmod(0o755)
    env = dict(os.environ, AURORA_LIVE_REPO=str(live))
    first = subprocess.run(['bash', str(publisher), 'closed'], env=env, capture_output=True)
    assert first.returncode != 0
    committed = git(live, 'rev-parse', 'HEAD').stdout
    hook.unlink()
    if concurrent_update:
        other = tmp_path / 'external-monitor'
        subprocess.run(['git', 'clone', str(remote), str(other)], check=True, capture_output=True)
        git(other, 'config', 'user.name', 'external monitor')
        git(other, 'config', 'user.email', 'external@example.invalid')
        (other / 'README.md').write_text('<!--STATUS-->new external check<!--/STATUS-->')
        git(other, 'add', 'README.md')
        git(other, 'commit', '-m', 'external update')
        git(other, 'push', 'origin', 'main')
    second = subprocess.run(['bash', str(publisher), 'closed'], env=env, capture_output=True)
    assert second.returncode == 0, second.stderr.decode()
    head = git(live, 'rev-parse', 'HEAD').stdout
    if not concurrent_update:
        assert head == committed
    assert git(remote, 'rev-parse', 'main').stdout == head
    assert (live / 'README.md').read_text() == '<!--STATUS-->offline<!--/STATUS-->'
