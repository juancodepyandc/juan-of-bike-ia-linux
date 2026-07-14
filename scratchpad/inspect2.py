import pygltflib
g=pygltflib.GLTF2().load("scratchpad/homme4_rough062.glb")
m=g.materials[0]
print("extUsed",g.extensionsUsed)
print("roughnessFactor", m.pbrMetallicRoughness.roughnessFactor)
print("metallicFactor", m.pbrMetallicRoughness.metallicFactor)
print("mrTexture", getattr(m.pbrMetallicRoughness.metallicRoughnessTexture,'index',None) if m.pbrMetallicRoughness.metallicRoughnessTexture else None)
print("extensions", m.extensions)
print("emissive", m.emissiveFactor)
