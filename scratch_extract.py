with open('/home/juan/AuroraIA/application/output/test_code_output.md', 'r') as f:
    text = f.read()

import re
parts = text.split("```typescript")
if len(parts) > 1:
    code = parts[1].split("```")[0]
    code = code.replace("readonly value: V;", "value: V;")
    with open('/home/juan/AuroraIA/scratch_lru_k_cache.ts', 'w') as out:
        out.write(code)
    print(f"Extracted {len(code)} characters to scratch_lru_k_cache.ts")
