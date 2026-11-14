"""Synthetic, reproducible tasks with executable oracles and reserved task families.

No model-generated reference is executed on the host. The functions below are
trusted exercise generators; candidate programs run in the existing sandbox.
"""
from __future__ import annotations
import copy
import csv
import heapq
import io
import ipaddress
import json
import random
import re
import unicodedata
from collections import OrderedDict, defaultdict
from .storage import digest


def merge_intervals(xs):
    result = []
    for a, b in sorted(xs):
        if result and a <= result[-1][1]:
            result[-1][1] = max(b, result[-1][1])
        else:
            result.append([a, b])
    return result


def shortest_paths(data):
    n, edges, start = data['n'], data['edges'], data['start']
    dist = [float('inf')] * n
    dist[start] = 0
    # Bellman-Ford oracle, independent of the Dijkstra solution usually generated.
    for _ in range(n - 1):
        changed = False
        for a, b, w in edges:
            if dist[a] + w < dist[b]:
                dist[b] = dist[a] + w
                changed = True
        if not changed:
            break
    return [None if x == float('inf') else x for x in dist]


def topo(data):
    n, edges = data['n'], {tuple(e) for e in data['edges']}
    done, result = set(), []
    while len(done) < n:
        ready = [x for x in range(n) if x not in done and all(a in done for a, b in edges if b == x)]
        if not ready:
            return []
        x = min(ready)
        done.add(x)
        result.append(x)
    return result


def lru(data):
    cache, evicted = OrderedDict(), []
    for key in data['accesses']:
        if key in cache:
            cache.move_to_end(key)
        elif data['capacity'] > 0:
            cache[key] = True
            if len(cache) > data['capacity']:
                evicted.append(cache.popitem(last=False)[0])
    return {'cache': list(cache), 'evicted': evicted}


def windows(data):
    xs, k = data['values'], data['k']
    if k < 1 or k > len(xs):
        return []
    return [max(xs[i:i+k]) for i in range(len(xs)-k+1)]


def csv_totals(text):
    totals = defaultdict(int)
    for row in csv.DictReader(io.StringIO(text)):
        totals[row['account']] += int(row['cents'])
    return dict(sorted(totals.items()))


def cidr(data):
    nets = [ipaddress.ip_network(n, strict=False) for n in data['networks']]
    result = []
    for address in data['addresses']:
        try:
            ip = ipaddress.ip_address(address)
            result.append(any(ip.version == net.version and ip in net for net in nets))
        except ValueError:
            result.append(False)
    return result


def log_totals(rows):
    totals, seen = defaultdict(int), set()
    for row in rows:
        if row['id'] in seen:
            continue
        seen.add(row['id'])
        if row['level'] == 'ERROR':
            totals[row['service']] += 1
    return dict(sorted(totals.items()))


def flatten(data):
    result = {}
    def walk(node, path):
        if isinstance(node, dict) and node:
            for k, v in sorted(node.items()):
                walk(v, path + '/' + k.replace('~', '~0').replace('/', '~1'))
        elif isinstance(node, list) and node:
            for i, v in enumerate(node):
                walk(v, path + '/' + str(i))
        else:
            result[path] = node
    walk(data, '')
    return result


def edit_distance(data):
    a, b = [unicodedata.normalize('NFC', s) for s in data]
    row = list(range(len(b)+1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(new[-1]+1, row[j]+1, row[j-1]+(x != y)))
        row = new
    return row[-1]


def weighted_intervals(jobs):
    if len(jobs)>16:
        # Large stress cases use an exact dynamic program. The small exhaustive
        # oracle remains available to cross-check this implementation in tests.
        from bisect import bisect_right
        jobs=sorted(jobs,key=lambda j:j[1]);ends=[j[1] for j in jobs];best=[0]
        for i,(start,end,value) in enumerate(jobs):
            previous=bisect_right(ends,start,0,i)
            best.append(max(best[-1],best[previous]+value))
        return best[-1]
    # Exhaustive oracle on small synthetic sets.
    best=0
    for mask in range(1 << len(jobs)):
        subset=sorted(j for i,j in enumerate(jobs) if mask & (1 << i))
        if all(a[1] <= b[0] for a,b in zip(subset,subset[1:])):
            best=max(best,sum(j[2] for j in subset))
    return best


def inversion_count(values):
    return sum(a>b for i,a in enumerate(values) for b in values[i+1:])


def components(data):
    groups=[{i} for i in range(data['n'])]
    for a,b in data['edges']:
        selected=[g for g in groups if a in g or b in g]
        groups=[g for g in groups if g not in selected]+[set().union(*selected)]
    return sorted(sorted(g) for g in groups)


def word_counts(text):
    words=re.findall(r"[^\W\d_]+",unicodedata.normalize('NFC',text).casefold())
    return {w:words.count(w) for w in sorted(set(words))}


def permissions(rows):
    return [''.join(char if mode & bit else '-' for bit,char in zip([256,128,64,32,16,8,4,2,1],'rwxrwxrwx')) for mode in rows]


def decimal_round(rows):
    from decimal import Decimal,ROUND_HALF_EVEN
    return [int((Decimal(x)*100).quantize(Decimal('1'),rounding=ROUND_HALF_EVEN)) for x in rows]


def sliding_limit(data):
    accepted=[];result=[]
    for t in data['times']:
        good=sum(t-data['window'] < x <= t for x in accepted)<data['limit']
        result.append(good)
        if good:accepted.append(t)
    return result


def closure(data):
    n=data['n'];reachable=[[False]*n for _ in range(n)]
    for a,b in data['edges']:reachable[a][b]=True
    for k in range(n):
        for i in range(n):
            for j in range(n):reachable[i][j] |= reachable[i][k] and reachable[k][j]
    return [[j for j in range(n) if reachable[i][j]] for i in range(n)]


def business_waterfall_oracle(data):
    gross = int(data['gross_cents'])
    direct = int(data['direct_cost_cents'])
    cac = int(data['cac_cents'])
    fixed = int(data['fixed_cost_cents'])
    yield_bps = int(data['reserve_yield_bps'])
    dso_lag = int(data['dso_lag_cents'])
    tax_bps = int(data['tax_bps'])
    ebitda = gross - direct - cac - fixed
    reserve_gain = (max(0, ebitda) * yield_bps) // 10000
    pre_tax = ebitda + reserve_gain - dso_lag
    tax = (max(0, pre_tax) * tax_bps) // 10000
    net_pocket = pre_tax - tax
    risk_ok = (gross > 0) and (net_pocket * 4 >= gross) and (dso_lag * 5 <= gross)
    return {'ebitda_cents': ebitda, 'net_pocket_cents': net_pocket, 'risk_approved': bool(risk_ok)}


def cyber_alloc_guard_oracle(data):
    count = int(data['count'])
    stride = int(data['stride'])
    header = int(data['header'])
    limit = int(data['max_bytes'])
    if count < 0 or stride < 0 or header < 0:
        return {'overflow': True, 'safe_bytes': None}
    total = count * stride + header
    overflow = (total > 0xFFFFFFFF) or (total > limit)
    if overflow:
        return {'overflow': True, 'safe_bytes': None}
    aligned = ((total + 15) // 16) * 16
    if aligned > 0xFFFFFFFF or aligned > limit:
        return {'overflow': True, 'safe_bytes': None}
    return {'overflow': False, 'safe_bytes': aligned}


def os_vfs_canonical_oracle(data):
    raw = str(data['path'])
    stack = []
    escaped = False
    for part in raw.split('/'):
        if not part or part == '.':
            continue
        if part == '..':
            if not stack:
                escaped = True
            else:
                stack.pop()
        else:
            stack.append(part)
    return {'escaped': escaped, 'canonical': '/' + '/'.join(stack)}


def os_aging_scheduler_oracle(data):
    aging = int(data['aging_factor'])
    procs = list(data['processes'])
    ranked = sorted(
        procs,
        key=lambda p: (-(int(p['base_priority']) + int(p['wait_ticks']) * aging), int(p['pid'])),
    )
    return [int(p['pid']) for p in ranked]


BASE_SPECS = [
 ('scheduling', 'Input is jobs [start,end,value] with start<end. Select non-overlapping jobs of maximum total value. Touching endpoints are allowed; return the maximum value. Choosing no jobs is allowed.', weighted_intervals),
 ('inversions', 'Return the number of pairs i<j with values[i]>values[j]. Equal values are not inversions. Support negatives, duplicates and empty input.', inversion_count),
 ('components', 'Input has n nodes 0..n-1 and undirected edges. Return connected components as sorted lists, with the outer list lexicographically sorted. Keep isolated nodes. Duplicate edges and self-loops are allowed.', components),
 ('words', 'Normalize text to Unicode NFC, then casefold. Extract maximal sequences of Unicode letters, excluding digits and underscore. Return counts per resulting word. Punctuation separates words.', word_counts),
 ('permissions', 'Input is integer POSIX modes in 0..511. Return corresponding nine-character rwxrwxrwx permission strings in order, replacing absent bits by -. Do not include a file-type prefix.', permissions),
 ('decimal', 'Input is decimal currency strings. Return integer cents rounded to nearest cent with exact decimal arithmetic and ties to even. Support negative amounts; avoid binary floating point.', decimal_round),
 ('rate_limit', 'Input has nondecreasing times, positive window and integer limit>=0. Accept each event if fewer than limit previously accepted events lie in (t-window,t]. Rejected events do not count. Return booleans in input order.', sliding_limit),
 ('reachability', 'Input has n nodes 0..n-1 and directed edges. Return sorted nodes reachable from each node by a path of at least one edge. A node reaches itself only through a cycle or self-loop.', closure),
 ('intervals', 'Merge closed integer intervals, including touching endpoints; sort the result; preserve no duplicates. Empty input gives [].', merge_intervals),
 ('routes', 'Input has n nodes 0..n-1, directed edges [a,b,nonnegative_weight], start. Return shortest distance to each node; unreachable is null. Handle zero-weight edges, cycles and parallel edges.', shortest_paths),
 ('dependencies', 'Input has n tasks 0..n-1 and directed prerequisite edges [a,b]. Return the lexicographically smallest topological ordering. Ignore duplicate edges. Return [] for any cycle.', topo),
 ('cache', 'Simulate LRU with capacity and accesses. A hit moves its key to most recently used. Return {cache: keys oldest-first, evicted: evicted keys in order}. Capacity zero stores nothing and evicts nothing.', lru),
 ('windows', 'Input has integer values and k. Return the maximum of each contiguous window of k values. Return [] when k<1 or k exceeds length. Handle negative numbers and duplicate maxima.', windows),
 ('csv', 'Parse an RFC4180 CSV string with header account,cents. Sum signed integer cents per account and return an object. Quoted names can contain commas and newlines. Never use floating point for money.', csv_totals),
 ('network', 'Input contains networks (IPv4/IPv6 CIDRs, host bits allowed) and addresses. Return a boolean per address for membership in any same-version network. Invalid addresses are false; include network/broadcast boundaries.', cidr),
 ('logs', 'Input is event objects with id,level,service. Deduplicate by id keeping the FIRST occurrence, then count exact level ERROR per service. Return only services with errors. Input order is authoritative.', log_totals),
 ('json_paths', 'Flatten arbitrary JSON using RFC6901 JSON Pointer paths. Escape ~ as ~0 and / as ~1. Index lists from zero. Keep empty lists, empty objects, null and scalar leaves. Root leaf path is the empty string.', flatten),
 ('unicode', 'Input is a pair of strings. Normalize each to Unicode NFC then return Levenshtein distance with unit insert/delete/substitute cost, over Unicode code points. Matching case matters.', edit_distance),
]

EXTRA_DEEP_SPECS = [
 ('business_waterfall', 'Compute the 8-step financial waterfall in integer cents: ebitda_cents = gross_cents - direct_cost_cents - cac_cents - fixed_cost_cents; reserve_gain = (max(0, ebitda_cents) * reserve_yield_bps) // 10000; pre_tax = ebitda_cents + reserve_gain - dso_lag_cents; tax = (max(0, pre_tax) * tax_bps) // 10000; net_pocket_cents = pre_tax - tax; risk_approved = (gross_cents > 0) and (net_pocket_cents * 4 >= gross_cents) and (dso_lag_cents * 5 <= gross_cents). Return {"ebitda_cents": int, "net_pocket_cents": int, "risk_approved": bool}.', business_waterfall_oracle),
 ('cyber_alloc_guard', 'Check 32-bit unsigned allocator arithmetic total = count * stride + header against 0xFFFFFFFF and max_bytes. If count, stride or header is negative, or total exceeds 0xFFFFFFFF or max_bytes, return {"overflow": True, "safe_bytes": None}. Otherwise round total up to the next multiple of 16: aligned = ((total + 15) // 16) * 16; if aligned exceeds 0xFFFFFFFF or max_bytes return {"overflow": True, "safe_bytes": None}, else return {"overflow": False, "safe_bytes": aligned}.', cyber_alloc_guard_oracle),
 ('os_vfs_canonical', 'Resolve a POSIX VFS path by splitting on "/", ignoring empty and "." segments, popping the current stack on "..", and setting escaped=True if ".." occurs when the stack is empty (still continuing resolution of remaining segments). Return {"escaped": bool, "canonical": "/" + "/".join(stack)}.', os_vfs_canonical_oracle),
 ('os_aging_scheduler', 'Schedule processes without starvation using effective priority = base_priority + wait_ticks * aging_factor. Return the list of integer pids sorted by effective priority descending, breaking ties by pid ascending.', os_aging_scheduler_oracle),
]

SPECS = BASE_SPECS + EXTRA_DEEP_SPECS

# The key names and container types are part of the task, never guessed by the
# candidate. These contracts describe inputs without exposing evaluation cases.
INPUT_CONTRACTS = {
    'scheduling': 'data is a list of [start, end, value] lists.',
    'inversions': 'data is a list of integers.',
    'components': 'data is a dict with exactly keys "n" (integer) and "edges" (list of [u, v] lists). Read the node count as data["n"].',
    'words': 'data is one string.',
    'permissions': 'data is a list of integers.',
    'decimal': 'data is a list of decimal strings.',
    'rate_limit': 'data is a dict with keys "times" (list of numbers), "window" (number), "limit" (integer).',
    'reachability': 'data is a dict with keys "n" (integer) and "edges" (list of [u, v] lists).',
    'intervals': 'data is a list of [start, end] lists.',
    'routes': 'data is a dict with keys "n" (integer), "edges" (list of [u, v, weight] lists), "start" (integer).',
    'dependencies': 'data is a dict with keys "n" (integer) and "edges" (list of [a, b] lists).',
    'cache': 'data is a dict with keys "capacity" (integer) and "accesses" (list of strings).',
    'windows': 'data is a dict with keys "values" (list of integers) and "k" (integer).',
    'csv': 'data is one string containing CSV text, including its header.',
    'network': 'data is a dict with keys "networks" (list of CIDR strings) and "addresses" (list of address strings).',
    'logs': 'data is a list of dicts, each with keys "id", "level", "service" (strings).',
    'json_paths': 'data is any JSON value: dict, list, string, number, boolean or null.',
    'unicode': 'data is a list of exactly two strings.',
    'business_waterfall': 'data is a dict with integer keys "gross_cents", "direct_cost_cents", "cac_cents", "fixed_cost_cents", "reserve_yield_bps", "dso_lag_cents", "tax_bps".',
    'cyber_alloc_guard': 'data is a dict with integer keys "count", "stride", "header", "max_bytes".',
    'os_vfs_canonical': 'data is a dict with string key "path".',
    'os_aging_scheduler': 'data is a dict with integer key "aging_factor" and list key "processes" (each dict has integer keys "pid", "base_priority", "wait_ticks").',
}


def inputs(family, rng):
    if family == 'scheduling':
        return [[[a,a+rng.randrange(1,5),rng.randrange(-5,30)] for a in rng.choices(range(10),k=n)] for n in range(10)]
    if family == 'inversions':
        return [rng.choices(range(-5,6),k=n*3) for n in range(12)]
    if family in {'components','reachability'}:
        return [{'n':n,'edges':[[rng.randrange(n),rng.randrange(n)] for _ in range(n*2)]} for n in range(1,13)]
    if family == 'words':
        return ['', 'CAFÉ cafe\u0301', 'Straße STRASSE', 'a_b 12c3', 'été—hiver', '🙂 chien! CHIEN', '東京 東京', 'naïve naïve', 'un,deux;trois']
    if family == 'permissions':
        return [[],[0],[511],[493,420],[1,2,4],[8,16,32],[64,128,256]]+[rng.choices(range(512),k=9) for _ in range(4)]
    if family == 'decimal':
        return [[],['0'],['1.005','1.015'],['-1.005','-1.015'],['999999999.995'],['0.009','-0.001'],['12.5','1e2'],['.005','.015']]
    if family == 'rate_limit':
        return [{'times':sorted(rng.choices(range(20),k=n*3)),'window':rng.randrange(1,8),'limit':n % 4} for n in range(12)]
    if family == 'intervals':
        return [[], [[1,2]], [[1,3],[3,5]], [[-8,-2],[-4,0]], [[2,2],[2,2]], [[0,10],[2,3]], [[9,10],[1,2]]] + [sorted([sorted(rng.sample(range(-50,51),2)) for _ in range(12)]) for _ in range(5)]
    if family in {'routes','dependencies'}:
        examples = []
        for i in range(12):
            n = 2 + i
            edges = [[rng.randrange(n),rng.randrange(n)] for _ in range(i*2)]
            if family == 'routes':
                edges = [e+[rng.randrange(8)] for e in edges]
            examples.append({'n':n, 'edges':edges, **({'start':i % n} if family=='routes' else {})})
        return examples
    if family == 'cache':
        return [{'capacity':k,'accesses':rng.choices(['a','b','c','d','x'], k=i*3)} for i,k in enumerate([0,1,2,3,0,2,1,4,2,3,1,4])]
    if family == 'windows':
        return [{'values':rng.choices(range(-10,11),k=i),'k':k} for i,k in enumerate([0,1,2,4,-1,2,3,1,8,3,5,4])]
    if family == 'csv':
        result=[]
        for n in range(12):
            output=io.StringIO(); w=csv.writer(output); w.writerow(['account','cents'])
            for _ in range(n): w.writerow([rng.choice(['a','b','c,d','two\nlines','épargne']),rng.randrange(-500000,500000)])
            result.append(output.getvalue())
        return result
    if family == 'network':
        return [{'networks':nets,'addresses':['10.0.0.0','10.255.255.255','11.0.0.0','::1','2001:db8::1','invalid','127.0.0.1','192.168.1.255']}
                for nets in [[],['10.0.0.1/8'],['::/0'],['0.0.0.0/0'],['::1/128'],['192.168.1.17/24'],['2001:db8::/32'],['10.0.0.0/8','::/0']]]
    if family == 'logs':
        return [[{'id':str(rng.randrange(5)), 'level':rng.choice(['ERROR','error','INFO']), 'service':rng.choice(['api','worker','db'])} for _ in range(n*3)] for n in range(12)]
    if family == 'json_paths':
        return [None,{},[],[1,None],{'a/b':{'~':3}},{'':{'':False}}, {'a':[{'b':[]},{}]}, {'é':'été'},0,{'/':{'~':[1,2]}},True,{'x':{'y':{'z':1}}}]
    if family == 'business_waterfall':
        return [
            {'gross_cents': 100000 * (i + 1), 'direct_cost_cents': 22000 * (i + 1), 'cac_cents': 11000 * (i + 1),
             'fixed_cost_cents': 15000, 'reserve_yield_bps': 350, 'dso_lag_cents': 8000 * (i % 4), 'tax_bps': 2500}
            for i in range(12)
        ]
    if family == 'cyber_alloc_guard':
        return [
            {'count': 0, 'stride': 64, 'header': 32, 'max_bytes': 4096},
            {'count': 65536, 'stride': 65536, 'header': 16, 'max_bytes': 0xFFFFFFFF},
            {'count': -1, 'stride': 16, 'header': 8, 'max_bytes': 1024},
            {'count': 15, 'stride': 17, 'header': 9, 'max_bytes': 512},
            {'count': 1024, 'stride': 4, 'header': 0, 'max_bytes': 4096},
            {'count': 1024, 'stride': 4, 'header': 1, 'max_bytes': 4096},
            {'count': 0x10000000, 'stride': 16, 'header': 0, 'max_bytes': 0xFFFFFFFF},
            {'count': 7, 'stride': 3, 'header': 5, 'max_bytes': 32},
        ]
    if family == 'os_vfs_canonical':
        return [
            {'path': '/home/aurora/./projets/../code//kernel.py'},
            {'path': '/../../etc/passwd'},
            {'path': '/a/b/c/../../d/./e/'},
            {'path': '/'},
            {'path': '///var//log/../cache/./app'},
            {'path': '/usr/local/../../../root'},
            {'path': 'relative/./sub/../file.txt'},
            {'path': '/home/user/..'},
        ]
    if family == 'os_aging_scheduler':
        return [
            {'aging_factor': 2, 'processes': [
                {'pid': 10, 'base_priority': 5, 'wait_ticks': 10},
                {'pid': 4, 'base_priority': 15, 'wait_ticks': 5},
                {'pid': 7, 'base_priority': 20, 'wait_ticks': 0},
            ]},
            {'aging_factor': 3, 'processes': [
                {'pid': i + 1, 'base_priority': (i * 7) % 13, 'wait_ticks': (12 - i) * 2}
                for i in range(8)
            ]},
            {'aging_factor': 1, 'processes': []},
            {'aging_factor': 5, 'processes': [
                {'pid': 2, 'base_priority': 10, 'wait_ticks': 4},
                {'pid': 1, 'base_priority': 10, 'wait_ticks': 4},
            ]},
            {'aging_factor': 4, 'processes': [
                {'pid': k, 'base_priority': rng.randrange(1, 20), 'wait_ticks': rng.randrange(0, 15)}
                for k in range(1, 7)
            ]},
            {'aging_factor': 2, 'processes': [
                {'pid': k, 'base_priority': rng.randrange(1, 20), 'wait_ticks': rng.randrange(0, 15)}
                for k in range(1, 9)
            ]},
        ]
    return [['',''],['','abc'],['kitten','sitting'],['café','cafe\u0301'],['é','e'],['🙂','🙃'],['A','a'],['naïve','naive'],['abc','xyz'],['résumé','resume'],['ab','ba'],['a'*50,'b'*50]]


def build_tasks(c):
    _mod_offsets = {'code':0,'conversation':1009,'cyber':2017,'cowork':3019,'business':4027,'simulator':5039}
    rng = random.Random(c['seed'] + _mod_offsets.get(c['module'],0))
    families = list(BASE_SPECS)
    partition_rng=(random.Random(c['audit_partition_seed'] + _mod_offsets.get(c['module'],0))
                   if 'audit_partition_seed' in c else rng)
    partition_rng.shuffle(families)
    # Whole problem families are reserved, including when many variants are used.
    # Audit families remain strictly identical to the 8 reserved base families,
    # while training families integrate the new multi-regime deep oracle tasks.
    train_families = list(EXTRA_DEEP_SPECS) + families[:-8]
    audit_families = families[-8:]
    result = []
    for split, count, pool in [('train',c['train_tasks'],train_families),('audit',c['eval_tasks'],audit_families)]:
        for i in range(count):
            family, description, oracle = pool[i % len(pool)]
            values = inputs(family, rng)
            if c.get('curriculum_version') in {'radical-v2','radical-v3'}:
                from .challenge_curriculum import harder_inputs
                values=harder_inputs(family,values,rng)
            task = {'id': f'{split}_{family}_{i:03d}', 'family':family, 'split':split,
                    'origin':'synthetic_verified_oracle', 'function':'solve',
                    'prompt':'Implement Python function solve(data). data is an already decoded JSON value: arrays are Python lists, objects are dicts with the stated keys. Do not read stdin. Return a JSON-serializable value, not printed text. Only parse text if the input itself is explicitly described as a string. Input contract: '+INPUT_CONTRACTS[family]+' Required behavior: '+description,
                    'cases':[{'args':[v]} for v in values],
                    'expected':[oracle(copy.deepcopy(v)) for v in values]}
            if c.get('curriculum_version') in {'radical-v2','radical-v3'}:
                focus=['nested cases and exact boundary semantics','larger inputs with duplicates and adversarial ordering',
                       'Unicode, empty cases and numerical precision'][i%3]
                task.update(difficulty=['complex','stress','edge_cases'][i%3],suite_version=c.get('curriculum_version','radical-v3'))
                task['prompt']+=' Validation focus for this brief: '+focus+'. Preserve every rule above and do not hard-code examples.'
            if c['module'] == 'conversation':
                # Exact structured reasoning, explicitly narrower than general dialogue.
                samples = ([values[j] for j in sorted(set([1,2,len(values)//3,len(values)//2,len(values)-2,len(values)-1]))]
                           if c.get('curriculum_version') in {'radical-v2','radical-v3'} else [values[1],values[len(values)//2],values[-1]])
                task.update(prompt='Réponds uniquement avec un objet JSON {"answers": [resultat_1, resultat_2, resultat_3]} contenant les trois résultats complets dans l’ordre. Chaque entrée est déjà une valeur JSON : objet, tableau ou chaîne, selon la règle. Respecte exactement les types de sortie demandés ; ne renvoie pas uniquement des noms de clés ou des indices. Règle : '+description+'\nEntrées : '+json.dumps(samples,ensure_ascii=False),
                            expected_json={'answers':[oracle(copy.deepcopy(v)) for v in samples]})
                if c.get('curriculum_version') in {'radical-v2','radical-v3'}:
                    task['prompt']=task['prompt'].replace('resultat_1, resultat_2, resultat_3','un résultat par entrée').replace('les trois résultats complets','tous les résultats complets')
            result.append(task)
    validate_tasks(result,c)
    return result


def validate_tasks(tasks,c):
    n=c['train_tasks']
    if len(tasks) < n+c['eval_tasks']:
        raise ValueError('Pas assez de sujets indépendants pour apprentissage et audit')
    ids=[t['id'] for t in tasks]
    if len(set(ids)) != len(ids):
        raise ValueError('Identifiants de sujets dupliqués')
    signatures=[]
    for t in tasks:
        signature={'prompt':' '.join(t['prompt'].split()).casefold()}
        if t.get('image'):
            from pathlib import Path
            from .storage import file_hash
            img_p = Path(t['image'])
            if not img_p.exists() and c.get('state_dir'):
                relocated = Path(c['state_dir']) / 'radical_references' / img_p.parent.name / img_p.name
                if relocated.exists():
                    t['image'] = str(relocated)
            signature={'image':file_hash(t['image'])}
        signatures.append(digest(signature))
    if set(signatures[:n]) & set(signatures[n:]):
        raise ValueError('Fuite de données : même sujet dans apprentissage et audit')
    families=lambda xs:{t['family'] for t in xs if t.get('family')}
    if families(tasks[:n]) & families(tasks[n:]):
        raise ValueError('Une famille de problèmes traverse la séparation apprentissage/audit')
    return tasks
