import trimesh

m1 = trimesh.creation.box()
m2 = trimesh.creation.icosphere()
m2.apply_translation([2,0,0])

scene = trimesh.Scene([m1, m2])
scene.export("test_scene.glb")
print("Done")
