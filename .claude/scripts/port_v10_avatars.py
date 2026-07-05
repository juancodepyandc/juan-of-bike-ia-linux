"""Convert v10/avatars.jsx (IIFE attaching to window) to a clean React module .tsx.

Steps:
- Strip the (function () { ... })(); IIFE wrapping
- Remove the React destructure (we import React normally)
- Replace Object.assign(window, ...) with `export {...}`
- Prefix file with `// @ts-nocheck` + `import React from 'react'`
- Keep the auto-keyframes injection block (runtime CSS once)
"""
import re, os
SRC = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\.claude\test-outputs\design_v4\v10\v10\avatars.jsx'
DST = r'C:\Users\Juan\Desktop\ia\AuroraIA-v2\application\src\components\studio\avatars.tsx'

with open(SRC, 'r', encoding='utf-8') as f:
    src = f.read()

# 1. Remove the IIFE opener line: `(function () {`
src = re.sub(r'\(function \(\) \{\s*\n', '', src, count=1)
# 2. Remove `const { useEffect, useRef, useState, useMemo } = React;`
src = re.sub(r'\s*const \{[^}]*\} = React;\s*\n', '\n', src, count=1)
# 3. Replace closing `})();` with blank
src = re.sub(r'\}\)\(\);\s*$', '', src)
# 4. Replace Object.assign(window, {...}) with export
src = src.replace(
    'Object.assign(window, { Avatar, AvatarMini, P, FightCloud, Onomatopee, mixColor });',
    'export { Avatar, AvatarMini, P, FightCloud, Onomatopee, mixColor };'
)
# 5. Reindent: original code was inside an IIFE so most lines have 2-space indent. Keep as-is — works fine in JSX.

# Header
header = '// @ts-nocheck\n// Studio avatar system — ported from v10 design.\n// Auto-injects 40 keyframes (a10-*) on first import.\n// Public API: Avatar, AvatarMini, FightCloud, Onomatopee, P (persona data), mixColor.\nimport React from \'react\';\n\n'

with open(DST, 'w', encoding='utf-8') as f:
    f.write(header + src)
print(f'wrote {DST} ({os.path.getsize(DST)} bytes)')
