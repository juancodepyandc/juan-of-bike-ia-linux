"""Independent grader regressions; these checks perform no model inference."""
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile
import unittest
from scripts.evaluation.mission_regression import build_case, grade_case


class EvaluationGraders(unittest.TestCase):
    def test_optimizer_rejects_type_schema_and_constraint_errors(self):
        _,_,oracle = build_case('optimizer',15791)
        cost_a,cost_b = oracle['costs']
        prod_a,prod_b = oracle['production']
        budget = oracle['budget']
        _,a,b = max((prod_a*a+prod_b*b,a,b) for a in range(budget//cost_a+1)
                    for b in range(budget//cost_b+1) if cost_a*a+cost_b*b<=budget)
        correct = {'a':a,'b':b,'pieces':prod_a*a+prod_b*b,'consommation':cost_a*a+cost_b*b}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            variants = [(correct,True),({**correct,'consommation':budget+1},False),
                        ({**correct,'extra':1},False),({**correct,'a':True},False),
                        ({**correct,'a':a+budget},False)]
            for data,expected in variants:
                with self.subTest(data=data):
                    (root/'answer.json').write_text(json.dumps(data),encoding='utf-8')
                    self.assertEqual(grade_case('optimizer',root,oracle,[])['passed'],expected)

    def test_csv_requires_actual_worker_role_skill_and_unmodified_bytes(self):
        _,fixtures,oracle = build_case('csv-worker',739)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'input.csv').write_bytes(fixtures['input.csv'].encode('utf-8'))
            (root/'summary.json').write_text(json.dumps({'rows':len(oracle['values']),'sum':sum(oracle['values'])}))
            skill = root/'.aurora/skills/AuditCSV/SKILL.md'
            skill.parent.mkdir(parents=True)
            skill.write_text('Real saved skill fixture')
            events = [{'type':'worker_complete','status':'completed'},
                      {'type':'tool_result','tool':'create_agent','ok':True,'result':{'name':'AuditCSV'}},
                      {'type':'tool_result','tool':'spawn_agent','ok':True,'result':{
                          'agent':'AuditCSV','passed':True,'workers':[{'status':'completed'}]}}]
            self.assertTrue(grade_case('csv-worker',root,oracle,events)['passed'])
            self.assertFalse(grade_case('csv-worker',root,oracle,[])['passed'])
            self.assertFalse(grade_case('csv-worker',root,oracle,events[:2])['passed'])
            generic = grade_case('csv-worker',root,oracle,[*events[:2],{**events[2],'result':{**events[2]['result'],'agent':''}}])
            self.assertFalse(generic['passed'])
            self.assertTrue(generic['any_worker_completed'])
            self.assertFalse(generic['requested_role_worker_completed'])
            self.assertFalse(grade_case('csv-worker',root,oracle,[*events[:2],{**events[2],'ok':False}])['passed'])
            (root/'summary.json').write_text(json.dumps({'rows':len(oracle['values'])-1,'sum':sum(oracle['values'][1:])}))
            self.assertFalse(grade_case('csv-worker',root,oracle,events)['passed'])
            (root/'summary.json').write_text(json.dumps({'rows':len(oracle['values']),'sum':sum(oracle['values'])}))
            (root/'input.csv').write_bytes(oracle['original'].replace(b'\r\n',b'\n'))
            self.assertFalse(grade_case('csv-worker',root,oracle,events)['passed'])

    def test_code_grader_detects_overlap_reverse_and_negative_errors(self):
        _,_,oracle = build_case('code-repair',973)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = '''def coverage(intervals):
    if any(a>b for a,b in intervals):
        raise ValueError('reversed')
    return len({x for a,b in intervals for x in range(a,b)})
'''
            (root/'solution.py').write_text(code)
            self.assertTrue(grade_case('code-repair',root,oracle,[])['passed'])
            (root/'solution.py').write_text('def coverage(intervals):\n    return sum(b-a for a,b in intervals)\n')
            self.assertFalse(grade_case('code-repair',root,oracle,[])['passed'])

    def test_code_grader_scores_current_source_despite_valid_stale_bytecode(self):
        _,_,oracle = build_case('code-repair',973)
        correct = ("def coverage(intervals):\n"
                   "    if any(a>b for a,b in intervals):\n"
                   "        raise ValueError('reversed')\n"
                   "    return len({x for a,b in intervals for x in range(a,b)})\n")
        wrong = 'def coverage(intervals):\n    return 0\n'
        wrong += '#'+('x'*(len(correct.encode())-len(wrong.encode())-2))+'\n'
        # Preserve exact bytes: Windows text writes would otherwise insert CRLF.
        correct_bytes,wrong_bytes = correct.encode('utf-8'),wrong.encode('utf-8')
        self.assertEqual(len(correct_bytes),len(wrong_bytes))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'solution.py'
            source.write_bytes(correct_bytes)
            stamp = 1711000000
            os.utime(source,(stamp,stamp))
            before = source.stat()
            py_compile.compile(str(source),doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
            source.write_bytes(wrong_bytes)
            os.utime(source,(stamp,stamp))
            self.assertEqual(source.stat().st_size,before.st_size)
            self.assertEqual(source.stat().st_mtime_ns,before.st_mtime_ns)
            self.assertEqual(source.read_bytes(),wrong_bytes)
            stale = subprocess.run([sys.executable,'-I','-c',
                'import sys; sys.path.insert(0,sys.argv[1]); from solution import coverage; print(coverage([[0,4],[2,7]]))',
                str(root)],text=True,capture_output=True,check=True)
            self.assertEqual(stale.stdout.strip(),'7')
            grade = grade_case('code-repair',root,oracle,[])
            self.assertFalse(grade['passed'])
            self.assertTrue(grade['source_preserved_during_grading'])
            self.assertEqual(source.read_bytes(),wrong_bytes)

    def test_code_grader_detects_mutation_even_if_solution_patches_deepcopy(self):
        _,_,oracle = build_case('code-repair',973)
        code = '''import copy
copy.deepcopy=lambda value:value
def coverage(intervals):
    if any(a>b for a,b in intervals):
        raise ValueError('reversed')
    result=len({x for a,b in intervals for x in range(a,b)})
    intervals.clear()
    return result
'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'solution.py').write_text(code,encoding='utf-8')
            grade = grade_case('code-repair',root,oracle,[])
            self.assertFalse(grade['passed'])
            self.assertTrue(grade['source_preserved_during_grading'])

    def test_code_grader_detects_mutation_of_retained_inputs_after_later_calls(self):
        oracle = {'cases':[[[0,2]],[[3,6]],[[8,9]]]}
        code = '''previous=None
def coverage(intervals):
    global previous
    if previous is not None:
        previous.clear()
    previous=intervals
    if any(a>b for a,b in intervals):
        raise ValueError('reversed')
    return len({x for a,b in intervals for x in range(a,b)})
'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'solution.py').write_text(code,encoding='utf-8')
            grade = grade_case('code-repair',root,oracle,[])
            self.assertFalse(grade['passed'])
            observations = json.loads(grade['stdout'].split('AURORA_COVERAGE_RESULTS=',1)[1])
            self.assertEqual([item['value'] for item in observations],[2,3,1])
            self.assertEqual([item['input_after'] for item in observations],
                             [json.dumps(intervals) for intervals in oracle['cases']])
            self.assertEqual([item['input_final'] for item in observations],['[]','[]','[[8, 9]]'])

    def test_code_grader_registers_module_for_dataclass_annotations(self):
        _,_,oracle = build_case('code-repair',973)
        code = '''from __future__ import annotations
from dataclasses import dataclass
@dataclass
class CoverageResult:
    value:int
def coverage(intervals):
    if any(a>b for a,b in intervals):
        raise ValueError('reversed')
    return CoverageResult(len({x for a,b in intervals for x in range(a,b)})).value
'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'solution.py').write_text(code,encoding='utf-8')
            grade = grade_case('code-repair',root,oracle,[])
            self.assertTrue(grade['passed'],grade['stderr'])
            self.assertTrue(grade['source_preserved_during_grading'])

    def test_code_grader_rejects_source_changed_during_execution(self):
        _,_,oracle = build_case('code-repair',973)
        code = '''from pathlib import Path
Path(__file__).write_text('def coverage(intervals):\\n    return 0\\n',encoding='utf-8')
def coverage(intervals):
    if any(a>b for a,b in intervals):
        raise ValueError('reversed')
    return len({x for a,b in intervals for x in range(a,b)})
'''
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'solution.py').write_text(code,encoding='utf-8')
            grade = grade_case('code-repair',root,oracle,[])
            self.assertFalse(grade['passed'])
            self.assertFalse(grade['source_preserved_during_grading'])

    def test_route_grader_rejects_wrong_energy_cost_paths_and_types(self):
        graph = {'nodes':['A','B','C','D'],'start':'A','end':'D','energy_budget':5,'edges':[
            {'from':'A','to':'B','cost':1,'energy':9},{'from':'B','to':'D','cost':1,'energy':9},
            {'from':'A','to':'D','cost':8,'energy':2},{'from':'A','to':'C','cost':2,'energy':2},
            {'from':'C','to':'D','cost':3,'energy':2}]}
        original = (json.dumps(graph)+'\n').encode('utf-8')
        oracle = {'graph':graph,'original':original}
        correct = {'path':['A','C','D'],'cost':5,'energy':4}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'network.json').write_bytes(original)
            variants = [(correct,True),({'path':['A','D'],'cost':8,'energy':2},False),
                ({'path':['A','B','D'],'cost':2,'energy':18},False),({**correct,'cost':4},False),
                ({**correct,'cost':5.0},False),({**correct,'energy':True},False),
                ({**correct,'path':['A','B','C','D']},False),({**correct,'extra':1},False),
                ({'path':[],'cost':None,'energy':None},False)]
            for data,expected in variants:
                with self.subTest(data=data):
                    (root/'route.json').write_text(json.dumps(data),encoding='utf-8')
                    self.assertEqual(grade_case('route-planning',root,oracle,[])['passed'],expected)
            (root/'route.json').write_text(json.dumps(correct),encoding='utf-8')
            (root/'network.json').write_bytes(original+b' ')
            self.assertFalse(grade_case('route-planning',root,oracle,[])['passed'])

    def test_route_grader_proves_unreachable_case_and_seeded_inputs(self):
        _,fixtures,oracle = build_case('route-planning',6357)
        self.assertEqual(build_case('route-planning',6357)[1],fixtures)
        self.assertNotEqual(build_case('route-planning',6358)[1],fixtures)
        graph = {**oracle['graph'],'energy_budget':0}
        original = json.dumps(graph).encode('utf-8')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'network.json').write_bytes(original)
            (root/'route.json').write_text('{"path":[],"cost":null,"energy":null}',encoding='utf-8')
            result = grade_case('route-planning',root,{'graph':graph,'original':original},[])
            self.assertTrue(result['passed'])
            self.assertIsNone(result['independent_optimum'])
            self.assertEqual(result['feasible_routes'],0)
