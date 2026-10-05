"""Seeded finite-rule induction; synthetic, not an official AGI benchmark.

The exact transformation and hidden expected outputs remain in evaluator memory
until grading. This is not an OS sandbox or a proof against host introspection.
"""
from __future__ import annotations
import json
import random
import subprocess
import sys


def transform(grid, turns, reflected, colors):
    """Coordinate-based oracle; learners receive examples, not these parameters."""
    source=[row[::-1] if reflected else row[:] for row in grid]
    for _ in range(turns):
        height,width=len(source),len(source[0])
        source=[[source[height-1-row][column] for row in range(height)] for column in range(width)]
    return [[colors[value] for value in row] for row in source]


def consistent_rules(examples):
    """Check that the finite stated family determines one rule from examples."""
    found=[]
    for turns in range(4):
        for reflected in (False,True):
            mapping={};valid=True
            for pair in examples:
                oriented=transform(pair['input'],turns,reflected,list(range(5)))
                expected=pair['output']
                if len(oriented)!=len(expected) or any(len(a)!=len(b) for a,b in zip(oriented,expected)):
                    valid=False;break
                for left,right in zip(oriented,expected):
                    for source,target in zip(left,right):
                        if source in mapping and mapping[source]!=target:valid=False
                        mapping[source]=target
            if valid and set(mapping)==set(range(5)) and len(set(mapping.values()))==5:
                found.append((turns,reflected,[mapping[v] for v in range(5)]))
    return found


def build_rule_discovery(seed):
    rng=random.Random(seed)
    turns=rng.randrange(4);reflected=bool(rng.randrange(2))
    colors=list(range(5));rng.shuffle(colors)
    def grid(height,width):return [[rng.randrange(5) for _ in range(width)] for _ in range(height)]
    for _ in range(64):
        train=[]
        for height,width in [(2,3),(4,5),(3,4)]:
            source=grid(height,width)
            train.append({'input':source,'output':transform(source,turns,reflected,colors)})
        if len(consistent_rules(train))==1:break
    else:raise ValueError('Could not generate uniquely identifiable finite-rule examples')
    public=[grid(rng.randint(1,7),rng.randint(1,7)) for _ in range(4)]
    hidden=[grid(rng.randint(1,7),rng.randint(1,7)) for _ in range(24)]
    # Keep the existing seeded cases; append bounded row/column and larger grids.
    hidden.extend(grid(height,width) for height,width in [(1,11),(13,1),(8,9),(9,8)])
    data={'palette':list(range(5)),'train':train,'test':public}
    content=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    prompt=("Lis examples.json et déduis la règle commune depuis les trois paires input/output. "
            "La famille est exactement : un éventuel miroir gauche-droite de chaque ligne, puis une rotation "
            "de 0, 90, 180 ou 270 degrés dans le sens horaire, puis une permutation bijective commune des couleurs 0 à 4. "
            "L'orientation et la permutation sont inconnues ; les exemples déterminent une règle unique dans cette famille. "
            "Écris solver.py avec solve(grid), fonction Python standard qui applique la règle déduite à toute grille "
            "rectangulaire non vide d'entiers de 0 à 4, sans modifier son entrée. "
            "Écris predictions.json avec exactement outputs, liste des grilles produites pour les entrées test dans leur ordre. "
            "Vérifie par Python les trois exemples, les prédictions sauvegardées et la non-mutation. "
            "Préserve les octets de examples.json. Ne remplace pas la règle par une table des seuls exemples.")
    oracle={'original':content.encode(),'public_outputs':[transform(g,turns,reflected,colors) for g in public],
            'hidden':[{'input':g,'output':transform(g,turns,reflected,colors)} for g in hidden],
            'rule':{'turns':turns,'reflected':reflected,'colors':colors},
            'scope':'Synthetic finite rotation/reflection/color-permutation rule induction, not official ARC/AGI certification'}
    return prompt,{'examples.json':content},oracle


def grade_rule_discovery(workspace, oracle):
    from agi_core.mission_tools import strict_json, same_json
    saved=strict_json((workspace/'predictions.json').read_text(encoding='utf-8'))
    predictions=same_json(saved,{'outputs':oracle['public_outputs']})
    solver_before=(workspace/'solver.py').read_bytes()
    examples=strict_json(oracle['original'].decode('utf-8'))
    groups={'train':examples['train'],
            'public':[{'input':grid,'output':output} for grid,output in zip(examples['test'],oracle['public_outputs'])],
            'hidden':oracle['hidden']}
    inputs=[case['input'] for cases in groups.values() for case in cases]
    program='''import json,sys
loads,dumps,emit=json.loads,json.dumps,print
inputs=loads(sys.stdin.read())
originals=[dumps(grid,allow_nan=False) for grid in inputs]
sys.path.insert(0,sys.argv[1])
from solver import solve
outputs=[]
preserved=[]
for grid,original in zip(inputs,originals):
    actual=solve(grid)
    assert isinstance(actual,list) and all(isinstance(row,list) and all(type(v) is int for v in row) for row in actual),"invalid grid types"
    preserved.append(dumps(grid,allow_nan=False)==original)
    outputs.append(loads(dumps(actual,allow_nan=False)))
emit("AURORA_SOLVER_OUTPUTS="+dumps({'outputs':outputs,'inputs_preserved':preserved},allow_nan=False))
'''
    result=subprocess.run([sys.executable,'-I','-c',program,str(workspace)],cwd=workspace,
                          input=json.dumps(inputs),text=True,capture_output=True,timeout=30)
    # Expected outputs never enter the learner process, even through stdin.
    passed_groups={name:False for name in groups}
    solver_inputs_preserved=False
    if result.returncode==0:
        lines=[line for line in result.stdout.splitlines() if line.startswith('AURORA_SOLVER_OUTPUTS=')]
        if lines:
            try:
                actual=strict_json(lines[-1].removeprefix('AURORA_SOLVER_OUTPUTS='))
                if isinstance(actual,dict) and set(actual)=={'outputs','inputs_preserved'} and isinstance(actual['outputs'],list) and len(actual['outputs'])==len(inputs):
                    solver_inputs_preserved=same_json(actual['inputs_preserved'],[True]*len(inputs))
                    offset=0
                    for name,cases in groups.items():
                        passed_groups[name]=same_json(actual['outputs'][offset:offset+len(cases)],
                                                      [case['output'] for case in cases])
                        offset+=len(cases)
            except ValueError:
                pass
    # Imported solver code must not make a formerly checked delivery stale.
    preserved=(workspace/'examples.json').read_bytes()==oracle['original']
    current=strict_json((workspace/'predictions.json').read_text(encoding='utf-8'))
    predictions=bool(predictions and same_json(current,{'outputs':oracle['public_outputs']}))
    source_unchanged=(workspace/'solver.py').read_bytes()==solver_before
    return {'passed':bool(predictions and preserved and source_unchanged and solver_inputs_preserved and all(passed_groups.values())),
            'public_predictions_correct':predictions,'input_preserved':preserved,
            'train_cases':len(groups['train']),'train_cases_passed':passed_groups['train'],
            'public_cases':len(groups['public']),'public_cases_passed':passed_groups['public'],
            'hidden_cases':len(groups['hidden']),'hidden_cases_passed':passed_groups['hidden'],
            'solver_inputs_preserved':solver_inputs_preserved,
            'solver_preserved_during_grading':source_unchanged,
            'stdout':result.stdout[-2000:],'stderr':result.stderr[-2000:],'scope':oracle['scope']}
