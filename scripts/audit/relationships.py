import argparse
import collections
import csv
import json
from pathlib import Path, PurePosixPath


def components(graph):
    index = 0
    indices, low = {}, {}
    stack, active, groups = [], set(), []

    def visit(node):
        nonlocal index
        indices[node] = low[node] = index
        index += 1
        stack.append(node)
        active.add(node)
        for target in sorted(graph.get(node, [])):
            if target not in indices:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in active:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            group = []
            while True:
                target = stack.pop()
                active.remove(target)
                group.append(target)
                if target == node:
                    break
            if len(group) > 1 or node in graph.get(node, []):
                groups.append(sorted(group))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(groups, key=lambda group: (-len(group), group))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inventory', type=Path)
    args = parser.parse_args()
    inventories = [json.loads((args.inventory / name).read_text())
                   for name in ['AuroraIA.json', 'aurora-remote-cli.json', 'typescript.json']]
    files = {record['file'] for data in inventories for record in data.get('files', [])}
    units = [unit for data in inventories for unit in data['units']]
    graph = collections.defaultdict(set)
    dependencies, unresolved = [], []
    roots = ['AuroraIA', 'AuroraIA/application', 'AuroraIA/application/python-services', 'aurora-remote-cli']
    for data in inventories:
        for entry in data['imports']:
            candidates = []
            if 'target' in entry:
                if entry['target']:
                    candidates.append(entry['target'])
            else:
                module = entry['module']
                if module.startswith('.'):
                    level = len(module) - len(module.lstrip('.'))
                    parent = PurePosixPath(entry['file']).parent
                    for _ in range(level - 1):
                        parent = parent.parent
                    prefixes = [str(parent / module.lstrip('.').replace('.', '/'))]
                else:
                    prefixes = [root + '/' + module.replace('.', '/') for root in roots]
                candidates = sorted({candidate for prefix in prefixes
                                     for candidate in [prefix + '.py', prefix + '/__init__.py'] if candidate in files})
            if len(candidates) == 1:
                target = candidates[0]
                graph[entry['file']].add(target)
                dependencies.append({**entry, 'target': target})
            else:
                unresolved.append({**entry, 'candidates': candidates})
    result = {'dependencies': dependencies, 'unresolved_or_external': unresolved, 'cycles': components(graph),
              'scope': 'Static file dependencies; dynamic imports and runtime dispatch are not resolved.'}
    (args.inventory / 'dependencies.json').write_text(json.dumps(result, indent=2) + '\n')
    with (args.inventory / 'units.csv').open('w', newline='') as stream:
        fields = ['module', 'file', 'name', 'line', 'end', 'public', 'language', 'review']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for unit in sorted(units, key=lambda row: (row['file'], row['line'])):
            writer.writerow({'module': str(PurePosixPath(unit['file']).parent), **unit})
    print(json.dumps({'units': len(units), 'public_units': sum(unit['public'] for unit in units),
                      'dependencies': len(dependencies), 'unresolved_or_external': len(unresolved),
                      'cycle_components': len(result['cycles']), 'largest_cycles': result['cycles'][:3]}, indent=2))


if __name__ == '__main__':
    main()
