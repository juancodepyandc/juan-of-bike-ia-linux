"""Measured GLB surface colors to closed printable inlays and structural core.

Use --spec JSON containing source, output, palette [{name,color}], size_mm,
shell_mm and profile. Preserve the original textured GLB separately. The result
is an engineering candidate, not print approval: validate local wall thickness,
clearance, insertion and fastening, then package with engineering_project.
"""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from application.engineering_color_parts import color_parts
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--spec',required=True)
    args=parser.parse_args();spec=json.loads(Path(args.spec).read_text(encoding='utf-8'))
    result=color_parts(**spec)
    print(json.dumps({'ok':True,'parts':len(result['spec']['parts']),'output':spec['output'],'proof':result['proof']},ensure_ascii=False))
