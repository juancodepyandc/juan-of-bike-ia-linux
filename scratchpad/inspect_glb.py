import sys, json
import pygltflib
p = "/home/juan/AuroraIA/application/output/3d/generations/realpath_homme4_021313/realpath_homme4_021313_final_materials.glb"
g = pygltflib.GLTF2().load(p)
print("extensionsUsed:", g.extensionsUsed)
print("extensionsRequired:", g.extensionsRequired)
print("n_materials:", len(g.materials or []))
print("n_images:", len(g.images or []))
print("n_textures:", len(g.textures or []))
for i,m in enumerate(g.materials or []):
    print("=== material", i, m.name)
    pbr = m.pbrMetallicRoughness
    if pbr:
        print("  baseColorFactor:", pbr.baseColorFactor)
        print("  baseColorTexture:", getattr(pbr.baseColorTexture,'index',None) if pbr.baseColorTexture else None)
        print("  metallicFactor:", pbr.metallicFactor, "roughnessFactor:", pbr.roughnessFactor)
        print("  metallicRoughnessTexture:", getattr(pbr.metallicRoughnessTexture,'index',None) if pbr.metallicRoughnessTexture else None)
    print("  emissiveFactor:", m.emissiveFactor)
    print("  emissiveTexture:", getattr(m.emissiveTexture,'index',None) if m.emissiveTexture else None)
    print("  normalTexture:", getattr(m.normalTexture,'index',None) if m.normalTexture else None, "scale", getattr(m.normalTexture,'scale',None) if m.normalTexture else None)
    print("  occlusionTexture:", getattr(m.occlusionTexture,'index',None) if m.occlusionTexture else None)
    print("  alphaMode:", m.alphaMode, "doubleSided:", m.doubleSided)
    print("  extensions:", m.extensions)
print("=== images ===")
for i,im in enumerate(g.images or []):
    print(i, "name=",im.name, "mime=",im.mimeType, "bufferView=",im.bufferView)
print("=== extras keys ===", list((g.extras or {}).keys()) if isinstance(g.extras,dict) else g.extras)
