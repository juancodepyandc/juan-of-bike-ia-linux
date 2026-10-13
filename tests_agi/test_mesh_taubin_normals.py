import importlib.util
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

MODULE = Path(__file__).resolve().parents[1] / "application/python-services/mesh_taubin.py"
spec = importlib.util.spec_from_file_location("taubin_normals_test", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_uv_split_surface_keeps_texture_and_continuous_reflection_normals(tmp_path):
    original = trimesh.creation.icosphere(subdivisions=2)
    vertices = original.vertices[original.faces].reshape(-1, 3)
    faces = np.arange(len(vertices)).reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    uv = np.tile([[0, 0], [1, 0], [0, 1]], (len(faces), 1))
    image = Image.new("RGB", (4, 4), (190, 140, 110))
    mesh.visual = trimesh.visual.texture.TextureVisuals(uv=uv,
        material=trimesh.visual.material.PBRMaterial(baseColorTexture=image,
            metallicFactor=0, roughnessFactor=.5))
    source, output = tmp_path / "source.glb", tmp_path / "smooth.glb"
    mesh.export(source)
    before = trimesh.load(source, force="mesh", process=False)
    result = module.taubin_smooth(source, output, iterations=2)
    assert result["ok"], result
    after = next(iter(trimesh.load_scene(output, process=False).geometry.values()))
    assert np.array_equal(before.faces, after.faces)
    assert np.array_equal(before.visual.uv, after.visual.uv)
    assert np.array_equal(np.asarray(before.visual.material.baseColorTexture),
                          np.asarray(after.visual.material.baseColorTexture))
    assert after.visual.material.metallicFactor == 0
    _, groups = np.unique(np.round(after.vertices, 7), axis=0, return_inverse=True)
    assert len(np.unique(groups)) < len(after.vertices)
    for group in np.unique(groups):
        normals = after.vertex_normals[groups == group]
        assert np.max(np.linalg.norm(normals - normals[0], axis=1)) < 1e-6
    assert np.allclose(np.linalg.norm(after.vertex_normals, axis=1), 1, atol=1e-6)


def test_already_shared_vertices_export_finite_unit_normals(tmp_path):
    source, output = tmp_path / "source.glb", tmp_path / "smooth.glb"
    trimesh.creation.icosphere(subdivisions=1).export(source)
    result = module.taubin_smooth(source, output, iterations=2)
    assert result["ok"], result
    mesh = next(iter(trimesh.load_scene(output, process=False).geometry.values()))
    assert np.all(np.isfinite(mesh.vertex_normals))
    assert np.allclose(np.linalg.norm(mesh.vertex_normals, axis=1), 1, atol=1e-6)


def test_decimation_material_transfer_preserves_reflection_and_normal_maps():
    path = MODULE.with_name('optimize_textured_mesh.py')
    spec = importlib.util.spec_from_file_location('optimize_material_test', path)
    optimizer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(optimizer)
    original = trimesh.creation.icosphere(subdivisions=1)
    image = Image.new('RGB', (4, 4), (170, 120, 100))
    normal = Image.new('RGB', (4, 4), (128, 128, 255))
    uv = np.zeros((len(original.vertices), 2))
    original.visual = trimesh.visual.texture.TextureVisuals(uv=uv,
        material=trimesh.visual.material.PBRMaterial(baseColorTexture=image,
            normalTexture=normal, metallicFactor=.8, roughnessFactor=.25))
    new = optimizer._preserved_texture_visual(original, uv, image)
    assert new.material is not original.visual.material
    assert new.material.metallicFactor == .8
    assert new.material.roughnessFactor == .25
    assert np.array_equal(np.asarray(new.material.normalTexture), np.asarray(normal))
    assert np.array_equal(np.asarray(new.material.baseColorTexture), np.asarray(image))
    new.material.roughnessFactor = .9
    assert original.visual.material.roughnessFactor == .25
