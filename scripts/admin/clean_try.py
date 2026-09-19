bridge_file = "application/bridge_server.py"
with open(bridge_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.strip() == "try:":
        if i+1 < len(lines) and "except Exception as e:" in lines[i+1]:
            continue
    if "except Exception as e:" in line:
        if i-1 >= 0 and lines[i-1].strip() == "try:":
            continue
        if i+1 < len(lines) and "print(f'Error registering" in lines[i+1]:
            continue
    if "print(f'Error registering" in line:
        continue
    new_lines.append(line)

with open(bridge_file, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
