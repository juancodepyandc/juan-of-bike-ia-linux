import ast
from pathlib import Path
import tempfile
import unittest
import subprocess

from scripts.audit.inventory import PythonInventory, inspect_repo, physical_tree
from scripts.audit.relationships import components


class InventoryTests(unittest.TestCase):
    def test_cycles_distinguish_recursion_from_acyclic_imports(self):
        self.assertEqual(components({'a': {'b'}, 'b': {'a', 'c'}, 'c': {'d'}, 'd': set(), 'e': {'e'}}),
                         [['a', 'b'], ['e']])

    def test_nested_units_and_routes_keep_source_locations(self):
        visitor = PythonInventory('example.py')
        visitor.visit(ast.parse('@app.get("/status")\ndef status():\n    def helper():\n        return read()\n    return helper()\n'))
        self.assertEqual([(u['name'], u['line']) for u in visitor.units], [('status', 2), ('status.helper', 3)])
        self.assertEqual([u['public'] for u in visitor.units], [True, False])
        self.assertEqual(visitor.routes[0]['path'], '/status')
        self.assertEqual(visitor.calls[-2]['caller'], 'status')
        self.assertEqual(visitor.calls[-2]['callee'], 'helper')

    def test_markers_never_include_secret_values(self):
        visitor = PythonInventory('example.py')
        visitor.visit(ast.parse('key = "sk-' + 'x' * 24 + '"\npath = "/home/example/file"'))
        self.assertEqual([m['kind'] for m in visitor.markers], ['secret_candidate', 'absolute_path'])
        self.assertTrue(all(set(m) == {'file', 'line', 'kind'} for m in visitor.markers))

    def test_parse_failure_does_not_hide_following_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', directory], check=True)
            (root / 'bad.py').write_text('def broken(:')
            (root / 'good.py').write_text('def valid():\n    return 1\n')
            subprocess.run(['git', 'add', '.'], cwd=root, check=True)
            result = inspect_repo(root, 'fixture')
            self.assertEqual(len(result['parse_failures']), 1)
            self.assertEqual(result['units'][0]['name'], 'valid')

    def test_physical_tree_does_not_follow_symlink_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'loop').symlink_to(root, target_is_directory=True)
            counts = physical_tree(root, root / 'tree.gz')
            self.assertEqual(counts, {'symlink': 1, 'file': 1})


if __name__ == '__main__':
    unittest.main()
