"""Measured static mesh exports and planar print assemblies, in millimetres.

No inferred CAD dimensions, mesh repairs, or physical fit certification.
The boolean engine operates on closed volumes; textures remain in the original.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import zipfile

import numpy as np
import trimesh


def number(value, label, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label} doit être compris entre {low} et {high}.')
    return float(value)


def settings(raw):
    if not isinstance(raw, dict):
        raise ValueError('Paramètres objet requis.')
    mode = raw.get('mode', 'geometry')
    if mode not in {'geometry', 'textured', 'assembly'}:
        raise ValueError('Version inconnue.')
    result = {'mode': mode, 'size_mm': number(raw.get('size_mm'), 'Dimension maximale (mm)', 1, 2000)}
    if mode != 'assembly':
        return result
    profile = raw.get('profile')
    if not isinstance(profile, dict) or not isinstance(profile.get('name'), str) or not profile['name'].strip():
        raise ValueError('Un profil imprimante nommé est requis.')
    if profile.get('process') not in {'FDM', 'resin'}:
        raise ValueError('Procédé FDM ou résine requis.')
    bed = profile.get('bed_mm')
    if not isinstance(bed, list) or len(bed) != 3:
        raise ValueError('Volume utile X, Y, Z requis.')
    p = {'name': profile['name'][:100], 'process': profile['process'],
         'bed_mm': [number(v, 'Volume utile (mm)', 10, 2000) for v in bed]}
    for key, low, high in [('clearance_mm', 0.01, 2), ('wall_mm', 0.5, 20),
                           ('pin_diameter_mm', 1, 30), ('pin_depth_mm', 2, 60), ('margin_mm', 0, 30)]:
        p[key] = number(profile.get(key), key, low, high)
    p['color_capability'] = profile.get('color_capability', 'single')
    if p['color_capability'] not in {'single', 'multi'}:
        raise ValueError('color_capability : single ou multi requis.')
    p['keyed_pins'] = profile.get('keyed_pins', True)
    if type(p['keyed_pins']) is not bool:
        raise ValueError('keyed_pins doit être un booléen.')
    p['lead_in_mm'] = number(profile.get('lead_in_mm', 0.2), 'Chanfrein d’entrée (mm)', 0, 2)
    small_radius = p['pin_diameter_mm']/2 * (0.8 if p['keyed_pins'] else 1)
    if p['lead_in_mm'] >= min(small_radius, p['pin_depth_mm']/2):
        raise ValueError('Chanfrein trop grand pour le diamètre ou la profondeur des pions.')
    if p['keyed_pins'] and p['clearance_mm'] >= p['pin_diameter_mm']*0.1:
        raise ValueError('Jeu trop grand pour le détrompage : réduire le jeu ou désactiver keyed_pins.')
    if min(p['bed_mm']) <= 2 * p['margin_mm']:
        raise ValueError('Marge supérieure au volume utile.')
    axis = raw.get('axis', 'auto')
    if axis not in {'auto', 'x', 'y', 'z'}:
        raise ValueError('Axe de découpe invalide.')
    cuts = raw.get('cuts_mm', [])
    if not isinstance(cuts, list) or len(cuts) > 15:
        raise ValueError('Maximum 15 plans de découpe.')
    view_up_axis = raw.get('view_up_axis', 'z')
    if view_up_axis not in {'x', 'y', 'z'}:
        raise ValueError('Verticale du modèle : x, y ou z requis.')
    result['view_up_axis'] = view_up_axis
    result.update(profile=p, axis=axis, cuts_mm=[number(v, 'Position de coupe (mm)', 0.01, 1999.99) for v in cuts])
    zones = raw.get('protected_zones_mm', [])
    centers = raw.get('connector_centers_mm', [])
    if not isinstance(zones, list) or len(zones) > 32 or not isinstance(centers, list) or len(centers) > 63:
        raise ValueError('Maximum 32 zones protégées et 63 paires de positions.')
    def vector(v):
        if not isinstance(v, list) or len(v) != 3:
            raise ValueError('Coordonnées X, Y, Z en mm requises.')
        return [number(x, 'Coordonnée (mm)', 0, 2000) for x in v]
    parsed_zones = []
    for zone in zones:
        if not isinstance(zone, list) or len(zone) != 2:
            raise ValueError('Zone protégée : [[xmin,ymin,zmin],[xmax,ymax,zmax]].')
        low, high = map(vector, zone)
        if any(a >= b for a, b in zip(low, high)):
            raise ValueError('Zone protégée : minimum strictement inférieur au maximum.')
        parsed_zones.append([low, high])
    parsed_centers = []
    for pair in centers:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError('Deux centres de raccord par jonction requis.')
        parsed_centers.append([vector(v) for v in pair])
    filaments = raw.get('piece_filaments', [])
    if not isinstance(filaments, list) or len(filaments) > 64:
        raise ValueError('Maximum 64 affectations de filament.')
    import re
    for filament in filaments:
        if (not isinstance(filament, dict) or not isinstance(filament.get('name'), str)
            or not filament['name'].strip() or len(filament['name']) > 100
            or not isinstance(filament.get('color'), str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', filament['color'])):
            raise ValueError('Filament : nom non vide et couleur #RRGGBB requis.')
    result.update(protected_zones_mm=parsed_zones, connector_centers_mm=parsed_centers,
                  piece_filaments=[{'name': f['name'].strip(), 'color': f['color'].lower()} for f in filaments])
    return result


def solid(mesh, label):
    if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty or not mesh.is_volume:
        raise ValueError(f'{label} : volume fermé, orienté et non vide requis. Réparer le maillage avant assemblage.')
    return mesh


def boolean(operation, meshes):
    try:
        result = getattr(trimesh.boolean, operation)(meshes, engine='manifold', check_volume=True)
    except ImportError as exc:
        raise ValueError('Moteur de découpe absent : installer manifold3d dans le Python du bridge.') from exc
    return result


def cylinder(radius, length, center, axis, *, envelope=False):
    # Circumscribe verification envelopes: the polygon must contain the
    # declared circular wall, including between polygon vertices.
    mesh = trimesh.creation.cylinder(radius=radius/math.cos(math.pi/48) if envelope else radius,
                                    height=length, sections=48)
    direction = np.eye(3)[axis]
    mesh.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], direction))
    mesh.apply_translation(center)
    return mesh


def revolved(profile, center, axis):
    mesh = trimesh.creation.revolve(np.array(profile), sections=48)
    mesh.apply_transform(trimesh.geometry.align_vectors([0,0,1],np.eye(3)[axis]))
    mesh.apply_translation(center)
    return solid(mesh, 'Raccord chanfreiné')


def socket(radius, depth, lead, center, axis):
    if not lead:
        return cylinder(radius,2*depth,center,axis)
    return revolved([[0,-depth],[radius,-depth],[radius,-lead],[radius+lead,0],
                     [radius,lead],[radius,depth],[0,depth]],center,axis)


def alignment_pin(radius, length, lead, center, axis):
    if not lead:
        return cylinder(radius,length,center,axis)
    h = length/2
    if lead >= h:
        raise ValueError('Chanfrein incompatible avec la longueur disponible du pion.')
    return revolved([[0,-h],[radius-lead,-h],[radius,-h+lead],[radius,h-lead],
                     [radius-lead,h],[0,h]],center,axis)


def connector_positions(adjacent, cut, axis, config):
    """Rank verified placements, rather than taking the first grid hits."""
    p = config['profile']; depth = p['pin_depth_mm']
    wall_radius = p['pin_diameter_mm']/2 + p['clearance_mm'] + p['lead_in_mm'] + p['wall_mm']
    transverse = [i for i in range(3) if i != axis]
    bounds = np.array([np.maximum(adjacent[0].bounds[0], adjacent[1].bounds[0]),
                       np.minimum(adjacent[0].bounds[1], adjacent[1].bounds[1])])
    prescribed = config.get('_prescribed_pair')
    if prescribed:
        candidates = [np.array(c, dtype=float) for c in prescribed]
        if any(abs(c[axis]-cut) > 1e-5 for c in candidates):
            raise ValueError('Les centres imposés doivent appartenir au plan de coupe.')
    else:
        ranges = [np.linspace(bounds[0,i]+wall_radius+0.01, bounds[1,i]-wall_radius-0.01, 9)
                  for i in transverse]
        if any(bounds[1,i]-bounds[0,i] <= 2*wall_radius for i in transverse):
            raise ValueError(f'Coupe {cut:g} mm : deux raccords avec la paroi demandée ne tiennent pas.')
        candidates = []
        for a in ranges[0]:
            for b in ranges[1]:
                c = np.zeros(3); c[axis] = cut; c[transverse] = [a,b]; candidates.append(c)
    zones = [trimesh.creation.box(np.array(hi)-lo,
             trimesh.transformations.translation_matrix((np.array(hi)+lo)/2))
             for lo,hi in config.get('protected_zones_mm', [])]
    valid = []
    for center in candidates:
        shell = cylinder(wall_radius, 2*(depth+p['wall_mm']), center, axis, envelope=True)
        if any(not boolean('intersection', [shell, zone]).is_empty for zone in zones):
            continue
        for part in adjacent:
            envelope = boolean('intersection', [shell, part])
            if abs(envelope.volume-shell.volume/2) > max(1e-4, shell.volume*1e-6):
                break
        else:
            valid.append(center)
    minimum = 2*wall_radius + 1
    pairs = [(a,b) for i,a in enumerate(valid) for b in valid[i+1:]
             if np.linalg.norm(a-b) >= minimum]
    if not pairs or (prescribed and len(valid) != 2):
        raise ValueError(f'Coupe {cut:g} mm : deux raccords avec la paroi demandée ne tiennent pas ou une zone protégée est touchée. Modifier les contraintes.')
    # Maximise the rotation-constraining baseline; tie-break by centred pair.
    middle = (bounds[0]+bounds[1])/2
    pair = max(pairs, key=lambda pair: (round(float(np.linalg.norm(pair[0]-pair[1])), 6),
                                      -float(np.linalg.norm((pair[0]+pair[1])/2-middle))))
    return pair


def section_volume(mesh, axis):
    """Exact polygonal cross-section area, including holes and branches."""
    from manifold3d import Manifold, Mesh
    oriented = mesh.copy()
    oriented.apply_transform(trimesh.geometry.align_vectors(np.eye(3)[axis], [0,0,1]))
    volume = Manifold(Mesh(np.asarray(oriented.vertices,dtype=np.float32),
                           np.asarray(oriented.faces,dtype=np.uint32)))
    return volume


def seam_area(mesh, axis, cut):
    return float(section_volume(mesh,axis).slice(float(cut)).area())


def automatic_cuts(mesh, axis, count, usable, config):
    profile = config['profile']
    if count == 1:
        return []
    length = float(mesh.extents[axis]); cuts = []; previous = 0
    section = section_volume(mesh,axis)
    minimum = 2*profile['pin_depth_mm'] + profile['wall_mm'] + 0.01
    for index in range(1, count):
        remaining = count-index
        low = max(previous+minimum, length-remaining*usable[axis])
        high = min(previous+usable[axis], length-remaining*minimum)
        if low > high:
            raise ValueError('Volume utile insuffisant pour les logements et les parois.')
        balanced = length*index/count
        candidates = sorted(set([float(np.clip(balanced, low, high)), *np.linspace(low, high, 17)]))
        scored = [(float(section.slice(float(cut)).area()), abs(cut-balanced), cut) for cut in candidates]
        # Smaller seam first; a uniform section keeps a balanced cut. Restrict
        # to 5 ranked planes and verify the real pair of sockets before choosing.
        reference = max((area for area,_,_ in scored if math.isfinite(area)),default=1)
        ranked = sorted(scored,key=lambda item: (item[0]/max(reference,1e-9)+.15*item[1]/length,item[1]))
        chosen = None
        for area,_,cut in ranked[:5]:
            if not math.isfinite(area) or area <= 0:
                continue
            adjacent=[]
            for lo,hi in [(previous,cut),(cut,min(length,cut+usable[axis]))]:
                lower,upper=mesh.bounds[0]-1,mesh.bounds[1]+1
                lower[axis],upper[axis]=lo,hi
                box=trimesh.creation.box(upper-lower,trimesh.transformations.translation_matrix((upper+lower)/2))
                adjacent.append(solid(boolean('intersection',[mesh,box]),'Coupe candidate'))
            try:
                connector_positions(adjacent,cut,axis,config)
            except ValueError:
                continue
            chosen=cut;break
        if chosen is None:
            raise ValueError('Aucune coupe candidate avec deux raccords vérifiés. Choisir des plans ou modifier les contraintes.')
        cuts.append(chosen); previous=chosen
    return cuts


def cut_plan(mesh, config):
    p = config['profile']
    usable = np.array(p['bed_mm']) - 2 * p['margin_mm']
    axis = int(np.argmax(mesh.extents / usable)) if config['axis'] == 'auto' else 'xyz'.index(config['axis'])
    others = [i for i in range(3) if i != axis]
    if any(mesh.extents[i] > usable[i] + 1e-5 for i in others):
        raise ValueError('Plusieurs axes dépassent le volume utile. Réorienter/réduire le modèle ou préparer plusieurs étapes de découpe.')
    length = float(mesh.extents[axis])
    cuts = sorted(config['cuts_mm'])
    if not cuts:
        count = math.ceil(length / usable[axis])
        if count > 16:
            raise ValueError('Découpe limitée à 16 pièces.')
        cuts = automatic_cuts(mesh, axis, count, usable, config)
    if len(set(cuts)) != len(cuts) or any(not 0 < v < length for v in cuts):
        raise ValueError('Les coupes doivent être distinctes et à l’intérieur du modèle, depuis son minimum sur l’axe.')
    depths = np.diff([0, *cuts, length])
    required = [p['pin_depth_mm'] + p['wall_mm']] * len(depths)
    for i in range(1, len(depths)-1):
        required[i] = 2*p['pin_depth_mm'] + p['wall_mm']
    if cuts and any(d <= r for d, r in zip(depths, required)):
        raise ValueError('Une pièce est trop mince pour les logements et la paroi demandés.')
    return axis, cuts, usable


def build_assembly(mesh, config):
    solid(mesh, 'Maillage source')
    axis, cuts, usable = cut_plan(mesh, config)
    p = config['profile']
    bounds = mesh.bounds.copy()
    pieces, slabs = [], []
    for slab, (lo, hi) in enumerate(zip([0, *cuts], [*cuts, mesh.extents[axis]])):
        low, high = bounds[0] - 1, bounds[1] + 1
        low[axis], high[axis] = lo, hi
        box = trimesh.creation.box(high-low, trimesh.transformations.translation_matrix((high+low)/2))
        clipped = solid(boolean('intersection', [mesh, box]), 'Pièce découpée')
        fragments = sorted(clipped.split(), key=lambda part: tuple(part.bounds[0]))
        ids = []
        for part in fragments:
            solid(part, 'Fragment découpé')
            part.metadata['slab'] = slab
            part.metadata['source_cut_volume_mm3'] = float(part.volume)
            ids.append(len(pieces)); pieces.append(part)
        slabs.append(ids)
    if len(pieces) > 64:
        raise ValueError('Maximum 64 pièces après séparation des branches.')
    expected = sum(part.volume for part in pieces)
    if abs(expected - mesh.volume) > max(1e-3, mesh.volume * 1e-5):
        raise ValueError('La découpe ne conserve pas le volume source.')
    joints, pins = [], []
    radius = p['pin_diameter_mm']/2
    depth = p['pin_depth_mm']
    interfaces = []
    epsilon = max(0.001, float(mesh.extents.max())*1e-5)
    for index, cut in enumerate(cuts):
        for left in slabs[index]:
            for right in slabs[index+1]:
                # Shift the right closed solid slightly into the left one to
                # measure a real contact, including each branch of a cut.
                moved = pieces[right].copy()
                delta = np.zeros(3); delta[axis] = -epsilon
                moved.apply_translation(delta)
                contact = boolean('intersection', [pieces[left], moved])
                if not contact.is_empty and contact.volume > 1e-5:
                    interfaces.append((left,right,cut,float(contact.volume/epsilon)))
    if len(interfaces) > 63:
        raise ValueError('Maximum 63 jonctions.')
    prescribed = config.get('connector_centers_mm', [])
    if prescribed and len(prescribed) != len(interfaces):
        raise ValueError('Fournir une paire de centres pour chaque jonction, dans l’ordre des coupes puis des fragments.')
    if len(mesh.split()) == 1:
        reached = {0}
        while True:
            next_nodes = {n for left,right,*_ in interfaces for n in (left,right) if left in reached or right in reached}
            expanded = reached | next_nodes
            if expanded == reached:
                break
            reached = expanded
        if len(reached) != len(pieces):
            raise ValueError('Une pièce issue de la découpe ne possède pas de jonction vérifiable ; changer les coupes.')
    for index, (left,right,cut,contact_area) in enumerate(interfaces):
        joint_config = dict(config)
        if prescribed:
            joint_config['_prescribed_pair'] = prescribed[index]
        positions = connector_positions([pieces[left],pieces[right]], cut, axis, joint_config)
        for slot, center in enumerate(positions):
            pin_radius = radius * (0.8 if p['keyed_pins'] and slot else 1)
            bore_radius = pin_radius + p['clearance_mm']
            hole = socket(bore_radius, depth, p['lead_in_mm'], center, axis)
            for j in [left, right]:
                metadata = dict(pieces[j].metadata)
                pieces[j] = solid(boolean('difference', [pieces[j], hole]), 'Logement de pion')
                pieces[j].metadata.update(metadata)
                if len(pieces[j].split()) != 1:
                    raise ValueError('Un logement détache de la matière ; raccord refusé.')
            # End clearance avoids a pin bottoming out before faces meet.
            pin = alignment_pin(pin_radius, 2*depth - 2*p['clearance_mm'], p['lead_in_mm'], center, axis)
            if pin.extents[axis] <= 0:
                raise ValueError('Jeu axial incompatible avec la longueur du pion.')
            for piece in pieces:
                if np.any(pin.bounds[1] < piece.bounds[0]) or np.any(piece.bounds[1] < pin.bounds[0]):
                    continue
                collision = boolean('intersection', [piece, pin])
                if not collision.is_empty and abs(collision.volume) > 1e-4:
                    raise ValueError('Interférence détectée entre pion et pièce.')
            pins.append(pin)
            joints.append({'id': f'J{len(joints)+1:02}', 'pieces': [left+1, right+1], 'interface': index+1,
                           'estimated_contact_area_before_sockets_mm2': contact_area,
                           'center_mm': center.tolist(), 'axis': 'xyz'[axis],
                           'pin_diameter_mm': 2*pin_radius, 'hole_diameter_mm': 2*bore_radius,
                           'keyed_pair': p['keyed_pins'], 'lead_in_mm': p['lead_in_mm'],
                           'socket_entry_diameter_mm': 2*(bore_radius+p['lead_in_mm']),
                           'depth_each_side_mm': depth, 'radial_clearance_mm': p['clearance_mm'],
                           'minimum_wall_envelope_mm': p['wall_mm'],
                           'baseline_mm': float(np.linalg.norm(positions[0]-positions[1])),
                           'placement': 'prescribed_verified' if config.get('connector_centers_mm') else 'maximum_verified_baseline',
                           'protected_zones_checked': len(config.get('protected_zones_mm', []))})
    for part in pieces:
        if np.any(part.extents > usable + 1e-4):
            raise ValueError('Une pièce ne tient pas dans le volume utile avec cette orientation.')
    if pins and np.any(np.array([2*radius, 2*radius, 2*depth-2*p['clearance_mm']]) > usable + 1e-4):
        raise ValueError('Un pion ne tient pas dans le volume utile.')
    return pieces, pins, joints, axis, cuts


def export_package(source, output, raw):
    config = settings(raw)
    source, output = Path(source), Path(output)
    if source.suffix.lower() not in {'.glb', '.stl', '.obj'}:
        raise ValueError('Formats GLB, STL ou OBJ requis (ressources embarquées pour GLB).')
    original = source.read_bytes()
    if len(original) > 120*1024*1024:
        raise ValueError('Maillage limité à 120 Mo.')
    # Disable external file/texture resolution for uploaded meshes.
    scene = trimesh.load_scene(io.BytesIO(original), file_type=source.suffix[1:], resolver=None)
    mesh = scene.to_mesh()
    if mesh.is_empty or len(mesh.faces) > 2_000_000 or not np.isfinite(mesh.vertices).all() or mesh.extents.max() <= 0:
        raise ValueError('Maillage invalide ou supérieur à deux millions de faces.')
    # UV/normal seams can duplicate a closed surface's positions in glTF.
    # Weld only coincident geometry for volume checks; original UV seams are
    # independently retained by the property-bearing texture export.
    mesh.merge_vertices(merge_tex=True, merge_norm=True)
    scale = config['size_mm'] / float(mesh.extents.max())
    source_transform = np.eye(4); source_transform[:3,:3] *= scale
    source_transform[:3,3] = -mesh.bounds[0]*scale
    mesh.apply_translation(-mesh.bounds[0]); mesh.apply_scale(scale)
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'aurora.print-assembly.v1', 'units': 'mm', 'mode': config['mode'],
              'coordinate_units': {'stl': 'mm', 'glb': 'm', 'manifest': 'mm'},
              'source_sha256': hashlib.sha256(original).hexdigest(), 'source_to_mm_scale': scale,
              'source_to_assembly_matrix_mm': source_transform.tolist(),
              'dimensions_mm': mesh.extents.tolist(), 'source_watertight': bool(mesh.is_watertight),
              'source_volume_valid': bool(mesh.is_volume), 'profile': config.get('profile'),
              'physical_fit_validated': False, 'parts': [], 'joints': []}
    if config['mode'] == 'textured':
        if source.suffix.lower() != '.glb':
            raise ValueError('La variante texturée requiert le GLB original avec matériaux/ressources embarqués.')
        # Preserve original textures, skins, animations and units byte-for-byte.
        (output/'textured_original.glb').write_bytes(original)
        report['export_units'] = 'source_original_units'
        report['size_applied'] = False
        report['materials_preserved'] = True
        report['materials_generated'] = False
    else:
        # Geometry exports never invent or bake colour as shape.
        mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh)
        mesh.export(output/'geometry.stl')
        metric_mesh = mesh.copy(); metric_mesh.apply_scale(0.001)
        metric_mesh.export(output/'geometry.glb')
        report['size_applied'] = True
        if config['mode'] == 'assembly':
            pieces, pins, joints, axis, cuts = build_assembly(mesh, config)
            assembled = trimesh.Scene(); exploded = trimesh.Scene()
            gap = max(20, 2*config['profile']['pin_depth_mm']+4, config['size_mm']*0.12)
            import colorsys
            palette = [[int(v*255) for v in colorsys.hsv_to_rgb((i*0.61803398875)%1,0.6,0.95)]+[255]
                       for i in range(len(pieces))]
            filaments = config.get('piece_filaments', [])
            if filaments and len(filaments) != len(pieces):
                raise ValueError(f'Fournir un filament par pièce : {len(pieces)} pièces, {len(filaments)} affectations.')
            if filaments:
                palette = [[int(f['color'][k:k+2],16) for k in (1,3,5)]+[255] for f in filaments]
            for i, part in enumerate(pieces):
                name = f'piece_{i+1:02}'
                part.visual.face_colors = palette[i % len(palette)]
                shift = -part.bounds[0]
                printable = part.copy(); printable.apply_translation(shift)
                printable.export(output/(name+'.stl'))
                assembled.add_geometry(part, node_name=name, geom_name=name)
                spread = part.copy(); delta = np.zeros(3); delta[axis] = part.metadata['slab'] * gap
                spread.apply_translation(delta); exploded.add_geometry(spread, node_name=name, geom_name=name)
                report['parts'].append({'id': name, 'file': name+'.stl', 'dimensions_mm': printable.extents.tolist(),
                                        'watertight': bool(printable.is_volume), 'print_to_assembly_translation_mm': (-shift).tolist(),
                                        'print_to_assembly_matrix_mm': trimesh.transformations.translation_matrix(-shift).tolist(),
                                        'explosion_translation_mm': delta.tolist(), 'color_rgba': palette[i],
                                        'filament': filaments[i] if filaments else None,
                                        'socket_removed_volume_fraction': 1-float(part.volume)/part.metadata['source_cut_volume_mm3']})
            for i, pin in enumerate(pins):
                name = f'pin_{i+1:02}'
                pin.visual.face_colors = [255,106,61,255]
                printed = alignment_pin(joints[i]['pin_diameter_mm']/2,
                                   2*config['profile']['pin_depth_mm']-2*config['profile']['clearance_mm'],
                                   joints[i]['lead_in_mm'], [0, 0, 0], 2)
                printed.apply_translation(-printed.bounds[0]); printed.export(output/(name+'.stl'))
                assembled.add_geometry(pin, node_name=name, geom_name=name)
                spread = pin.copy(); delta = np.zeros(3)
                delta[axis] = (pieces[joints[i]['pieces'][0]-1].metadata['slab']+0.5)*gap
                spread.apply_translation(delta); exploded.add_geometry(spread, node_name=name, geom_name=name)
                transform = trimesh.geometry.align_vectors([0,0,1],np.eye(3)[axis])
                transform[:3,3] = np.array(joints[i]['center_mm'])-transform[:3,:3]@printed.centroid
                report['parts'].append({'id': name, 'file': name+'.stl', 'dimensions_mm': printed.extents.tolist(),
                                        'watertight': True, 'joint': joints[i]['id'], 'color_rgba': [255,106,61,255],
                                        'print_to_assembly_matrix_mm': transform.tolist(), 'explosion_translation_mm': delta.tolist()})
            assembled.scaled(0.001).export(output/'assembled.glb')
            exploded.scaled(0.001).export(output/'exploded.glb')
            has_texture = any(g.visual.kind == 'texture' for g in scene.geometry.values())
            if has_texture:
                from application.engineering_texture import textured_pieces
                textured = trimesh.Scene()
                groups = textured_pieces(scene, scale, pieces, joints, axis)
                for i, geometries in enumerate(groups):
                    for k, geometry in enumerate(geometries):
                        name = f'piece_{i+1:02}_surface_{k:02}'
                        textured.add_geometry(geometry, node_name=name, geom_name=name)
                for i,pin in enumerate(pins):
                    textured.add_geometry(pin.copy(), node_name=f'pin_{i+1:02}', geom_name=f'pin_{i+1:02}')
                textured.scaled(0.001).export(output/'assembled_textured.glb')
                for name,geometry in textured.geometry.items():
                    delta = np.array(next(part['explosion_translation_mm'] for part in report['parts']
                                         if part['id'] == '_'.join(name.split('_')[:2])))
                    geometry.apply_translation(delta)
                textured.scaled(0.001).export(output/'exploded_textured.glb')
            shutil.copyfile(Path(__file__).with_name('engineering_viewer.html'), output/'viewer.html')
            shutil.copytree(Path(__file__).with_name('engineering_viewer_assets'),output/'viewer_assets')
            cross_sections = section_volume(mesh,axis) if cuts else None
            report.update(view_up_axis=config['view_up_axis'], joints=joints, cut_axis='xyz'[axis], cuts_mm=cuts, piece_count=len(pieces), pin_count=len(pins),
                          textured_assembly_available=has_texture, exploded_gap_mm=gap,
                          protected_zones_mm=config.get('protected_zones_mm', []),
                          viewer_file='viewer.html',
                          cut_selection='explicit_planes' if config['cuts_mm'] else 'sampled_seam_area_with_verified_sockets',
                          seam_area_mm2=[float(cross_sections.slice(float(c)).area()) for c in cuts],
                          fabrication={'color_capability': config['profile']['color_capability'],
                                       'separate_filament_parts': bool(filaments),
                                       'filament_plan': [{'part': f'piece_{i+1:02}', **f} for i,f in enumerate(filaments)],
                                       'texture_is_not_print_color': True,
                                       'instructions': 'Imprimer les pièces séparément avec leur filament, puis assembler avec les pions appariés.' if filaments else 'Couleurs du viewer : repères de pièces, pas des couleurs de filament. Une texture ne définit pas une séparation volumique.'},
                          checks={'closed_pieces': True, 'source_cut_volume_preserved': True,
                                  'pins_without_mesh_interference': True, 'fits_declared_build_volume': True,
                                  'all_cut_interfaces_connected': True, 'wall_envelopes_verified': True,
                                  'protected_zones_respected': True})
    (output/'assembly.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'READ_ME.txt').write_text(
        'Aurora — géométrie / texture / assemblage\n'
        'STL et manifeste : millimètres. GLB de géométrie/assemblage : mètres selon la convention glTF.\n'
        'textured_original.glb conserve exactement le fichier et les unités d’origine ; aucune nouvelle texture.\n'
        'piece_NN.stl : pièces au sol dans leur orientation de découpe. pin_NN.stl : pions séparés verticaux.\n'
        'assembled.glb : positions finales. exploded.glb : ordre des pièces. assembly.json : cotes et raccords.\n'
        'viewer.html : viewer interactif autonome ; ouvrir via jobia view3d archive.zip.\n'
        'Le CLI ouvre le viewer après assemblage ; --viewer textured démarre en vue éclatée texturée.\n'
        'Textures des surfaces originales et UV conservés ; nouvelles faces de coupe/logement neutres.\n'
        'Contraintes optionnelles protected_zones_mm : boîtes [minimum XYZ, maximum XYZ].\n'
        'connector_centers_mm : une paire XYZ par jonction, ordre des coupes puis des fragments.\n'
        'Toutes ces coordonnées utilisent le modèle final en mm, minimum ramené à zéro.\n'
        'Le jeu est radial : diamètre du logement = diamètre du pion + 2 × jeu.\n'
        'Deux pions par jonction/branche guident le placement ; les placements valides sont comparés.\n'
        'Détrompage activé par défaut : second diamètre à 80 % du premier ; chanfrein par défaut 0,2 mm.\n'
        'Renseigner les zones fonctionnelles interdites : elles ne peuvent pas être devinées par le moteur.\n'
        'Ajuster le profil sur un essai imprimé avant la série.\n'
        'Les contrôles de maillage ne certifient ni résistance, supports, retrait matière, ni précision de fabrication.\n', encoding='utf-8')
    archive = output.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(output.rglob('*')):
            if file.is_file():
                z.write(file, file.relative_to(output).as_posix())
    return report


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--settings', required=True)
    args = parser.parse_args()
    try:
        result = export_package(args.source, args.output, json.loads(Path(args.settings).read_text(encoding='utf-8')))
        print(json.dumps({'ok': True, 'report': result}))
    except Exception as exc:
        # Never leave a partially completed package available as a success.
        shutil.rmtree(args.output, ignore_errors=True)
        Path(args.output).with_suffix('.zip').unlink(missing_ok=True)
        print(json.dumps({'ok': False, 'error': str(exc)}))
        raise SystemExit(1)
