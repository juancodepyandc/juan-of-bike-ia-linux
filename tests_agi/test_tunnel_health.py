"""An arbitrary HTTP 200 must not identify an Aurora Quick Tunnel."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify-tunnel-url.sh'


@pytest.mark.skipif(os.name != 'posix' or not shutil.which('bash'), reason='POSIX tunnel launcher')
@pytest.mark.parametrize('payload,expected', [
    ('{"ok":true,"service":"aurora-bridge"}', 0),
    ('{"ok":true,"service":"foreign-server"}', 1),
    ('{"ok":"true","service":"aurora-bridge"}', 1),
    ('<html>Proxy error</html>', 1),
])
def test_verifier_requires_the_bridge_protocol(tmp_path, payload, expected):
    for name, source in {'curl': '#!/bin/sh\nprintf "%s" "$FIXTURE_HEALTH"\n',
                         'dig': '#!/bin/sh\nexit 0\n'}.items():
        path = tmp_path / name
        path.write_text(source)
        path.chmod(0o700)
    env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + os.environ['PATH'], FIXTURE_HEALTH=payload)
    result = subprocess.run(['bash', str(SCRIPT), 'https://fixture.trycloudflare.com', '1'],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == expected, result.stderr
