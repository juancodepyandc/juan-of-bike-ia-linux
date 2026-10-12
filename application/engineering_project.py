"""Generic verified packaging for agent-designed projects, never project templates."""
from __future__ import annotations
import html
import json
import math
import os
import re
from pathlib import Path
import shutil
import zipfile
import numpy as np
import trimesh


def build_project(spec, root='.', *, require_sources=False):
    root=Path(root).resolve()
    if isinstance(spec,(str,Path)):
        source=(root/spec).resolve()
        if not source.is_relative_to(root) or source.suffix.lower()!='.json' or not source.is_file() or source.stat().st_size>2*1024*1024:raise ValueError('Project JSON must exist inside the project and be at most 2 MiB.')
        spec=json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(spec,dict) or spec.get('units')!='mm': raise ValueError('Project object with units=mm required.')
    title=spec.get('title'); objective=spec.get('objective')
    if not isinstance(title,str) or not title.strip() or not isinstance(objective,str) or not objective.strip(): raise ValueError('Title and objective required.')
    parts=spec.get('parts',[]);bom=spec.get('bom',[]);steps=spec.get('assembly_steps',[])
    if not all(isinstance(v,list) for v in [parts,bom,steps]) or len(parts)>int(os.environ.get('AURORA_ENGINEERING_MAX_PARTS','512')) or len(bom)>200: raise ValueError('Bounded parts, BOM and assembly steps required.')
    if require_sources and parts and any(not (root/name).is_file() for name in ['design.py','tests.py']): raise ValueError('Create design.py and tests.py before packaging; execute the geometry and tests, then rebuild the archive.')
    if not parts and not spec.get('blockers'): raise ValueError('Provide actual parts or explain infeasibility with blockers.')
    bed=np.asarray(spec.get('bed_mm',[220,220,250]),dtype=float)
    if bed.shape!=(3,) or not np.isfinite(bed).all() or np.any(bed<10): raise ValueError('Finite build volume required.')
    margin=float(spec.get('margin_mm',5));usable=bed-2*margin
    if not math.isfinite(margin) or margin<0 or np.any(usable<=0): raise ValueError('Invalid build margin.')
    scene=trimesh.Scene();exploded=trimesh.Scene();measured=[];ids=set();source_files=[];cursor=None
    for index,part in enumerate(parts):
        if not isinstance(part,dict) or not isinstance(part.get('id'),str) or part['id'] in ids: raise ValueError('Unique part IDs required.')
        ids.add(part['id']);path=(root/str(part.get('file',''))).resolve()
        if not path.is_relative_to(root) or path.suffix.lower()!='.stl' or not path.is_file(): raise ValueError('Part STL must exist inside the project.')
        mesh=trimesh.load_mesh(path)
        if not mesh.is_volume or not np.isfinite(mesh.vertices).all() or len(mesh.faces)>2_000_000: raise ValueError('Each printable part must be a closed valid solid.')
        manufacturing=part.get('manufacturing','print')
        if manufacturing not in {'print','purchased'}:raise ValueError('Part manufacturing must be print or purchased.')
        if manufacturing=='purchased' and (part.get('geometry_basis') not in {'manufacturer_cad','measured','assumed_envelope'} or not isinstance(part.get('source_reference'),str) or not part['source_reference'].strip()):raise ValueError('Purchased component requires geometry provenance and a reference; never silently print a motor, sensor or fixing.')
        if manufacturing=='print' and np.any(mesh.extents>usable+1e-4): raise ValueError(f"{part['id']}: does not fit the declared printer; redesign, orient or split it.")
        transform=np.asarray(part.get('assembly_matrix_mm',np.eye(4).tolist()),dtype=float)
        if transform.shape!=(4,4) or not np.isfinite(transform).all() or not np.allclose(transform[3],[0,0,0,1]) or not np.allclose(transform[:3,:3].T@transform[:3,:3],np.eye(3),atol=1e-6) or not np.isclose(np.linalg.det(transform[:3,:3]),1): raise ValueError('Rigid placement matrices required; no hidden scaling.')
        palette=[[120,180,240,255],[245,170,90,255],[110,210,165,255],[200,145,235,255],[240,130,150,255],[225,215,100,255]]
        color=part.get('color_rgba',palette[index%len(palette)])
        if isinstance(color,list) and len(color)==4 and all(type(c) in {int,float} and math.isfinite(c) and 0<=c<=1 for c in color):color=[round(c*255) for c in color]
        if not isinstance(color,list) or len(color)!=4 or any(type(c)!=int or not 0<=c<=255 for c in color): raise ValueError('RGBA bytes or normalized RGBA values required.')
        mesh.visual.face_colors=color;placed=mesh.copy();placed.apply_transform(transform)
        node=f'piece_{index+1:02}';scene.add_geometry(placed,node_name=node,geom_name=node)
        gap=max(10.,max(bed)*.08)
        offset=0. if cursor is None else max(gap*index,cursor-placed.bounds[0,0])
        displacement=np.array([offset,0,0]);spread=placed.copy();spread.apply_translation(displacement)
        cursor=float(spread.bounds[1,0]+gap)
        exploded.add_geometry(spread,node_name=node,geom_name=node)
        printable=mesh.copy();printable.apply_translation(-mesh.bounds[0])
        printable_dir=root/('printable' if manufacturing=='print' else 'components');printable_dir.mkdir(exist_ok=True)
        print_path=printable_dir/(node+'.stl');printable.export(print_path)
        print_transform=transform @ trimesh.transformations.translation_matrix(mesh.bounds[0])
        measured.append({'id':node,'design_id':part['id'],'name':str(part.get('name',part['id'])),'file':print_path.relative_to(root).as_posix(),'dimensions_mm':mesh.extents.tolist(),'volume_mm3':float(mesh.volume),'watertight':True,'manufacturing':manufacturing,'geometry_basis':part.get('geometry_basis','generated_printable'),'source_reference':part.get('source_reference'),'color_rgba':color,'explosion_translation_mm':displacement.tolist(),'assembly_matrix_mm':print_transform.tolist(),'source_origin_mm':mesh.bounds[0].tolist()})
        source_files.extend([path,print_path])
    checked_bom=[]
    for item in bom:
        if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not item['name'].strip() or type(item.get('quantity'))!=int or not 1<=item['quantity']<=10000: raise ValueError('BOM: name and positive integer quantity required.')
        references=item.get('part_ids',[])
        if not isinstance(references,list) or any(ref not in ids for ref in references): raise ValueError('BOM references an unknown part.')
        if not isinstance(item.get('specification'),str) or not item['specification'].strip(): raise ValueError('BOM technical specification required; dimensions, ratings or reference cannot be silently omitted.')
        checked_bom.append({**item,'validation':'proposed; verify manufacturer data and fit before purchase'})
    purchased={p['design_id'] for p in measured if p['manufacturing']=='purchased'}
    if purchased-{ref for i in checked_bom for ref in i.get('part_ids',[])}:raise ValueError('Every purchased component must be referenced by the BOM.')
    for step in steps:
        if not isinstance(step,dict) or not isinstance(step.get('instruction'),str) or any(ref not in ids for ref in step.get('part_ids',[])): raise ValueError('Assembly steps must reference existing parts.')
    blockers=spec.get('blockers',[]);assumptions=spec.get('assumptions',[])
    if not all(isinstance(v,list) and all(isinstance(x,str) for x in v) for v in [blockers,assumptions]): raise ValueError('Assumptions and blockers must be explicit text lists.')
    report={'schema':'aurora.engineering-project.v1','title':title,'objective':objective,'units':'mm','parts':measured,'bom':checked_bom,'assembly_steps':steps,'constraints':spec.get('constraints',[]),'assumptions':assumptions,'blockers':blockers,'design_tests':spec.get('tests',[]),'feasibility':'requires_resolution' if blockers else 'prototype_requires_physical_validation','physical_fit_validated':False,'measured_checks':{'closed_volumes':True,'printer_fit':True,'rigid_placements':True,'references_resolved':True},'sources':spec.get('sources',[])}
    from application.engineering_motion import validate_joints,coordinates
    id_map={p['design_id']:p['id'] for p in measured}
    motion=[{**j,'parent':id_map.get(j.get('parent'),j.get('parent')),'child':id_map.get(j.get('child'),j.get('child'))} for j in spec.get('mechanism_joints',[])]
    report['mechanism_joints']=validate_joints(measured,motion)
    report['closure_constraints']=[{**c,'parent':id_map.get(c.get('parent'),c.get('parent')),'child':id_map.get(c.get('child'),c.get('child'))} for c in spec.get('closure_constraints',[])]
    by_id={p['id']:p for p in measured}
    for closure in report['closure_constraints']:
        for side in ['parent','child']:
            part=by_id.get(closure.get(side))
            anchor=closure.get(side+'_anchor_mm')
            if part and isinstance(anchor,list) and len(anchor)==3:closure[side+'_anchor_mm']=(np.asarray(anchor,dtype=float)-np.asarray(part['source_origin_mm'])).tolist()
    from application.engineering_motion import solve_closures
    _,resolved_home,report['closure_at_home']=solve_closures(measured,report['mechanism_joints'],{},report['closure_constraints'])
    if any(abs(resolved_home.get(j['id'],j['home'])-j['home'])>1e-4 for j in coordinates(report['mechanism_joints'])):raise ValueError('The declared rest assembly requires different passive positions. Revise the actual rest matrices and joint frames using the calculated closure, then rerun; packaging cannot silently replace the declared assembly.')
    if not report['closure_at_home']['converged']:raise ValueError('The declared mechanism does not close at home; inspect residual and revise its geometry or constraints.')
    report['fastening_assessment']=[]
    if spec.get('fastening_candidates'):
        from application.engineering_connections import rank_fastening_locations
        proposals=[{**c,'part_ids':[id_map.get(ref,ref) for ref in c.get('part_ids',[])]} for c in spec['fastening_candidates']]
        report['fastening_assessment']=rank_fastening_locations(measured,root,proposals,spec.get('assembly_views',[]))
    filament_plan=[]
    for part,source in zip(measured,parts):
        if part['manufacturing']!='print':continue
        color=source.get('filament_color','#eeeeee')
        if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):raise ValueError('Physical filament color must be #RRGGBB.')
        filament_plan.append({'part':part['id'],'name':str(source.get('filament') or 'Matière/couleur à confirmer'),'color':color.lower()})
    report['filament_plan']=filament_plan
    printed=[p for p in measured if p['manufacturing']=='print']
    if printed:
        from application.engineering_mesh import print_plates
        plate_report={'profile':{'bed_mm':bed.tolist(),'margin_mm':margin},'parts':printed,'fabrication':{'filament_plan':filament_plan}}
        report['print_plates']=print_plates(root,plate_report)
    else:report['print_plates']=[]
    lines=[f'# {title}',objective,'','## État','Résoudre les blocages avant fabrication.' if blockers else 'Prototype géométriquement vérifié. Validation mécanique, électrique et essai physique nécessaires.','','## Contraintes et hypothèses']
    lines += ['- '+str(v) for v in [*report['constraints'],*assumptions]]
    lines += ['','## Architecture et composants','| Élément | Quantité | Spécification / dimensions | Pièces concernées |','|---|---:|---|---|']
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
    lines += [f"| {cell(i['name'])} | {i['quantity']} | {cell(i['specification'])} | {cell(', '.join(i.get('part_ids',[])))} |" for i in checked_bom]
    lines += ['','## Pièces imprimables']+[f"- {p['name']} ({p['design_id']}) : {' × '.join(f'{v:.2f}' for v in p['dimensions_mm'])} mm ; volume {p['volume_mm3']:.2f} mm³ ; fichier `{p['file']}`." for p in printed]
    lines += ['','## Composants achetés et enveloppes']+[f"- {p['name']} : géométrie {p['geometry_basis']} (provenance déclarée), référence {p['source_reference']}, fichier `{p['file']}` ; exclu des plaques d’impression." for p in measured if p['manufacturing']=='purchased']
    lines += ['','## Plaques et couleurs']+[f"- {plate['id']} : {plate['filament']['name']} ; {len(plate['parts'])} pièce(s), fichier `{plate['file']}`." for plate in report['print_plates']]
    lines += ['- Les couleurs de repérage de l’assemblage distinguent les pièces ; elles ne prescrivent pas plusieurs filaments. Le plan de filaments ci-dessus décrit les couleurs physiques proposées.','- Plaques regroupées par filament/couleur ; placement conservateur. Trancher et choisir supports, matière et paramètres avant impression.']
    lines += ['','![Projection des pièces réellement produites](representation.svg)','','## Montage']+[f"{i+1}. {step['instruction']}" for i,step in enumerate(steps)]
    lines += ['','## Discrétion et accès des fixations']+['- '+json.dumps(c,ensure_ascii=False) for c in report['fastening_assessment']]
    if not report['fastening_assessment']:lines.append('Aucune comparaison géométrique des emplacements de fixation fournie ; discrétion non vérifiée.')
    lines += ['','## Mobilité et vérification géométrique', 'Articulations définies dans le repère mondial au repos ; limites et position initiale explicites. Sans articulation déclarée, aucune animation fonctionnelle.', 'Contrôle de pénétration des solides à la position demandée uniquement. Contacts, efforts, friction, déformations, flexion des câbles et trajectoires continues restent à valider.']
    lines += ['- '+json.dumps(j,ensure_ascii=False) for j in report['mechanism_joints']]
    lines += ['','## Tests']+['- Géométrie mesurée : volumes fermés, dimensions dans le volume utile, transformations rigides et références résolues.','- Les autres résultats sont déclarés par le concepteur : consulter leurs scripts et preuves. Aucun succès mécanique ou électrique n’est déduit de la seule validité du STL.']
    lines += ['- '+json.dumps(t,ensure_ascii=False) for t in report['design_tests']]
    lines += ['','## Points bloquants ou restant à valider']+['- '+x for x in blockers or ['Ajustement imprimé, efforts, matière, fixations et composants achetés à vérifier avec leurs fiches techniques.']]
    lines += ['','## Sources']+['- '+str(x) for x in report['sources']]
    (root/'DOSSIER.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    svg=projection_svg(scene)
    (root/'representation.svg').write_text(svg,encoding='utf-8')
    # Printable HTML includes real geometry and the complete plain-text dossier.
    (root/'DOSSIER.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>body{font:14px system-ui;max-width:960px;margin:30px auto;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}svg{width:100%;height:auto}@page{size:A4;margin:16mm}</style>'+svg+'<pre>'+html.escape('\n'.join(lines))+'</pre><button onclick="print()">Enregistrer en PDF / imprimer</button></html>',encoding='utf-8')
    (root/'project.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if measured:
        scene.scaled(.001).export(root/'assembled.glb');exploded.scaled(.001).export(root/'exploded.glb')
        mesh=scene.to_mesh();manifest={'mode':'assembly','piece_count':len(measured),'pin_count':0,'profile':{'name':spec.get('printer_name','Profil du projet'),'bed_mm':bed.tolist()},'dimensions_mm':mesh.extents.tolist(),'parts':measured,'joints':[],'cut_axis':'x','exploded_gap_mm':max(bed)*.18,'view_up_axis':'z','textured_assembly_available':False,'fabrication':{'instructions':'Consulter DOSSIER.md pour le montage, les composants et les limites de validation.'},'protected_zones_mm':[],'print_plates':report['print_plates']}
        manifest['mechanism_joints']=report['mechanism_joints']
        manifest['motion_controls']=coordinates(report['mechanism_joints'])
        manifest['closure_constraints']=report['closure_constraints']
        (root/'assembly.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
        shutil.copyfile(Path(__file__).with_name('engineering_viewer.html'),root/'viewer.html')
        shutil.copytree(Path(__file__).with_name('engineering_viewer_assets'),root/'viewer_assets',dirs_exist_ok=True)
    archive=root/'engineering-project.zip'
    portable={**spec,'parts':[{**part,'file':(root/part['file']).resolve().relative_to(root).as_posix()} for part in parts]}
    (root/'project_spec.json').write_text(json.dumps(portable,ensure_ascii=False,indent=2),encoding='utf-8')
    included=[root/'DOSSIER.md',root/'DOSSIER.html',root/'representation.svg',root/'project.json',*source_files]
    included += [p for p in [root/'assembled.glb',root/'exploded.glb',root/'viewer.html',root/'assembly.json',root/'design.py',root/'tests.py',root/'project_spec.json'] if p.is_file()]
    included += [(root/c['tool_envelope_file']).resolve() for c in report['fastening_assessment'] if c.get('tool_envelope_file')]
    included += [root/p[key] for p in report['print_plates'] for key in ['file','preview_file']]
    included += list((root/'viewer_assets').rglob('*')) if (root/'viewer_assets').exists() else []
    assets=spec.get('source_assets',[])
    if not isinstance(assets,list) or len(assets)>100:raise ValueError('Bounded source assets list required.')
    for name in assets:
        if not isinstance(name,str):raise ValueError('Source asset paths must be text.')
        path=(root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in {'.glb','.stl','.obj','.png','.jpg','.jpeg','.webp','.json','.md','.pdf'}:raise ValueError('Source assets must be actual data files inside the project.')
        included.append(path)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in dict.fromkeys(included):
            if path.is_file():bundle.write(path,path.relative_to(root))
    return report


def projection_svg(scene):
    if not scene.geometry:return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500"><text x="30" y="50">Étude de faisabilité — aucune pièce fabriquée</text></svg>'
    vertices=[];triangles=[]
    for node in scene.graph.nodes_geometry:
        transform,name=scene.graph[node];mesh=scene.geometry[name].copy();mesh.apply_transform(transform)
        faces=mesh.faces[::max(1,len(mesh.faces)//4000)]
        offset=sum(len(v) for v in vertices);vertices.append(mesh.vertices);triangles.extend((face+offset,mesh.visual.face_colors[i*max(1,len(mesh.faces)//4000)][:3]) for i,face in enumerate(faces))
    v=np.vstack(vertices);projected=np.column_stack([(v[:,0]-v[:,1])*.7071,(v[:,0]+v[:,1])*.4082-v[:,2]*.8165]);low=projected.min(axis=0);span=projected.ptp(axis=0) if hasattr(projected,'ptp') else np.ptp(projected,axis=0);scale=min(820/max(span[0],1e-6),400/max(span[1],1e-6));xy=(projected-low)*scale+[40,40]
    polygons=[]
    for face,color in sorted(triangles,key=lambda f:float(v[f[0]].sum())):
        points=' '.join(f'{x:.2f},{y:.2f}' for x,y in xy[face]);rgb=','.join(str(int(c)) for c in color)
        polygons.append(f'<polygon points="{points}" fill="rgb({rgb})" stroke="#33445c" stroke-width=".25"/>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500">'+''.join(polygons)+'<text x="30" y="475" font-family="sans-serif" font-size="15">Projection des maillages livrés — consulter les cotes du dossier</text></svg>'


def write_assembly_dossier(report,scene,root):
    root=Path(root)
    lines=['# Dossier de fabrication et montage',f"Profil : {report['profile']['name']}.",f"Dimensions assemblées : {' × '.join(f'{x:.2f}' for x in report['dimensions_mm'])} mm.",'','## Nomenclature']
    for part in report['parts']:
        lines.append(f"- 1 × {part['id']} : {' × '.join(f'{x:.2f}' for x in part['dimensions_mm'])} mm ; fichier {part['file']}.")
    for component in report.get('components',[]):
        dims=np.array(component['bounds_mm'][1])-component['bounds_mm'][0]
        lines.append(f"- 1 × {component['name']} ({component['kind']}) : {' × '.join(f'{x:.2f}' for x in dims)} mm ; jeu par côté {component['clearance_mm']} mm ; accès {component['access_side']} {component['access_axis'].upper()}.")
    lines += ['','## Plaques et matières',report['fabrication']['instructions']]
    for plate in report.get('print_plates',[]):
        lines.append(f"- {plate['id']} : {plate['filament']['name']} ({plate['filament']['color']}) ; {', '.join(p['id'] for p in plate['parts'])} ; fichier {plate['file']}.")
    lines += ['','## Montage']
    for joint in report['joints']:
        lines.append(f"- {joint['id']} : joindre les pièces {' ↔ '.join(map(str,joint['pieces']))}, pion Ø{joint['pin_diameter_mm']:.2f} mm, logement Ø{joint['hole_diameter_mm']:.2f} mm, profondeur {joint['depth_each_side_mm']:.2f} mm/côté, centre XYZ {' / '.join(f'{v:.2f}' for v in joint['center_mm'])} mm.")
    lines += ['','## Plaques et couleurs']+[f"- {plate['id']} : {plate['filament']['name']} ; {len(plate['parts'])} pièce(s), fichier `{plate['file']}`." for plate in report['print_plates']]
    lines += ['- Les couleurs de repérage de l’assemblage distinguent les pièces ; elles ne prescrivent pas plusieurs filaments. Le plan de filaments ci-dessus décrit les couleurs physiques proposées.','- Plaques regroupées par filament/couleur ; placement conservateur. Trancher et choisir supports, matière et paramètres avant impression.']
    lines += ['','![Projection du modèle réellement livré](representation.svg)','','## Vérifications et limites','Les contrôles géométriques portent sur la fermeture des pièces, le volume utile, les logements, parois et interférences des pions.','Le jeu doit être calibré par impression. La résistance, les fixations des composants et leurs connexions électriques ne sont pas validées par cet export de maillage.','Pour concevoir ces fonctions, utiliser la conception par objectif : l’agent doit déterminer les composants, effectuer ses calculs et documenter ses preuves.']
    (root/'DOSSIER.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    svg=projection_svg(scene);(root/'representation.svg').write_text(svg,encoding='utf-8')
    (root/'DOSSIER.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Dossier de montage</title><style>body{font:14px system-ui;max-width:960px;margin:30px auto;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}svg{width:100%;height:auto}@page{size:A4;margin:16mm}</style>'+svg+'<pre>'+html.escape('\n'.join(lines))+'</pre><button onclick="print()">Enregistrer en PDF / imprimer</button></html>',encoding='utf-8')
