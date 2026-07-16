from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from code_loop_files import APPLICATION_ROOT, extract_files, syntax_check_files, write_project


class CodeLoopFilesTests(unittest.TestCase):
    def test_extracts_structured_and_inferred_files(self) -> None:
        structured = extract_files('<FILE path="src/main.py">print("ok")</FILE>')
        self.assertEqual(structured, [("src/main.py", 'print("ok")')])

        inferred = extract_files('```tsx\nexport default function App(){ return <main /> }\n```')
        self.assertEqual(inferred[0][0], "src/App.tsx")

    def test_writes_nested_tree_and_reports_python_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = pathlib.Path(tmp)
            files = [("src/main.py", "def broken(:\n    pass")]
            self.assertEqual(write_project(files, project), 1)
            report = syntax_check_files(project, files)
        self.assertFalse(report["passed"])
        self.assertRegex(report["flags"][0], r"py syntax line 1")

    def test_output_root_is_derived_from_application(self) -> None:
        self.assertEqual(APPLICATION_ROOT, pathlib.Path(__file__).resolve().parents[2])


if __name__ == "__main__":
    unittest.main()
