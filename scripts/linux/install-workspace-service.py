#!/usr/bin/env python3
"""Install the independent PC browser service without restarting native Aurora."""
from pathlib import Path
import json
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
node = shutil.which('node')
if not node:
    raise SystemExit('Node.js et les dépendances npm de application/ sont requis.')
units = Path.home() / '.config/systemd/user'
units.mkdir(parents=True, exist_ok=True)
unit = '\n'.join([
    '[Unit]', 'Description=Aurora persistent workspace (PC-owned browser)',
    'After=network.target', '', '[Service]',
    'WorkingDirectory=' + str(root / 'application').replace('%', '%%'),
    'ExecStart=' + json.dumps(node) + ' ' + json.dumps(str(root / 'application/scripts/persistent-workspace.mjs')),
    'Restart=on-failure', 'RestartSec=5', 'TimeoutStopSec=10', 'UMask=0077', '',
    '[Install]', 'WantedBy=default.target', '',
])
(units / 'aurora-workspace.service').write_text(unit)
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
subprocess.run(['systemctl', '--user', 'enable', '--now', 'aurora-workspace.service'], check=True)
subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'aurora-workspace.service'], check=True)
print('Espace persistant installé ; application native conservée.')
