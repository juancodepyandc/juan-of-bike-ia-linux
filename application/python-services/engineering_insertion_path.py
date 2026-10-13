"""Verify continuous straight insertion paths using exported STL solids in mm.

Use --manifest project.json --part PART_ID --output insertion-proof.json.
Compare all bounded, geometry-derived candidates; keep uncertain results and
do not turn a lack of a straight path into an impossibility claim.
"""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from application.engineering_insertion import evaluate_insertion


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--part',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args();manifest=Path(args.manifest).resolve()
    report=json.loads(manifest.read_text(encoding='utf-8'));results=[];index=0;assembly_sha256=None
    while True:
        result=evaluate_insertion(report,manifest.parent,args.part,direction_index=index)
        if assembly_sha256 is not None and assembly_sha256!=result['assembly_sha256']:raise ValueError('Geometry changed between candidate directions')
        assembly_sha256=result['assembly_sha256']
        results.append(result)
        print('PROGRESS:assemblage:direction %d/%d — %s'%(index+1,result['direction_count'],result['status']),flush=True)
        index+=1
        if index==result['direction_count']:break
    clear=[r for r in results if r['status']=='clear']
    selected=min(clear,key=lambda r:sum(v*v for v in r['translation_mm'])) if clear else None
    proof={'schema':'aurora.insertion-proof.v1','part_id':args.part,'candidates':results,'selected':selected,
           'status':'clear_path_found' if selected else 'requires_revision_or_other_path',
           'selection_criterion':'Shortest fully verified translation among tested geometry-derived directions only.',
           'physical_fit_validated':False}
    Path(args.output).write_text(json.dumps(proof,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'ok':selected is not None,'proof':str(Path(args.output).resolve()),'status':proof['status']}))
    return 0 if selected else 2


if __name__=='__main__':sys.exit(main())
