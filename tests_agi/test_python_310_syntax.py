"""Production code must stay valid Python 3.10, the oldest version the project supports.

Python 3.12 (PEP 701) accepts inside f-string replacement fields what earlier versions reject:
backslashes, the enclosing quote character, comments. One such f-string in
agi_core/agent_forge.py made the module unimportable on 3.10; the sub-agent rigor audit that
imports it then failed open and accepted workers that had run no tool at all.

On 3.10 and 3.11 compiling a file is the check. On 3.12+ the tokenizer exposes the expression
part of each f-string, so the same rule is checked statically there too, and a developer on 3.12
sees the failure before the CI does.
"""
from __future__ import annotations

import io
import sys
import token
import tokenize
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_no_undefined_names import ROOT, production_files  # noqa: E402

AGENT_CORE = sorted(path for path in (ROOT / "agi_core").glob("*.py") if path.is_file())
SUPPORTS_PEP701_TOKENS = sys.version_info >= (3, 12)


def _opening_quote(literal: str) -> str:
    """The quote sequence that opens a string token: \"\"\", \'\'\', " or '."""
    body = literal.lstrip("rRbBfFuU")
    return body[:3] if body[:3] in ('"""', "\'\'\'") else body[:1]


def _ends_enclosing(inner: str, enclosing: str) -> bool:
    """Before 3.12 an f-string was first read as an ordinary literal: an inner string opened by the
    enclosing delimiter ended it. A single quote inside a triple-quoted f-string does not."""
    if len(enclosing) == 3:
        return inner == enclosing
    return inner[:1] == enclosing


def pre_312_fstring_violations(source: str) -> list[str]:
    """Describe each f-string replacement field that only Python 3.12+ can parse."""
    if not SUPPORTS_PEP701_TOKENS:
        raise RuntimeError("token-level check needs Python 3.12+")
    problems: list[str] = []
    stack: list[dict] = []          # one entry per open f-string
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        line = tok.start[0]
        inside_expression = bool(stack) and stack[-1]["depth"] > 0
        if tok.type == token.FSTRING_START:
            quote = _opening_quote(tok.string)
            if inside_expression and _ends_enclosing(quote, stack[-1]["quote"]):
                problems.append(f"line {line}: nested f-string reuses the enclosing quote {stack[-1]['quote']}")
            stack.append({"quote": quote, "depth": 0})
            continue
        if not stack:
            continue
        current = stack[-1]
        if tok.type == token.FSTRING_END:
            stack.pop()
            continue
        if tok.type == token.FSTRING_MIDDLE:
            continue
        if tok.type == token.OP and tok.string == "{":
            current["depth"] += 1
            continue
        if tok.type == token.OP and tok.string == "}":
            current["depth"] = max(0, current["depth"] - 1)
            continue
        if current["depth"] == 0:
            continue
        if tok.type == token.COMMENT:
            problems.append(f"line {line}: comment inside an f-string expression")
        elif tok.type == token.STRING:
            if "\\" in tok.string:
                problems.append(f"line {line}: backslash inside an f-string expression")
            if _ends_enclosing(_opening_quote(tok.string), current["quote"]):
                problems.append(f"line {line}: f-string expression reuses the enclosing quote {current['quote']}")
        elif tok.type not in (token.NL, token.NEWLINE) and "\\" in tok.string:
            problems.append(f"line {line}: backslash inside an f-string expression")
    return problems


class Python310Syntax(unittest.TestCase):
    def files(self):
        return sorted(set(production_files()) | set(AGENT_CORE))

    @unittest.skipUnless(SUPPORTS_PEP701_TOKENS, "token-level check needs Python 3.12+")
    def test_the_checker_flags_what_python_310_rejects(self):
        # Built at run time so this test file itself stays valid Python 3.10.
        backslash = 'x = f"{a if a else ' + "'\\\\n'" + '}"\n'
        same_quote = 'x = f"{d["key"]}"\n'
        comment = 'x = f"""{a  # note\n}"""\n'
        self.assertTrue(pre_312_fstring_violations(backslash))
        self.assertTrue(pre_312_fstring_violations(same_quote))
        self.assertTrue(pre_312_fstring_violations(comment))
        accepted = (
            'block = a if a else "  - read_file"\n'
            'x = f"{block}\\n"\n'
            "y = f\"{d['key']}\" + f'{json.dumps(name)}'\n"
            'z = f"{value!r:>10} {{literal}}"\n'
            'w = f"""{parent or "racine"}"""\n'
        )
        self.assertTrue(pre_312_fstring_violations('x = f"""{a or """b"""}"""\n'))
        self.assertTrue(pre_312_fstring_violations('x = f"{f"{a}"}"\n'))
        self.assertEqual(pre_312_fstring_violations(accepted), [])

    def test_production_modules_are_valid_python_310(self):
        files = self.files()
        self.assertIn(ROOT / "agi_core" / "agent_forge.py", files)
        for path in files:
            with self.subTest(module=path.relative_to(ROOT).as_posix()):
                source = path.read_text(encoding="utf-8")
                if SUPPORTS_PEP701_TOKENS:
                    self.assertEqual(pre_312_fstring_violations(source), [])
                else:
                    compile(source, str(path), "exec", dont_inherit=True)


if __name__ == "__main__":
    unittest.main()
