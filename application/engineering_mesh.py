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
    if min(p['bed_mm']) <= 2 * p['margin_mm']:
        raise ValueError('Marge supérieure au volume utile.')
    axis = raw.get('axis', 'auto')
    if axis not in {'auto', 'x', 'y', 'z'}:
        raise ValueError('Axe de découpe invalide.')
    cuts = raw.get('cuts_mm', [])
    if not isinstance(cuts, list) or len(cuts) > 15:
        raise ValueError('Maximum 15 plans de découpe.')
    result.update(profile=p, axis=axis, cuts_mm=[number(v, 'Position de coupe (mm)', 0.01, 1999.99) for v in cuts])
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


def cylinder(radius, length, center, axis):
    mesh = trimesh.creation.cylinder(radius=radius, height=length, sections=48)
    direction = np.eye(3)[axis]
    mesh.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], direction))
    mesh.apply_translation(center)
    return mesh


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
        cuts = [length * i / count for i in range(1, count)]
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
    pieces = []
    for lo, hi in zip([0, *cuts], [*cuts, mesh.extents[axis]]):
        low, high = bounds[0] - 1, bounds[1] + 1
        low[axis], high[axis] = lo, hi
        box = trimesh.creation.box(high-low, trimesh.transformations.translation_matrix((high+low)/2))
        part = solid(boolean('intersection', [mesh, box]), 'Pièce découpée')
        # A disconnected slice could produce unretained islands. Refuse it.
        if len(part.split()) != 1:
            raise ValueError('Une coupe produit plusieurs morceaux détachés. Déplacer la coupe ou séparer les objets avant export.')
        pieces.append(part)
    expected = sum(part.volume for part in pieces)
    if abs(expected - mesh.volume) > max(1e-3, mesh.volume * 1e-5):
        raise ValueError('La découpe ne conserve pas le volume source.')
    joints, pins = [], []
    radius = p['pin_diameter_mm']/2
    hole_radius = radius + p['clearance_mm']  # radial, not diameter
    wall_radius = hole_radius + p['wall_mm']
    depth = p['pin_depth_mm']
    transverse = [i for i in range(3) if i != axis]
    for index, cut in enumerate(cuts):
        positions = []
        ranges = [np.linspace(bounds[0, i] + wall_radius, bounds[1, i] - wall_radius, 7)
                  for i in transverse]
        candidates = [(a, b) for a in ranges[0] for b in ranges[1]]
        # Deterministic, favour wide separation to constrain rotation.
        for a, b in candidates:
            center = np.zeros(3); center[axis] = cut
            center[transverse] = [a, b]
            if positions and min(np.linalg.norm(center-c) for c in positions) < 2*wall_radius + 1:
                continue
            shell = cylinder(wall_radius, 2*(depth+p['wall_mm']), center, axis)
            outside = boolean('difference', [shell, mesh])
            if not outside.is_empty and abs(outside.volume) > max(1e-4, shell.volume*1e-6):
                continue
            # Check both adjacent pieces, including earlier joint cavities.
            hole = cylinder(hole_radius, 2*depth, center, axis)
            removed = []
            for part in pieces[index:index+2]:
                envelope = boolean('intersection', [shell, part])
                if abs(envelope.volume-shell.volume/2) > max(1e-3, shell.volume*1e-5):
                    break
                overlap = boolean('intersection', [hole, part])
                removed.append(overlap.volume if not overlap.is_empty else 0)
            if len(removed) != 2 or any(abs(v-hole.volume/2) > max(1e-3, hole.volume*1e-5) for v in removed):
                continue
            positions.append(center)
            if len(positions) == 2:
                break
        if len(positions) != 2:
            raise ValueError(f'Coupe {cut:g} mm : deux raccords avec la paroi demandée ne tiennent pas. Changer coupe, diamètre, profondeur ou paroi.')
        for center in positions:
            hole = cylinder(hole_radius, 2*depth, center, axis)
            for j in [index, index+1]:
                pieces[j] = solid(boolean('difference', [pieces[j], hole]), 'Logement de pion')
                if len(pieces[j].split()) != 1:
                    raise ValueError('Un logement détache de la matière ; raccord refusé.')
            # End clearance avoids a pin bottoming out before faces meet.
            pin = cylinder(radius, 2*depth - 2*p['clearance_mm'], center, axis)
            if pin.extents[axis] <= 0:
                raise ValueError('Jeu axial incompatible avec la longueur du pion.')
            for piece in pieces[index:index+2]:
                collision = boolean('intersection', [piece, pin])
                if not collision.is_empty and abs(collision.volume) > 1e-4:
                    raise ValueError('Interférence détectée entre pion et pièce.')
            pins.append(pin)
            joints.append({'id': f'J{len(joints)+1:02}', 'pieces': [index+1, index+2],
                           'center_mm': center.tolist(), 'axis': 'xyz'[axis],
                           'pin_diameter_mm': 2*radius, 'hole_diameter_mm': 2*hole_radius,
                           'depth_each_side_mm': depth, 'radial_clearance_mm': p['clearance_mm'],
                           'minimum_wall_envelope_mm': p['wall_mm']})
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
    scale = config['size_mm'] / float(mesh.extents.max())
    mesh.apply_translation(-mesh.bounds[0]); mesh.apply_scale(scale)
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'aurora.print-assembly.v1', 'units': 'mm', 'mode': config['mode'],
              'coordinate_units': {'stl': 'mm', 'glb': 'm', 'manifest': 'mm'},
              'source_sha256': hashlib.sha256(original).hexdigest(), 'source_to_mm_scale': scale,
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
            palette = [[127,183,255,255], [77,213,164,255], [255,209,102,255]]
            for i, part in enumerate(pieces):
                name = f'piece_{i+1:02}'
                part.visual.face_colors = palette[i % len(palette)]
                shift = -part.bounds[0]
                printable = part.copy(); printable.apply_translation(shift)
                printable.export(output/(name+'.stl'))
                assembled.add_geometry(part, node_name=name, geom_name=name)
                spread = part.copy(); delta = np.zeros(3); delta[axis] = i * gap
                spread.apply_translation(delta); exploded.add_geometry(spread, node_name=name, geom_name=name)
                report['parts'].append({'id': name, 'file': name+'.stl', 'dimensions_mm': printable.extents.tolist(),
                                        'watertight': bool(printable.is_volume), 'print_to_assembly_translation_mm': (-shift).tolist()})
            for i, pin in enumerate(pins):
                name = f'pin_{i+1:02}'
                pin.visual.face_colors = [255,106,61,255]
                printed = cylinder(config['profile']['pin_diameter_mm']/2,
                                   2*config['profile']['pin_depth_mm']-2*config['profile']['clearance_mm'], [0, 0, 0], 2)
                printed.apply_translation(-printed.bounds[0]); printed.export(output/(name+'.stl'))
                assembled.add_geometry(pin, node_name=name, geom_name=name)
                spread = pin.copy(); delta = np.zeros(3)
                delta[axis] = (joints[i]['pieces'][0]-1+0.5)*gap
                spread.apply_translation(delta); exploded.add_geometry(spread, node_name=name, geom_name=name)
                report['parts'].append({'id': name, 'file': name+'.stl', 'dimensions_mm': printed.extents.tolist(),
                                        'watertight': True, 'joint': joints[i]['id']})
            assembled.scaled(0.001).export(output/'assembled.glb')
            exploded.scaled(0.001).export(output/'exploded.glb')
            report.update(joints=joints, cut_axis='xyz'[axis], cuts_mm=cuts, piece_count=len(pieces), pin_count=len(pins),
                          checks={'closed_pieces': True, 'source_cut_volume_preserved': True,
                                  'pins_without_mesh_interference': True, 'fits_declared_build_volume': True})
    (output/'assembly.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'READ_ME.txt').write_text(
        'Aurora — géométrie / texture / assemblage\n'
        'STL et manifeste : millimètres. GLB de géométrie/assemblage : mètres selon la convention glTF.\n'
        'textured_original.glb conserve exactement le fichier et les unités d’origine ; aucune nouvelle texture.\n'
        'piece_NN.stl : pièces au sol dans leur orientation de découpe. pin_NN.stl : pions séparés verticaux.\n'
        'assembled.glb : positions finales. exploded.glb : ordre des pièces. assembly.json : cotes et raccords.\n'
        'Le jeu est radial : diamètre du logement = diamètre du pion + 2 × jeu.\n'
        'Deux pions par jonction guident le placement. Ajuster le profil sur un essai imprimé avant la série.\n'
        'Les contrôles de maillage ne certifient ni résistance, supports, retrait matière, ni précision de fabrication.\n', encoding='utf-8')
    archive = output.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(output.iterdir()):
            z.write(file, file.name)
    return report


if __name__ == '__main__':
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
