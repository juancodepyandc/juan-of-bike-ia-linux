import re

with open('/home/juan/aurora-remote-cli/aurora_cli/interactive.py', 'r') as f:
    content = f.read()

# Replace JOBIACore with AGICore setup
import_block = """from aurora_cli import display
try:
    from aurora_cli.core.jobia import JOBIACore
    jobia_engine = JOBIACore()
except ImportError:
    jobia_engine = None

try:
    from aurora_cli.agi.cognitive_loop import CognitiveEngine
    agi_engine = CognitiveEngine()
except ImportError:
    agi_engine = None"""
content = re.sub(r"from aurora_cli import display\ntry:\n    from aurora_cli\.core\.jobia import JOBIACore\n    jobia_engine = JOBIACore\(\)\nexcept ImportError:\n    jobia_engine = None", import_block, content)

# Update internal commands list
commands_block = """    "/exit": "Exit Aurora",
    "/mode": "Changer le mode (autonome, fast, base)",
    "/agi": "Lancer la boucle cognitive AGI (Swarm, RAG, ReAct)",
}"""
content = re.sub(r'    "/exit": "Exit Aurora",\n    "/mode": "Changer le mode \(autonome, fast, base\)",\n}', commands_block, content)

# Add handler for /agi
handler_block = """            elif cmd == "/mode":
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
            elif cmd == "/agi":
                if agi_engine:
                    query = user_input[len("/agi"):].strip()
                    if not query:
                        console.print("[yellow]Requête requise (ex: /agi optimise ce code de sécurité).[/yellow]")
                        continue
                    console.print("[bold magenta]🧠 Activation du Swarm AGI (ReAct + Vector DB)...[/bold magenta]")
                    agi_engine.run_sync(query)
                else:
                    console.print("[red]Moteur AGI non initialisé (vérifiez les dépendances, ex: chromadb).[/red]")
"""
content = re.sub(r'            elif cmd == "/mode":[\s\S]*?non disponible\.\[/red\]"\)', handler_block, content)

with open('/home/juan/aurora-remote-cli/aurora_cli/interactive.py', 'w') as f:
    f.write(content)
