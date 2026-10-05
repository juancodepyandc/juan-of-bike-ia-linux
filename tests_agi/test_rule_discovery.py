"""Independent grid outputs and held-out input checks over actual Python code."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.evaluation.rule_discovery import build_rule_discovery, consistent_rules, grade_rule_discovery, transform


class RuleDiscovery(unittest.TestCase):
    def test_coordinate_oracle_orientation_and_color_mapping(self):
        source=[[0,1,2],[3,4,0]]
        self.assertEqual(transform(source,1,False,list(range(5))),[[3,0],[4,1],[0,2]])
        self.assertEqual(transform(source,0,True,list(range(5))),[[2,1,0],[0,4,3]])
        self.assertEqual(transform(source,2,False,list(range(5))),[[0,4,3],[2,1,0]])
        self.assertEqual(transform(source,0,False,[4,3,2,1,0]),[[4,3,2],[1,0,4]])
        self.assertEqual(source,[[0,1,2],[3,4,0]])

    def test_generated_rules_are_unique_and_expected_values_are_not_fixture_fields(self):
        for seed in [0,1,27,819,1427013]:
            with self.subTest(seed=seed):
                _,fixtures,oracle=build_rule_discovery(seed)
                data=json.loads(fixtures['examples.json'])
                self.assertEqual(set(data),{'palette','train','test'})
                self.assertEqual(len(consistent_rules(data['train'])),1)
                self.assertEqual(len(oracle['hidden']),24)
                self.assertNotIn('rule',data)
                self.assertNotIn('public_outputs',data)

    def test_independent_hidden_grader_rejects_memorization_mutation_and_wrong_outputs(self):
        _,fixtures,oracle=build_rule_discovery(2874)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'examples.json').write_bytes(fixtures['examples.json'].encode())
            (root/'predictions.json').write_text(json.dumps({'outputs':oracle['public_outputs']}))
            rule=oracle['rule']
            # Separate zip-based implementation rather than importing the oracle.
            code=f'''TURNS={rule['turns']}
MIRROR={rule['reflected']}
COLORS={rule['colors']!r}
def solve(grid):
    g=[list(reversed(row)) if MIRROR else row[:] for row in grid]
    for i in range(TURNS):g=[list(row) for row in zip(*g[::-1])]
    return [[COLORS[v] for v in row] for row in g]
'''
            (root/'solver.py').write_text(code)
            self.assertTrue(grade_rule_discovery(root,oracle)['passed'])
            data=json.loads(fixtures['examples.json'])
            table={json.dumps(pair['input']):pair['output'] for pair in data['train']}
            (root/'solver.py').write_text('import json\nTABLE='+repr(table)+'\ndef solve(grid):\n    return TABLE[json.dumps(grid)]\n')
            self.assertFalse(grade_rule_discovery(root,oracle)['passed'])
            (root/'solver.py').write_text('import json,sys\nCASES=json.load(sys.stdin)\ndef solve(grid):\n    return next(c["output"] for c in CASES if c["input"]==grid)\n')
            self.assertFalse(grade_rule_discovery(root,oracle)['passed'])
            (root/'solver.py').write_text(code+'\n_original=solve\ndef solve(grid):\n    result=_original(grid)\n    grid.clear()\n    return result\n')
            self.assertFalse(grade_rule_discovery(root,oracle)['passed'])
            (root/'solver.py').write_text(code+'\nfrom pathlib import Path\nPath("predictions.json").write_text(\'{"outputs":[]}\')\n')
            self.assertFalse(grade_rule_discovery(root,oracle)['passed'])
            (root/'solver.py').write_text(code)
            (root/'predictions.json').write_text(json.dumps({'outputs':[]}))
            self.assertFalse(grade_rule_discovery(root,oracle)['passed'])
