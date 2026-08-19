# Hunyuan 3D is licensed under the TENCENT HUNYUAN NON-COMMERCIAL LICENSE AGREEMENT
# except for the third-party components listed below.
# Hunyuan 3D does not impose any additional limitations beyond what is outlined
# in the repsective licenses of these third-party components.
# Users must comply with all terms and conditions of original licenses of these third-party
# components and must ensure that the usage of the third party components adheres to
# all relevant laws and regulations.

# For avoidance of doubts, Hunyuan 3D means the large language models and
# their software and algorithms, including trained model weights, parameters (including
# optimizer states), machine-learning model code, inference-enabling code, training-enabling code,
# fine-tuning enabling code and other elements of the foregoing made publicly available
# by Tencent in accordance with TENCENT HUNYUAN COMMUNITY LICENSE AGREEMENT.

import trimesh
import pymeshlab


def remesh_mesh(mesh_path, remesh_path):
    mesh = mesh_simplify_trimesh(mesh_path, remesh_path)


def mesh_simplify_trimesh(inputpath, outputpath, target_count=150000):
    ms = pymeshlab.MeshSet()
    if inputpath.endswith(".glb"):
        ms.load_new_mesh(inputpath, load_in_a_single_layer=True)
    else:
        ms.load_new_mesh(inputpath)
    
    # 1. Taubin smoothing removes marching cubes octree stepping ("effet carre") without shrinking volume
    try:
        ms.apply_coord_taubin_smoothing(lambda_=0.5, mu=-0.53, steps=3)
    except Exception:
        try:
            ms.apply_coord_laplacian_smoothing(steps=2)
        except Exception:
            pass

    # 2. Quadric edge collapse decimation preserving boundaries and normals
    try:
        if ms.current_mesh().face_number() > target_count:
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=int(target_count),
                preserveboundary=True,
                preservenormal=True
            )
    except Exception:
        pass

    # 3. Recompute smooth organic vertex normals
    try:
        ms.compute_normal_per_vertex()
    except Exception:
        pass

    out_obj = outputpath.replace(".glb", ".obj")
    ms.save_current_mesh(out_obj, save_textures=False)
    if outputpath.endswith(".obj"):
        return
    # If output was requested as another extension, convert
    courent = trimesh.load(out_obj, force="mesh", process=False)
    courent.export(outputpath)
