"""Derive closed color inlays from actual surface faces, never a subject template.

The designer supplies a measured palette, physical scale and shell depth. This
computes ideal internal interfaces; printer compensation and joint strength
remain calibration tasks, not inferred from a rendering.
"""
from pathlib import Path
import json
import math
import re
import io
import hashlib
import numpy as np
import trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def color_parts(source,output,*,palette,size_mm,shell_mm=2,profile=None,max_parts=128):
    source=Path(source).resolve();output=Path(output).resolve()
    if source.suffix.lower()!='.glb':raise ValueError('An actual local GLB is required.')
    if not isinstance(palette,list) or not 2<=len(palette)<=16:raise ValueError('Provide 2–16 physical colors derived from the actual reference.')
    for entry in palette:
        if not isinstance(entry,dict) or not isinstance(entry.get('name'),str) or not entry['name'] or not re.fullmatch('#[0-9a-fA-F]{6}',str(entry.get('color',''))):raise ValueError('Each physical color requires a name and #RRGGBB.')
    if not all(type(v) in {int,float} and math.isfinite(v) and v>0 for v in [size_mm,shell_mm]):raise ValueError('Finite physical size and shell depth required.')
    profile=profile or {};bed=np.asarray(profile.get('bed_mm',[220,220,250]),float)
    margin=float(profile.get('margin_mm',5))
    if bed.shape!=(3,) or not np.isfinite(bed).all() or np.any(bed<10) or not math.isfinite(margin) or margin<0 or np.any(bed<=2*margin):raise ValueError('Valid printer volume and margin required.')
    if source.stat().st_size>120*1024*1024:raise ValueError('GLB input exceeds the bounded 120 MiB processing batch; revise the project into subassemblies.')
    original=source.read_bytes()
    scene=trimesh.load_scene(io.BytesIO(original),file_type='glb',resolver=None)
    meshes=[];colors=[]
    for node in scene.graph.nodes_geometry:
        matrix,name=scene.graph[node];mesh=scene.geometry[name].copy()
        if not isinstance(mesh,trimesh.Trimesh):raise ValueError('Triangular surface geometry required.')
        visual=mesh.visual
        if visual.kind=='texture':
            visual=visual.to_color()
            rgb=visual.vertex_colors[mesh.faces][...,:3].mean(axis=1)
        elif visual.kind in {'face','vertex'}:rgb=visual.face_colors[:,:3].astype(float)
        else:raise ValueError('Source surface has no measured color information; inspect/revise the reference rather than inventing color regions.')
        mesh.apply_transform(matrix);meshes.append(mesh);colors.append(rgb)
    if not meshes:raise ValueError('No triangular geometry in source.')
    body=trimesh.util.concatenate(meshes);rgb=np.vstack(colors)
    if len(body.faces)>2_000_000:raise ValueError('Surface batch exceeds two million faces; process measured subassemblies.')
    extent=float(body.extents.max())
    if not math.isfinite(extent) or extent<=0:raise ValueError('Empty or nonfinite geometry.')
    center=body.bounds.mean(axis=0);body.vertices=(body.vertices-center)*(size_mm/extent)
    body.merge_vertices()
    if not body.is_volume:raise ValueError('Source must be a closed valid solid before color partition; repair and measure shape changes first.')
    if shell_mm>=float(body.extents.min())/2:raise ValueError('Shell depth exceeds the measured object thickness.')
    palette_rgb=np.array([[int(e['color'][i:i+2],16) for i in [1,3,5]] for e in palette],float)
    labels=np.empty(len(rgb),int)
    for offset in range(0,len(rgb),16384):
        labels[offset:offset+16384]=np.argmin(np.sum((rgb[offset:offset+16384,None,:]-palette_rgb[None,:,:])**2,axis=2),axis=1)
    areas=np.bincount(labels,weights=body.area_faces,minlength=len(palette))
    if np.count_nonzero(areas)<2:raise ValueError('The supplied palette does not separate at least two actual source color regions.')
    if np.any(areas<=0):raise ValueError('A requested palette color has no measured surface region; revise the reference or palette rather than fabricating a colored piece.')
    base=int(areas.argmax());inlays=[];measurements=[]
    adjacency=body.face_adjacency
    for color in range(len(palette)):
        if color==base:continue
        selected=np.flatnonzero(labels==color)
        if not len(selected):continue
        index=np.full(len(body.faces),-1,int);index[selected]=np.arange(len(selected))
        links=adjacency[(index[adjacency]>=0).all(axis=1)]
        graph=coo_matrix((np.ones(len(links)),(index[links[:,0]],index[links[:,1]])),shape=(len(selected),len(selected)))
        count,components=connected_components(graph,directed=False)
        for component in range(count):
            faces=selected[components==component]
            if len(inlays)+2>max_parts:raise ValueError('Too many disconnected color details; revise the measured palette or manufacturing strategy, not a subject-specific fallback.')
            outer_ids=np.unique(body.faces[faces]);mapping=np.full(len(body.vertices),-1,int);mapping[outer_ids]=np.arange(len(outer_ids))
            outer=body.vertices[outer_ids];inner=outer-body.vertex_normals[outer_ids]*shell_mm
            top=mapping[body.faces[faces]];n=len(outer)
            edges=np.vstack([top[:,[0,1]],top[:,[1,2]],top[:,[2,0]]])
            sorted_edges=np.sort(edges,axis=1);_,inverse,counts=np.unique(sorted_edges,axis=0,return_inverse=True,return_counts=True)
            boundary=edges[counts[inverse]==1]
            sides=np.array([tri for a,b in boundary for tri in ([b,a,a+n],[b,a+n,b+n])],int).reshape((-1,3))
            shell=trimesh.Trimesh(vertices=np.vstack([outer,inner]),faces=np.vstack([top,top[:,::-1]+n,sides]),process=True)
            if not shell.is_volume:raise ValueError('A color region does not form a valid internal shell; revise the depth, palette or surface topology.')
            inlay=trimesh.boolean.intersection([body,shell],engine='manifold')
            if not inlay.is_volume or inlay.volume<=1e-6:raise ValueError('Color inlay is empty or non-manifold after clipping to the actual object.')
            parts=inlay.split(only_watertight=False)
            if len(parts)!=1:raise ValueError('Color inlay has disconnected solids; revise the region or expose them as separately assessed pieces.')
            outer_area=float(body.area_faces[faces].sum())
            mean_depth=float(inlay.volume/outer_area)
            minimum=float(profile.get('minimum_printable_wall_mm',profile.get('wall_mm',.8)))
            if not math.isfinite(minimum) or minimum<=0 or mean_depth<minimum:raise ValueError('Measured average inlay depth is below the printer wall requirement; revise shell depth and inspect local thickness.')
            inlays.append((color,inlay))
            measurements.append({'palette_index':color,'source_face_count':len(faces),'outer_area_mm2':outer_area,'inlay_volume_mm3':float(inlay.volume),'average_depth_mm':mean_depth,'local_minimum_thickness_validated':False})
    core=trimesh.boolean.difference([body,*[m for _,m in inlays]],engine='manifold')
    if not core.is_volume:raise ValueError('Partition invalidates the structural core; revise interfaces.')
    core_parts=core.split(only_watertight=False)
    if any(not p.is_volume for p in core_parts) or len(core_parts)+len(inlays)>max_parts:raise ValueError('Structural components must be closed and fit the bounded subassembly.')
    all_parts=[*[(base,p) for p in core_parts],*inlays]
    if any(np.any(mesh.extents>bed-2*float(profile.get('margin_mm',5))+1e-4) for _,mesh in all_parts):raise ValueError('A measured color part exceeds the printer bed; split/orient that geometry before packaging. The physical scale has not been silently reduced.')
    reconstructed=trimesh.boolean.union([mesh for _,mesh in all_parts],engine='manifold')
    lost=trimesh.boolean.difference([body,reconstructed],engine='manifold')
    extra=trimesh.boolean.difference([reconstructed,body],engine='manifold')
    residual=float((0 if lost.is_empty else abs(lost.volume))+(0 if extra.is_empty else abs(extra.volume)))
    tolerance=max(1e-5,float(body.volume)*1e-5)
    if not math.isfinite(residual) or residual>tolerance:raise ValueError('Color partition changed the measured original solid; do not approve the silhouette.')
    output.mkdir(parents=True,exist_ok=True)
    parts=[]
    for index,(color,mesh) in enumerate(all_parts):
        pid=f'color-part-{index+1}';mesh.export(output/(pid+'.stl'))
        parts.append({'id':pid,'name':palette[color]['name']+f' · {index+1}','file':pid+'.stl','assembly_matrix_mm':np.eye(4).tolist(),'color_rgba':palette_rgb[color].astype(int).tolist()+[255],'filament':palette[color]['name'],'filament_color':palette[color]['color']})
    proof={'source':'source.glb','source_sha256':hashlib.sha256(original).hexdigest(),'size_mm':size_mm,'source_volume_mm3':float(body.volume),'color_regions':measurements,'palette_surface_area_mm2':areas.tolist(),'volume_residual_mm3':residual,'palette_rgb_rms_error':float(np.sqrt(np.mean((rgb-palette_rgb[labels])**2))),
           'physical_fit_validated':False,'clearance_applied_mm':0,'scope':'Closed geometrical inlays with internal mating surfaces. Ideal zero-clearance partition preserves the solid; local minimum thickness, semantic fidelity, compensation, insertion paths, adhesive choice and strength require further measured tests.'}
    (output/'color-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    spec={'units':'mm','title':'Pièces par couleur du modèle réel','objective':'Préparer les couleurs physiques sans remplacer la silhouette du modèle source.','bed_mm':bed.tolist(),'margin_mm':profile.get('margin_mm',5),'printer_name':profile.get('name','Profil à confirmer'),'parts':parts,
          'bom':[{'name':p['filament'],'quantity':1,'specification':'Filament compatible avec le profil fourni ; couleur '+p['filament_color'],'part_ids':[p['id']]} for p in parts],
          'assembly_steps':[{'instruction':'Insérer les volumes de couleur sur leurs interfaces internes après validation des jeux, de la trajectoire d’insertion et du procédé de fixation. Aucun pion ajouté sans justification géométrique.','part_ids':[p['id'] for p in parts]}],
          'assumptions':['Palette proposée par le concepteur ; comparer plusieurs vues au modèle source.','Partition idéale sans jeu ; calibration et compensation requises avant impression.','Les surfaces de raccord sont intérieures ; la résistance de la fixation n’est pas certifiée.'],
          'blockers':['Valider épaisseurs locales, insertion, compensation et fixation avant fabrication.'],
          'tests':[{'name':'Préservation volumique du solide original','passed':residual<=tolerance,'proof_file':'color-proof.json'}]}
    (output/'source.glb').write_bytes(original)
    input_data={'source':'source.glb','output':'.','palette':palette,'size_mm':size_mm,'shell_mm':shell_mm,'profile':profile,'max_parts':max_parts}
    (output/'color-input.json').write_text(json.dumps(input_data,ensure_ascii=False,indent=2),encoding='utf-8')
    marker='# AURORA_COLOR_DESIGN_ENTRY'
    code=Path(__file__).read_text(encoding='utf-8').split('\n'+marker)[0]
    (output/'design.py').write_text(code+'\n'+marker+"\nif __name__=='__main__':\n    color_parts(**json.loads(Path('color-input.json').read_text(encoding='utf-8')))\n",encoding='utf-8')
    (output/'tests.py').write_text('''import json
from pathlib import Path
import numpy as np
import trimesh
settings=json.loads(Path('color-input.json').read_text(encoding='utf-8'))
spec=json.loads(Path('project_spec.json').read_text(encoding='utf-8'))
source=trimesh.load_scene('source.glb').to_mesh();source.merge_vertices()
assert source.is_volume
source.vertices=(source.vertices-source.bounds.mean(axis=0))*(settings['size_mm']/source.extents.max())
parts=[trimesh.load_mesh(p['file']) for p in spec['parts']]
assert all(p.is_volume and np.isfinite(p.vertices).all() for p in parts)
union=trimesh.boolean.union(parts,engine='manifold')
assert union.is_volume
assert abs(union.volume-source.volume)<=max(1e-5,source.volume*1e-5)
assert np.allclose(union.bounds,source.bounds,atol=1e-4)
assert all(np.all(p.extents<=np.asarray(spec['bed_mm'])-2*spec['margin_mm']+1e-4) for p in parts)
for i,a in enumerate(parts):
 for b in parts[i+1:]:
  intersection=trimesh.boolean.intersection([a,b],engine='manifold')
  assert intersection.is_empty or abs(intersection.volume)<1e-5
Path('tests-proof.json').write_text(json.dumps({'closed_solids':True,'volume_and_bounds_preserved':True,'printer_bounds_checked':True,'physical_fit_validated':False}))
''',encoding='utf-8')
    spec['source_assets']=['source.glb','color-input.json','color-proof.json']
    (output/'project_spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'spec':spec,'proof':proof}
