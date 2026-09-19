import re

with open('/home/juan/aurora-remote-cli/aurora_cli/cli.py', 'r') as f:
    content = f.read()

import_block = """import click
from rich.traceback import install as install_rich_traceback

# Install expert traceback handler
install_rich_traceback(show_locals=True, theme="monokai")

from aurora_cli import config"""

content = re.sub(r"import click[\s\n]+from aurora_cli import config", import_block, content, flags=re.MULTILINE)

with open('/home/juan/aurora-remote-cli/aurora_cli/cli.py', 'w') as f:
    f.write(content)
