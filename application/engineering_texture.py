"""UV-preserving static boolean previews, with provenance per material.

Manifold interpolates UV channels on original surfaces; cutter surfaces have
their own original IDs and deliberately receive a neutral material.
"""
import numpy as np
import trimesh


def textured_source(scene, scale):
    from manifold3d import Mesh, Manifold, Error
    vertices, faces, runs, ids, materials = [], [], [0], [], {}
    original_bounds = scene.to_mesh().bounds[0]
    offset = 0
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        geometry = scene.geometry[name].copy()
        geometry.apply_transform(transform)
        geometry.apply_translation(-original_bounds); geometry.apply_scale(scale)
        visual = geometry.visual
        uv = getattr(visual, 'uv', None)
        if uv is None:
            # Vertex/face colours are retained as a texture atlas by trimesh.
            visual = visual.to_texture() if hasattr(visual, 'to_texture') else visual
            uv = getattr(visual, 'uv', None)
        if uv is None:
            uv = np.zeros((len(geometry.vertices), 2))
        material = getattr(visual, 'material', None)
        material_list = getattr(material, 'materials', None) or [material]
        face_materials = getattr(visual, 'face_materials', None)
        if face_materials is None:
            face_materials = np.zeros(len(geometry.faces), dtype=int)
        vertices.append(np.column_stack([geometry.vertices, uv]))
        for index, mat in enumerate(material_list):
            selected = geometry.faces[np.asarray(face_materials) == index]
            if not len(selected):
                continue
            identity = Manifold.reserve_ids(1)
            faces.append(selected + offset); ids.append(identity)
            runs.append(runs[-1]+selected.size); materials[identity] = mat
        offset += len(geometry.vertices)
    data = Mesh(np.asarray(np.vstack(vertices), dtype=np.float32),
                np.asarray(np.vstack(faces), dtype=np.uint32),
                run_index=np.asarray(runs, dtype=np.uint32), run_original_id=np.asarray(ids, dtype=np.uint32))
    data.merge()  # weld positional seams without merging their different UVs
    result = Manifold(data)
    if result.status() != Error.NoError:
        raise ValueError('La topologie texturée ne peut pas être découpée avec conservation des UV.')
    return result, materials


def textured_pieces(scene, scale, pieces, joints, axis):
    from manifold3d import Mesh, Manifold
    source, materials = textured_source(scene, scale)
    from application.engineering_mesh import socket
    bounds = scene.to_mesh().extents * scale
    def volume(mesh):
        return Manifold(Mesh(np.asarray(mesh.vertices, dtype=np.float32),
                             np.asarray(mesh.faces, dtype=np.uint32)))
    # Replay cuts on the property-bearing source. Intersecting two identical
    # outside surfaces would make material provenance ambiguous.
    previews = []
    for index, part in enumerate(pieces):
        low, high = np.full(3,-1.), bounds+1
        low[axis], high[axis] = part.bounds[:,axis]
        box = trimesh.creation.box(high-low, trimesh.transformations.translation_matrix((high+low)/2))
        textured = source ^ volume(box)
        fragments = textured.decompose()
        if len(fragments) > 1:
            target = volume(part)
            textured = max(fragments, key=lambda fragment: (fragment ^ target).volume())
        for joint in joints:
            if index+1 in joint['pieces']:
                hole = socket(joint['hole_diameter_mm']/2,joint['depth_each_side_mm'],
                              joint['lead_in_mm'],joint['center_mm'],axis)
                textured = textured - volume(hole)
        result = textured.to_mesh()
        geometries = []
        for run, identity in enumerate(result.run_original_id):
            triangles = result.tri_verts[result.run_index[run]//3:result.run_index[run+1]//3]
            if not len(triangles):
                continue
            used, inverse = np.unique(triangles, return_inverse=True)
            properties = result.vert_properties[used]
            mesh = trimesh.Trimesh(properties[:,:3], inverse.reshape((-1,3)), process=False)
            if identity in materials:
                mesh.visual = trimesh.visual.texture.TextureVisuals(uv=properties[:,3:5], material=materials[identity])
            else:
                mesh.visual.face_colors = [190,196,204,255]
            geometries.append(mesh)
        if not geometries:
            raise ValueError('Aperçu texturé vide après découpe.')
        # Compare preview geometry to the actual printable volume, so a failed
        # texture operation cannot quietly masquerade as the completed part.
        joined = trimesh.util.concatenate(geometries)
        if abs(abs(joined.volume)-part.volume) > max(0.02,part.volume*1e-5):
            raise ValueError('Le volume de la vue texturée diffère de la pièce imprimable.')
        previews.append(geometries)
    return previews
