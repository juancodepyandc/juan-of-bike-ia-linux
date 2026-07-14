import pygltflib, copy
base="scratchpad/homme4_rough062.glb"
# variant A: strip KHR_materials_specular entirely (renderer that ignores ext => F0=0.04)
g=pygltflib.GLTF2().load(base)
g.materials[0].extensions={}
g.extensionsUsed=[]
g.save_binary("scratchpad/homme4_nospec.glb")
# variant B: corrected specularFactor 0.7 (skin F0 = 0.04*0.7 = 0.028, real skin)
g2=pygltflib.GLTF2().load(base)
g2.materials[0].extensions={"KHR_materials_specular":{"specularFactor":0.7}}
g2.save_binary("scratchpad/homme4_spec070.glb")
print("done")
