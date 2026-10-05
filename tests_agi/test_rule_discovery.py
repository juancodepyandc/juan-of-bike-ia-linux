"""Independent grid outputs and held-out input checks over actual Python code."""
import hashlib
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.evaluation.rule_discovery import build_rule_discovery, consistent_rules, grade_rule_discovery, transform


class RuleDiscovery(unittest.TestCase):
    @staticmethod
    def correct_solver(oracle):
        rule=oracle['rule']
        # Separate zip-based implementation rather than importing the oracle.
        return f'''TURNS={rule['turns']}
MIRROR={rule['reflected']}
COLORS={rule['colors']!r}
def solve(grid):
    g=[list(reversed(row)) if MIRROR else row[:] for row in grid]
    for i in range(TURNS):g=[list(row) for row in zip(*g[::-1])]
    return [[COLORS[v] for v in row] for row in g]
'''

    @staticmethod
    def write_delivery(root, fixtures, oracle, code):
        (root/'examples.json').write_bytes(fixtures['examples.json'].encode())
        (root/'predictions.json').write_text(json.dumps({'outputs':oracle['public_outputs']}))
        (root/'solver.py').write_text(code)

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
                self.assertEqual(len(oracle['hidden']),28)
                self.assertEqual([(len(case['input']),len(case['input'][0])) for case in oracle['hidden'][24:]],
                                 [(1,11),(13,1),(8,9),(9,8)])
                self.assertNotIn('rule',data)
                self.assertNotIn('public_outputs',data)

    def test_existing_seeded_examples_and_hidden_prefix_are_preserved(self):
        _,fixtures,oracle=build_rule_discovery(2874)
        self.assertEqual(hashlib.sha256(fixtures['examples.json'].encode()).hexdigest(),
                         'c0234da70edd9407af815fc82cfbf27d045bfbb4e3dcce564d1653586183773a')
        self.assertEqual(hashlib.sha256(json.dumps(oracle['hidden'][:24],sort_keys=True).encode()).hexdigest(),
                         '9d07fa6ec15f5733215c92f8b58a8ae4d1166c4f3a88d9e0f7185ae3019cdbb0')

    def test_independent_hidden_grader_rejects_memorization_mutation_and_wrong_outputs(self):
        _,fixtures,oracle=build_rule_discovery(2874)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            code=self.correct_solver(oracle)
            self.write_delivery(root,fixtures,oracle,code)
            data=json.loads(fixtures['examples.json'])
            real_run=subprocess.run
            with patch('scripts.evaluation.rule_discovery.subprocess.run',wraps=real_run) as run:
                grade=grade_rule_discovery(root,oracle)
            self.assertTrue(grade['passed'])
            for group in ('train','public','hidden'):
                self.assertTrue(grade[group+'_cases_passed'])
            self.assertTrue(grade['solver_inputs_preserved'])
            # The process gets each input once, without expected outputs or rule parameters.
            self.assertEqual(json.loads(run.call_args.kwargs['input']),
                             [pair['input'] for pair in data['train']]+data['test']+
                             [case['input'] for case in oracle['hidden']])
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

    def test_solver_must_match_training_and_public_examples_despite_correct_saved_predictions(self):
        _,fixtures,oracle=build_rule_discovery(2874)
        data=json.loads(fixtures['examples.json'])
        for group,bad_input in [('train',data['train'][0]['input']),('public',data['test'][0])]:
            with self.subTest(group=group), tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                code=self.correct_solver(oracle)+f'''
_original=solve
def solve(grid):
    if grid=={bad_input!r}: return []
    return _original(grid)
'''
                self.write_delivery(root,fixtures,oracle,code)
                grade=grade_rule_discovery(root,oracle)
                self.assertFalse(grade['passed'])
                self.assertTrue(grade['public_predictions_correct'])
                self.assertFalse(grade[group+'_cases_passed'])
                self.assertTrue(grade['hidden_cases_passed'])
                self.assertTrue(grade['solver_inputs_preserved'])

    def test_mutation_cannot_hide_behind_patched_copy_or_json_helpers(self):
        _,fixtures,oracle=build_rule_discovery(2874)
        for sabotage in ['import copy\ncopy.deepcopy=lambda value: value',
                         'import json\njson.dumps=lambda *args,**kwargs: "[]"']:
            with self.subTest(sabotage=sabotage), tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                code=self.correct_solver(oracle)+'\n'+sabotage+'''
_original=solve
def solve(grid):
    result=_original(grid)
    grid.clear()
    return result
'''
                self.write_delivery(root,fixtures,oracle,code)
                grade=grade_rule_discovery(root,oracle)
                self.assertFalse(grade['passed'])
                self.assertFalse(grade['solver_inputs_preserved'])
                self.assertTrue(grade['hidden_cases_passed'])

    def test_hidden_grids_reject_solvers_limited_to_dimensions_at_most_seven(self):
        _,fixtures,oracle=build_rule_discovery(2874)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            code=self.correct_solver(oracle)+'''
_original=solve
def solve(grid):
    if len(grid)>7 or len(grid[0])>7: return []
    return _original(grid)
'''
            self.write_delivery(root,fixtures,oracle,code)
            grade=grade_rule_discovery(root,oracle)
            self.assertFalse(grade['passed'])
            self.assertTrue(grade['train_cases_passed'])
            self.assertTrue(grade['public_cases_passed'])
            self.assertFalse(grade['hidden_cases_passed'])
            self.assertTrue(grade['solver_inputs_preserved'])

    def test_grader_executes_delivered_source_despite_timestamp_valid_cached_solver(self):
        _,fixtures,oracle=build_rule_discovery(2874)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            correct=self.correct_solver(oracle)
            self.write_delivery(root,fixtures,oracle,correct)
            source=root/'solver.py'
            # Timestamp caches require equal source byte sizes on every OS.
            correct_bytes=correct.encode('utf-8')
            source.write_bytes(correct_bytes)
            before=source.stat()
            py_compile.compile(str(source),doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
            incorrect='def solve(grid):\n    return []\n'
            incorrect+=' '*(len(correct_bytes)-len(incorrect.encode('utf-8')))
            incorrect_bytes=incorrect.encode('utf-8')
            source.write_bytes(incorrect_bytes)
            os.utime(source,ns=(before.st_atime_ns,before.st_mtime_ns))
            self.assertEqual(source.stat().st_size,before.st_size)
            self.assertEqual(source.stat().st_mtime_ns,before.st_mtime_ns)
            self.assertEqual(source.read_bytes(),incorrect_bytes)
            stale=subprocess.run([sys.executable,'-I','-c',
                'import json,sys; sys.path.insert(0,sys.argv[1]); from solver import solve; print(json.dumps(solve([[0,1],[2,3]])))',
                str(root)],text=True,capture_output=True,check=True)
            rule=oracle['rule']
            self.assertEqual(json.loads(stale.stdout),
                             transform([[0,1],[2,3]],rule['turns'],rule['reflected'],rule['colors']))
            grade=grade_rule_discovery(root,oracle)
            self.assertFalse(grade['passed'])
            self.assertTrue(grade['public_predictions_correct'])
            self.assertTrue(grade['solver_preserved_during_grading'])
            for group in ('train','public','hidden'):
                self.assertFalse(grade[group+'_cases_passed'])
