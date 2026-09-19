import re

with open('/home/juan/aurora-remote-cli/aurora_cli/interactive.py', 'r') as f:
    content = f.read()

# Replace Nexus import with JOBIACore
import_block = """from aurora_cli import display
try:
    from aurora_cli.core.jobia import JOBIACore
    jobia_engine = JOBIACore()
except ImportError:
    jobia_engine = None"""
content = re.sub(r"from aurora_cli import display\ntry:\n    from aurora_cli\.core\.nexus import AuroraNexus\n    nexus_engine = AuroraNexus\(\)\nexcept ImportError:\n    nexus_engine = None", import_block, content)

# Update internal commands list
commands_block = """    "/exit": "Exit Aurora",
    "/mode": "Changer le mode (autonome, fast, base)",
}"""
content = re.sub(r'    "/exit": "Exit Aurora",\n    "/nexus": "Launch Nexus Engineering Mode \(Async, RAG, Sandbox\)",\n}', commands_block, content)

# Update command handlers
handler_block = """            elif cmd == "/clear":
                console.clear()
            elif cmd == "/mode":
                if jobia_engine:
                    parts = user_input.split()
                    if len(parts) > 1:
                        new_mode = parts[1].lower()
                        if jobia_engine.set_mode(new_mode):
                            console.print(f"[bold green]Mode J.O.B.I.A. défini sur : {new_mode.upper()}[/bold green]")
                        else:
                            console.print("[red]Mode invalide (utilisez : autonome, fast, base).[/red]")
                    else:
                        console.print(f"[cyan]Mode actuel : {jobia_engine.mode.upper()}[/cyan]")
                else:
                    console.print("[red]Moteur J.O.B.I.A. non disponible.[/red]")
"""
content = re.sub(r'            elif cmd == "/clear":\n                console.clear()\n            elif cmd == "/nexus":[\s\S]*?non disponible\.\[/red\]"\)\n', handler_block, content)

# Add exit cleanup
content = re.sub(r'elif cmd == "/exit":\n                console.print\("\[dim\]Au revoir\.\[/dim\]"\)\n                break', 'elif cmd == "/exit":\n                if jobia_engine:\n                    jobia_engine.shutdown()\n                console.print("[dim]Au revoir.[/dim]")\n                break', content)

# Update bottom toolbar
content = re.sub(r'🔧 NEXUS ENGINEER MODE', '🔧 J.O.B.I.A. CORE', content)

with open('/home/juan/aurora-remote-cli/aurora_cli/interactive.py', 'w') as f:
    f.write(content)
