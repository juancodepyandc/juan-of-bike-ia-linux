"""
Genere un modele 3D de tete avec morph targets pour lip sync.
Sortie: GLB standard sans compression, sans KTX2, sans meshopt.
Morph targets: jawOpen, mouthSmile, mouthFunnel, eyeBlinkL, eyeBlinkR, browUp
"""
import json, struct, math, sys, os
import numpy as np

def make_sphere(rings=32, sectors=32):
    """Sphere UV modifiee en forme de tete."""
    verts, norms, uvs, indices = [], [], [], []
    for r in range(rings + 1):
        phi = math.pi * r / rings
        for s in range(sectors + 1):
            theta = 2 * math.pi * s / sectors
            x = math.sin(phi) * math.cos(theta)
            y = math.cos(phi)
            z = math.sin(phi) * math.sin(theta)
            # Deformer en tete: aplatir l'arriere, etirer le menton
            x *= 0.85
            z *= 0.9
            if y < -0.2:  # Menton
                y *= 1.15
                x *= 0.8 + (y + 0.2) * 0.3
            if y > 0.3:  # Crane
                x *= 0.95
                z *= 0.95
            verts.extend([x, y, z])
            # Normal approximatif
            l = math.sqrt(x*x + y*y + z*z) or 1
            norms.extend([x/l, y/l, z/l])
            uvs.extend([s / sectors, r / rings])
    for r in range(rings):
        for s in range(sectors):
            a = r * (sectors + 1) + s
            b = a + sectors + 1
            indices.extend([a, b, a + 1, b, b + 1, a + 1])
    return np.array(verts, dtype=np.float32), np.array(norms, dtype=np.float32), \
           np.array(uvs, dtype=np.float32), np.array(indices, dtype=np.uint16)

def make_morph_target(base_verts, func):
    """Cree un morph target en appliquant func a chaque vertex."""
    n = len(base_verts) // 3
    deltas = np.zeros(n * 3, dtype=np.float32)
    for i in range(n):
        x, y, z = base_verts[i*3], base_verts[i*3+1], base_verts[i*3+2]
        dx, dy, dz = func(x, y, z)
        deltas[i*3] = dx
        deltas[i*3+1] = dy
        deltas[i*3+2] = dz
    return deltas

def jaw_open(x, y, z):
    """Ouvrir la machoire — vertices sous le nez descendent."""
    if y < -0.15 and abs(z) > 0.3:
        strength = max(0, (-y - 0.15)) * 2
        return 0, -strength * 0.3, 0
    return 0, 0, 0

def mouth_smile(x, y, z):
    """Sourire — coins de la bouche montent."""
    if -0.35 < y < -0.1 and abs(x) > 0.2 and z > 0.4:
        return 0, 0.05, 0.02
    return 0, 0, 0

def mouth_funnel(x, y, z):
    """Bouche en O — levres se rapprochent du centre."""
    if -0.35 < y < -0.05 and z > 0.5:
        dist = math.sqrt(x*x + (y + 0.2)**2)
        if dist < 0.25:
            return -x * 0.15, -(y + 0.2) * 0.1, 0.05
    return 0, 0, 0

def eye_blink_l(x, y, z):
    """Clignement oeil gauche — paupiere descend."""
    if 0.1 < y < 0.35 and -0.5 < x < -0.1 and z > 0.4:
        return 0, -0.04, -0.02
    return 0, 0, 0

def eye_blink_r(x, y, z):
    """Clignement oeil droit."""
    if 0.1 < y < 0.35 and 0.1 < x < 0.5 and z > 0.4:
        return 0, -0.04, -0.02
    return 0, 0, 0

def brow_up(x, y, z):
    """Sourcils leves."""
    if 0.3 < y < 0.5 and abs(x) < 0.5 and z > 0.3:
        return 0, 0.06, 0
    return 0, 0, 0

def mouth_stretch(x, y, z):
    """Bouche etiree (i, e)."""
    if -0.35 < y < -0.05 and z > 0.5:
        return x * 0.12, 0, 0
    return 0, 0, 0

def mouth_lower_down(x, y, z):
    """Levre inferieure descend."""
    if -0.4 < y < -0.15 and abs(x) < 0.3 and z > 0.5:
        return 0, -0.08, 0
    return 0, 0, 0

def pack_buffer(data_list):
    """Pack multiple arrays into a single buffer, return views."""
    views = []
    offset = 0
    parts = []
    for data in data_list:
        raw = data.tobytes()
        # Align to 4 bytes
        padding = (4 - len(raw) % 4) % 4
        parts.append(raw + b'\x00' * padding)
        views.append({
            'buffer': 0,
            'byteOffset': offset,
            'byteLength': len(raw),
        })
        offset += len(raw) + padding
    return b''.join(parts), views

def build_glb(out_path):
    verts, norms, uvs, indices = make_sphere(32, 32)

    # Morph targets
    targets = {
        'jawOpen': make_morph_target(verts, jaw_open),
        'mouthSmile_L': make_morph_target(verts, mouth_smile),
        'mouthSmile_R': make_morph_target(verts, mouth_smile),
        'mouthFunnel': make_morph_target(verts, mouth_funnel),
        'eyeBlink_L': make_morph_target(verts, eye_blink_l),
        'eyeBlink_R': make_morph_target(verts, eye_blink_r),
        'browInnerUp': make_morph_target(verts, brow_up),
        'mouthStretch_L': make_morph_target(verts, mouth_stretch),
        'mouthStretch_R': make_morph_target(verts, mouth_stretch),
        'mouthLowerDown_L': make_morph_target(verts, mouth_lower_down),
        'mouthLowerDown_R': make_morph_target(verts, mouth_lower_down),
        'mouthPucker': make_morph_target(verts, mouth_funnel),
    }

    # Build buffer
    all_data = [verts, norms, uvs, indices]
    target_data = list(targets.values())
    all_data.extend(target_data)

    buffer_bin, buffer_views = pack_buffer(all_data)

    # Accessors
    n_verts = len(verts) // 3
    n_indices = len(indices)

    def vec3_bounds(arr):
        r = arr.reshape(-1, 3)
        return r.min(axis=0).tolist(), r.max(axis=0).tolist()

    v_min, v_max = vec3_bounds(verts)

    accessors = [
        {'bufferView': 0, 'componentType': 5126, 'count': n_verts, 'type': 'VEC3', 'min': v_min, 'max': v_max},  # POSITION
        {'bufferView': 1, 'componentType': 5126, 'count': n_verts, 'type': 'VEC3'},  # NORMAL
        {'bufferView': 2, 'componentType': 5126, 'count': n_verts, 'type': 'VEC2'},  # TEXCOORD
        {'bufferView': 3, 'componentType': 5123, 'count': n_indices, 'type': 'SCALAR'},  # indices
    ]

    # Morph target accessors
    morph_targets = []
    for i, (name, data) in enumerate(targets.items()):
        acc_idx = len(accessors)
        t_min, t_max = vec3_bounds(data)
        accessors.append({
            'bufferView': 4 + i,
            'componentType': 5126,
            'count': n_verts,
            'type': 'VEC3',
            'min': t_min,
            'max': t_max,
        })
        morph_targets.append({'POSITION': acc_idx})

    # Material — peau
    material = {
        'name': 'Skin',
        'pbrMetallicRoughness': {
            'baseColorFactor': [0.85, 0.68, 0.55, 1.0],
            'metallicFactor': 0.0,
            'roughnessFactor': 0.7,
        },
        'doubleSided': True,
    }

    gltf = {
        'asset': {'version': '2.0', 'generator': 'AuroraIA'},
        'scene': 0,
        'scenes': [{'nodes': [0]}],
        'nodes': [{'mesh': 0, 'name': 'Head', 'rotation': [0, 0, 0, 1], 'scale': [1, 1, 1]}],
        'meshes': [{
            'name': 'FaceMesh',
            'primitives': [{
                'attributes': {'POSITION': 0, 'NORMAL': 1, 'TEXCOORD_0': 2},
                'indices': 3,
                'material': 0,
                'targets': morph_targets,
            }],
            'extras': {
                'targetNames': list(targets.keys()),
            },
        }],
        'materials': [material],
        'accessors': accessors,
        'bufferViews': buffer_views,
        'buffers': [{'byteLength': len(buffer_bin)}],
    }

    json_str = json.dumps(gltf).encode('utf-8')
    while len(json_str) % 4 != 0:
        json_str += b' '

    total = 12 + 8 + len(json_str) + 8 + len(buffer_bin)

    with open(out_path, 'wb') as f:
        f.write(b'glTF')
        f.write(struct.pack('<I', 2))
        f.write(struct.pack('<I', total))
        f.write(struct.pack('<I', len(json_str)))
        f.write(struct.pack('<I', 0x4E4F534A))
        f.write(json_str)
        f.write(struct.pack('<I', len(buffer_bin)))
        f.write(struct.pack('<I', 0x004E4942))
        f.write(buffer_bin)

    print(f'GLB genere: {out_path} ({total} bytes)')
    print(f'Vertices: {n_verts}, Indices: {n_indices}')
    print(f'Morph targets: {list(targets.keys())}')

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'public/aurora-avatar.glb'
    build_glb(out)
