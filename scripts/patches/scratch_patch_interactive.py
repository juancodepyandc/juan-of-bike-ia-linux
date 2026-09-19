import re

with open('/home/juan/aurora-remote-cli/aurora_cli/interactive.py', 'r') as f:
    content = f.read()

# Replace the prompt_session block
new_prompt_setup = """
    # Style cyberpunk / moderne expert
    custom_style = Style.from_dict({
        'bottom-toolbar': 'bg:#1e1e1e #ffffff',
        'bottom-toolbar.text': '#00ffff bold',
        'completion-menu': 'bg:#1e1e1e #00ffff',
        'completion-menu.completion.current': 'bg:#00ffff #000000 bold',
        'completion-menu.completion': 'bg:#1e1e1e #00aaaa',
        'scrollbar.background': 'bg:#222222',
        'scrollbar.button': 'bg:#00ffff',
        'prompt': '#00ffff bold',
        'keyword': '#ff00ff bold',
        'string': '#ffff00',
    })

    def bottom_toolbar():
        return [
            ('class:bottom-toolbar', ' '),
            ('class:bottom-toolbar.text', f'🔧 NEXUS ENGINEER MODE | Session: {session_id[:8] if session_id else "N/A"} | Press [Tab] for completion '),
        ]

    prompt_session: PromptSession = PromptSession(
        history=FileHistory(history_file),
        completer=COMMAND_COMPLETER,
        style=custom_style,
        lexer=PygmentsLexer(AuroraLexer),
        complete_while_typing=True,
        bottom_toolbar=bottom_toolbar,
        mouse_support=True
    )
"""
content = re.sub(r"# Style cyberpunk.*?prompt_session:\s*PromptSession\s*=\s*PromptSession\([\s\S]*?complete_while_typing=True\s*\)", new_prompt_setup, content, flags=re.MULTILINE)

with open('/home/juan/aurora-remote-cli/aurora_cli/interactive.py', 'w') as f:
    f.write(content)
