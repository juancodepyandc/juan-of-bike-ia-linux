"""Seeded, real-model local mission evaluation with independent output graders.

No AGI certification, model replacement, training or service startup. The host
command runner has no OS sandbox.
"""
from __future__ import annotations
import argparse
import asyncio
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import random
import secrets
import subprocess
import sys
import time
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]


def build_case(name, seed):
    rng = random.Random(seed)
    if name=='optimizer':
        costs = [rng.randint(7,25) for _ in range(2)]
        production = [rng.randint(2,12) for _ in range(2)]
        budget = rng.randint(80,180)
        data = {'costs':costs,'production':production,'budget':budget}
        prompt = (f"Machine A : coût {costs[0]}, production {production[0]}. Machine B : coût {costs[1]}, production {production[1]}. "
                  f"Budget maximal {budget}, cycles entiers non négatifs. Calcule l'optimum par Python exhaustif. "
                  "Écris answer.json avec exactement les champs entiers a,b,pieces,consommation. "
                  "Vérifie le contenu sauvegardé, le budget, le calcul et l'optimalité avant de conclure.")
        return prompt,{},data
    if name=='csv-worker':
        values = [rng.randint(-50,100) for _ in range(rng.randint(5,12))]
        values[0] = 17  # Keep the first row nonzero to expose skipped-row errors.
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(['label','value'])
        writer.writerows((f'ligne {i}, donnée',v) for i,v in enumerate(values))
        content = stream.getvalue()
        prompt = ("Lis input.csv, crée une compétence AuditCSV avec create_skill et un rôle AuditCSV avec create_agent. "
                  "Délègue avec spawn_agent une vérification du nombre de lignes et de la somme de value en utilisant ce rôle. "
                  "Écris summary.json contenant exactement les entiers rows et sum. Préserve les octets de input.csv. "
                  "Vérifie les résultats sauvegardés à partir des données réelles avant de conclure.")
        return prompt,{'input.csv':content},{'values':values,'original':content.encode()}
    if name=='code-repair':
        cases = [[],[[-2,-1],[-1,1]],[[0,4],[2,7]],[[1,1]],[[5,-3]]]
        for index in range(80):
            intervals = [[rng.randint(-40,40),rng.randint(-40,40)] for _ in range(rng.randrange(12))]
            if index<40:
                intervals = [sorted(pair) for pair in intervals]
            cases.append(intervals)
        prompt = ("Corrige solution.py : coverage(intervals) doit calculer la longueur de l'union d'intervalles entiers "
                  "semi-ouverts [a,b), sans modifier l'entrée. Ignore les intervalles vides ; a>b doit lever ValueError. "
                  "Utilise Python standard et teste les chevauchements, intervalles adjacents, valeurs négatives, "
                  "liste vide, intervalles inversés et non-mutation. Préserve les autres fichiers. "
                  "Livrable : solution.py fonctionnel ; résume les vérifications réellement exécutées.")
        return prompt,{'solution.py':'def coverage(intervals):\n    return sum(b-a for a,b in intervals)\n'},{'cases':cases}
    raise ValueError('Unknown evaluation case: '+name)


def grade_case(name, workspace, oracle, events):
    if name=='optimizer':
        from agi_core.mission_tools import strict_json
        data = strict_json((workspace/'answer.json').read_text(encoding='utf-8'))
        if not isinstance(data,dict) or set(data)!={'a','b','pieces','consommation'} or any(type(v) is not int for v in data.values()):
            return {'passed':False,'reason':'Wrong fields or types','observed':data}
        costs,production,budget = oracle['costs'],oracle['production'],oracle['budget']
        optimum = max(production[0]*a+production[1]*b for a in range(budget//costs[0]+1)
                      for b in range(budget//costs[1]+1) if costs[0]*a+costs[1]*b<=budget)
        cost = costs[0]*data['a']+costs[1]*data['b']
        pieces = production[0]*data['a']+production[1]*data['b']
        return {'passed':data['a']>=0 and data['b']>=0 and cost<=budget and data['consommation']==cost
                and data['pieces']==pieces==optimum,'observed':data,'independent_optimum':optimum}
    if name=='csv-worker':
        from agi_core.mission_tools import strict_json
        data = strict_json((workspace/'summary.json').read_text(encoding='utf-8'))
        expected = {'rows':len(oracle['values']),'sum':sum(oracle['values'])}
        preserved = (workspace/'input.csv').read_bytes()==oracle['original']
        skills = (workspace/'.aurora/skills/AuditCSV/SKILL.md').is_file()
        worker = any(e['type']=='tool_result' and e.get('tool')=='spawn_agent' and e.get('ok')
                     and isinstance(e.get('result'),dict) and e['result'].get('agent')=='AuditCSV'
                     and e['result'].get('passed') and any(w.get('status')=='completed' for w in e['result'].get('workers',[])) for e in events)
        roles = any(e['type']=='tool_result' and e.get('tool')=='create_agent' and e.get('ok')
                    and isinstance(e.get('result'),dict) and e['result'].get('name')=='AuditCSV' for e in events)
        passed = isinstance(data,dict) and data==expected and all(type(v) is int for v in data.values())
        return {'passed':passed and preserved and bool(skills) and worker and roles,'observed':data,
                'input_preserved':preserved,'skill_created':bool(skills),'role_created':roles,'worker_completed':worker}
    if name=='code-repair':
        program = '''import copy,json,sys
sys.path.insert(0,sys.argv[1])
from solution import coverage
for intervals in json.loads(sys.stdin.read()):
    before=copy.deepcopy(intervals)
    if any(a>b for a,b in intervals):
        try: coverage(intervals)
        except ValueError: pass
        else: raise AssertionError('reversed interval accepted')
    else:
        expected=len({x for a,b in intervals for x in range(a,b)})
        assert coverage(intervals)==expected,(intervals,coverage(intervals),expected)
    assert intervals==before,'input modified'
print('independent_cases_passed')
'''
        result = subprocess.run([sys.executable,'-I','-c',program,str(workspace)],input=json.dumps(oracle['cases']),
                                cwd=workspace,text=True,capture_output=True,timeout=30)
        return {'passed':result.returncode==0,'cases':len(oracle['cases']),
                'stdout':result.stdout[-2000:],'stderr':result.stderr[-2000:]}
    raise ValueError(name)


async def evaluate(args):
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    os.environ['AURORA_DATA_DIR'] = str(output/'runtime-data')
    sys.path.insert(0,str(REPO))
    from agi_core.llm_gateway import LLMGateway
    from agi_core.mission_agent import AutonomousMissionAgent
    from agi_core.runtime_policy import model_options
    gateway = LLMGateway()
    if args.model not in await gateway.get_available_models():
        raise ValueError('Explicit evaluation model is not installed; no implicit fallback')
    files = ['agi_core/mission_agent.py','agi_core/mission_tools.py','agi_core/mission_protocol.py','agi_core/context.py',
             'scripts/evaluation/mission_regression.py']
    result = {'model':args.model,'seed':args.seed,'timeout_seconds':args.timeout,'options':model_options(),'python':platform.python_version(),
              'os':platform.platform(),'substituted_model':False,'agi_certification':False,
              'scope':'Local mission loop; these cases only, no bridge/tunnel/GPU media certification',
              'source_sha256':{p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in files},'cases':[]}
    names = ['optimizer','csv-worker','code-repair'] if args.case=='all' else [args.case]
    for name in names:
        case_seed = args.seed+['optimizer','csv-worker','code-repair'].index(name)
        prompt,fixtures,oracle = build_case(name,case_seed)
        workspace = output/name
        workspace.mkdir(mode=0o700)
        for path,content in fixtures.items():
            (workspace/path).write_bytes(content.encode('utf-8'))
        events = []
        agent = AutonomousMissionAgent('eval_'+uuid4().hex,prompt,str(workspace),args.model,'AUTONOMOUS')
        event_path = output/(name+'-events.jsonl')
        event_stream = event_path.open('x',encoding='utf-8')
        event_path.chmod(0o600)
        async def record(kind,data):
            events.append({'type':kind,**data})
            event_stream.write(json.dumps(events[-1],ensure_ascii=False)+'\n')
            if kind not in {'token','command_output'}:
                event_stream.flush()
        agent._emit = record
        started = time.monotonic()
        print('Starting '+name,flush=True)
        error = None
        try:
            await asyncio.wait_for(agent.run(),args.timeout)
        except asyncio.TimeoutError:
            error = 'Evaluation deadline exceeded; mission stopped with work preserved'
        except Exception as exc:
            error = type(exc).__name__+': '+str(exc)
        finally:
            event_stream.close()
        try:
            assessment = await asyncio.to_thread(grade_case,name,workspace,oracle,events)
        except Exception as exc:
            assessment = {'passed':False,'error':type(exc).__name__+': '+str(exc)}
        record = {'name':name,'seed':case_seed,'request':prompt,'elapsed_seconds':time.monotonic()-started,
                  'deadline_seconds':args.timeout,'iterations':agent.state['iteration'],
                  'plan':agent.state['plan'],'criteria':agent.state['criteria'],'verified':agent.state['verified'],
                  'required_tools':agent.state.get('required_tools',[]),'executed_tools':agent.state.get('executed_tools',[]),
                  'status':agent.state['status'],'error':error,'independent_assessment':assessment,
                  'passed':not error and agent.state['status']=='completed' and assessment['passed'],
                  'context_window':agent.state.get('context_window'),'metrics':[e for e in events if e['type']=='model_metrics']}
        result['cases'].append(record)
        (output/(name+'-events.json')).write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
        (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'{name}: passed={record["passed"]}, status={record["status"]}',flush=True)
    return 0 if all(c['passed'] for c in result['cases']) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,help='Explicit installed Ollama model')
    parser.add_argument('--output',type=Path,required=True,help='New private local output directory')
    parser.add_argument('--seed',type=int,default=secrets.randbits(32))
    parser.add_argument('--case',choices=['all','optimizer','csv-worker','code-repair'],default='all')
    parser.add_argument('--timeout',type=float,default=480,help='Seconds per real mission')
    args = parser.parse_args()
    if args.timeout<=0:
        parser.error('--timeout must be positive')
    try:
        return asyncio.run(evaluate(args))
    except (ValueError,OSError) as exc:
        parser.exit(2,str(exc)+'\n')


if __name__=='__main__':
    raise SystemExit(main())
