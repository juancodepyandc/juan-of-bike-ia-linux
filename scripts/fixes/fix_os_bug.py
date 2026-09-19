import re
file_path = "/home/juan/AuroraIA/application/bridge_server.py"
with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

# Remove the bad import
code = code.replace("import pty, os, select", "")

# Add pty and select imports at the top of _cli_run_mission
new_func_def = """def _cli_run_mission(mission_id):
    import pty, select
    \"\"\"Execute a mission autonomously with FULL Agentic ReAct Loop.\"\"\""""
    
code = code.replace("def _cli_run_mission(mission_id):\n    \"\"\"Execute a mission autonomously with FULL Agentic ReAct Loop.\"\"\"", new_func_def)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Bug fixed")
