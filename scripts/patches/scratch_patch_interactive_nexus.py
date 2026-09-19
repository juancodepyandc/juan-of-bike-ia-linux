import re

with open('/home/juan/aurora-remote-cli/aurora_cli/interactive.py', 'r') as f:
    content = f.read()

# 1. Add Nexus import at the top
import_block = """from aurora_cli import display
try:
    from aurora_cli.core.nexus import AuroraNexus
    nexus_engine = AuroraNexus()
except ImportError:
    nexus_engine = None"""
content = re.sub(r"from aurora_cli import display", import_block, content, count=1)

# 2. Add /nexus to internal commands
commands_block = """    "/exit": "Exit Aurora",
    "/nexus": "Launch Nexus Engineering Mode (Async, RAG, Sandbox)",
}"""
content = re.sub(r'    "/exit": "Exit Aurora",\n}', commands_block, content)

# 3. Handle /nexus command
handler_block = """            elif cmd == "/clear":
                console.clear()
            elif cmd == "/nexus":
                if nexus_engine:
                    query = user_input[len("/nexus"):].strip()
                    if not query:
                        console.print("[yellow]Veuillez fournir une requête (ex: /nexus scan réseau).[/yellow]")
                        continue
                        
                    def on_nexus_done(task_id, result):
                        console.print(f"\\n[bold green]✔ NEXUS Tâche {task_id} Terminée[/bold green]")
                        console.print(result)
                        console.print("Aurora > ", end="", flush=True)
                        
                    task_id, route, past_ctx = nexus_engine.process_request(query, callback=on_nexus_done)
                    console.print(f"[bold cyan]NEXUS[/bold cyan] routage actif : [bold magenta]{route}[/bold magenta]")
                    if past_ctx:
                        console.print(f"[dim]Mémoire locale récupérée : {len(past_ctx)} entrées contextuelles.[/dim]")
                    console.print(f"[dim]Tâche {task_id} lancée en arrière-plan (non-bloquant)...[/dim]")
                else:
                    console.print("[red]Nexus Engine non disponible.[/red]")
"""
content = re.sub(r'            elif cmd == "/clear":\n                console.clear()', handler_block, content)

with open('/home/juan/aurora-remote-cli/aurora_cli/interactive.py', 'w') as f:
    f.write(content)
