#!/usr/bin/env python3
"""Inventory published/indexed code without importing it or reading local secrets.

The main repository is read from its Git index, so unrelated unstaged drafts
are excluded. Neighbour repositories use origin/main when available, otherwise
HEAD. Presence and static declarations never imply runtime readiness or quality.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
DESTINATION=ROOT/'scripts/documentation/architecture_catalog.json'
SUFFIXES={'.py','.ts','.tsx','.js','.mjs','.cjs','.rs','.sh','.html','.css','.scss','.toml','.yml','.yaml','.json','.c','.cpp','.h','.cu'}
EXCLUDE_PREFIXES=('.secrets/','.aurora/','modele/','models/','node_modules/','application/node_modules/',
                  'application/output/','application/.transfer_to_client/','application/.venv/',
                  'application/dist/','application/src-tauri/target/','db_vector/')


def indexed_sources(root, ref=None):
    command=['git','ls-tree','-r','-z',ref] if ref else ['git','ls-files','--stage','-z']
    output=subprocess.check_output(command,cwd=root).split(b'\0');objects=[]
    for entry in output:
        if not entry:continue
        metadata,name=entry.split(b'\t',1);fields=metadata.split();path=name.decode('utf-8')
        mode=fields[0].decode();oid=fields[2 if ref else 1].decode()
        if mode not in {'100644','100755'} or Path(path).suffix not in SUFFIXES or path.startswith(EXCLUDE_PREFIXES) or path=='scripts/documentation/architecture_catalog.json':continue
        if not ref and fields[2]!=b'0':raise ValueError('Resolve Git index conflicts before cataloguing sources')
        objects.append((path,oid))
    # One Git process, not one subprocess per source. Only blob bytes are read.
    process=subprocess.Popen(['git','cat-file','--batch'],cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        for path,oid in sorted(objects):
            process.stdin.write((oid+'\n').encode());process.stdin.flush()
            header=process.stdout.readline().split();size=int(header[2]);data=process.stdout.read(size)
            if len(data)!=size or process.stdout.read(1)!=b'\n':raise ValueError('Incomplete Git blob stream')
            yield path,data
    finally:
        process.stdin.close();process.stdout.close();process.wait(timeout=10)


def python_routes(data):
    try:tree=ast.parse(data.decode('utf-8-sig'))
    except (UnicodeError,SyntaxError):return [],'not_parsed'
    routes=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
        for decorator in node.decorator_list:
            if not isinstance(decorator,ast.Call) or not isinstance(decorator.func,ast.Attribute) or not decorator.args:continue
            verb=decorator.func.attr
            if verb not in {'route','get','post','put','delete','patch','head','options'}:continue
            try:path=ast.literal_eval(decorator.args[0])
            except (ValueError,TypeError):continue
            if not isinstance(path,str) or not path.startswith('/'):continue
            methods=['GET'] if verb=='route' else [verb.upper()]
            for keyword in decorator.keywords:
                if keyword.arg=='methods':
                    try:methods=list(ast.literal_eval(keyword.value))
                    except (ValueError,TypeError):methods=['DYNAMIC']
            routes.append({'path':path,'methods':methods,'handler':node.name,'line':node.lineno})
    return routes,'static_decorators_only'


def build_catalog():
    files=[];repositories={}
    for name,root in [('AuroraIA',ROOT),('aurora-remote-cli',ROOT.parent/'aurora-remote-cli'),('aurora-live',ROOT.parent/'aurora-live')]:
        if not (root/'.git').exists():continue
        ref=None
        if name!='AuroraIA':
            probe=subprocess.run(['git','rev-parse','--verify','origin/main'],cwd=root,capture_output=True,text=True)
            ref='origin/main' if probe.returncode==0 else 'HEAD'
        repositories[name]={'source':ref or 'git-index','working_tree_drafts_included':False}
        for path,data in indexed_sources(root,ref):
            record={'repo':name,'path':path,'sha256':hashlib.sha256(data).hexdigest(),'lines':data.count(b'\n')}
            if path.endswith('.py'):
                record['http_routes'],record['route_analysis']=python_routes(data)
            files.append(record)
    return {'schema':'aurora.architecture-catalog.v1','scope':'Static indexed sources and literal Python route decorators; no imports, runtime calls, weights, secrets, generated results or unstaged drafts.',
            'repositories':repositories,'source_files':len(files),'source_lines':sum(f['lines'] for f in files),
            'static_route_declarations':sum(len(f.get('http_routes',[])) for f in files),
            'by_repository':dict(Counter(f['repo'] for f in files)),'files':files}


def check_catalog(current=None):
    current=current or build_catalog()
    previous=json.loads(DESTINATION.read_text(encoding='utf-8'))
    available=set(current['repositories'])
    expected={(f['repo'],f['path']):f['sha256'] for f in previous['files'] if f['repo'] in available}
    actual={(f['repo'],f['path']):f['sha256'] for f in current['files']}
    changes=[key for key in sorted(expected.keys()|actual.keys()) if expected.get(key)!=actual.get(key)]
    if changes:
        for repo,path in changes:print('Source added, removed or changed: '+repo+'/'+path)
        return 1
    print('Catalog matches %d indexed sources; unavailable neighbour repositories skipped; presence is not capability proof.'%len(actual))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    current=build_catalog()
    if args.write:
        DESTINATION.write_text(json.dumps(current,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
        print('Indexed %d sources, %d literal route declarations; runtime state unverified.'%(current['source_files'],current['static_route_declarations']))
        return 0
    return check_catalog(current)


if __name__=='__main__':raise SystemExit(main())
