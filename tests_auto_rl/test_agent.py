import re
import json

text = """
Je vais utiliser la commande ls.
```json
{
  "tool": "run_command",
  "args": {"command": "ls -la"}
}
```
Et voilà.
"""

match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
if match:
    print(json.loads(match.group(1)))
