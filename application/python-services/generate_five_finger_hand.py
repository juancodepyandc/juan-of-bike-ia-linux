import bpy
import bmesh
import math
from mathutils import Vector, Matrix

def create_stylized_5finger_hand(is_right=False):
    bm = bmesh.new()
    
    # Palm base: rounded box
    # Dimensions: width(X)=0.07, thickness(Y)=0.035, length(Z)=0.075
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((0.07, 0.035, 0.075)), verts=bm.verts)
    
    # 5 Fingers: Thumb + Index + Middle + Ring + Pinky
    # Finger specs: (name, x_offset, length, radius, angle_z, angle_x)
    finger_specs = [
        ("Thumb",  -0.038, 0.055, 0.015, -45, 20),
        ("Index",  -0.024, 0.068, 0.013, -8,  0),
        ("Middle",  0.000, 0.076, 0.0135, 0,  0),
        ("Ring",    0.022, 0.070, 0.0125, 6,  0),
        ("Pinky",   0.040, 0.055, 0.011, 14,  0),
    ]
    
    for name, ox, flen, frad, ang_z, ang_x in finger_specs:
        if name == "Thumb":
            # Thumb comes from the side of the palm
            f_bm = bmesh.new()
            bmesh.ops.create_cone(f_bm, cap_ends=True, segments=12, radius1=frad, radius2=frad*0.75, depth=flen)
            # Translate and rotate
            rot = Matrix.Rotation(math.radians(ang_z), 4, 'Y') @ Matrix.Rotation(math.radians(ang_x), 4, 'X')
            bmesh.ops.transform(f_bm, matrix=rot, verts=f_bm.verts)
            bmesh.ops.translate(f_bm, vec=Vector((ox, 0.008, 0.005)), verts=f_bm.verts)
            # Merge into main bm
            for v in f_bm.verts:
                bm.verts.new(v.co)
            bm.verts.ensure_lookup_table()
            f_bm.free()
        else:
            # 4 fingers come from the top of the palm (Z+)
            f_bm = bmesh.new()
            bmesh.ops.create_cone(f_bm, cap_ends=True, segments=12, radius1=frad, radius2=frad*0.75, depth=flen)
            rot = Matrix.Rotation(math.radians(ang_z), 4, 'Y') @ Matrix.Rotation(math.radians(ang_x), 4, 'X')
            bmesh.ops.transform(f_bm, matrix=rot, verts=f_bm.verts)
            bmesh.ops.translate(f_bm, vec=Vector((ox, 0.0, 0.0375 + flen*0.5)), verts=f_bm.verts)
            for v in f_bm.verts:
                bm.verts.new(v.co)
            bm.verts.ensure_lookup_table()
            f_bm.free()
            
    mesh = bpy.data.meshes.new("HandMesh")
    bm.to_mesh(mesh)
    bm.free()
    
    obj = bpy.data.objects.new("HandObj", mesh)
    bpy.context.collection.objects.link(obj)
    
    # Select and Remesh with Voxel remesh to seamlessly weld all 5 fingers to palm!
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    bpy.ops.object.voxel_remesh()
    
    # Smooth modifier
    mod = obj.modifiers.new("Smooth", 'SMOOTH')
    mod.factor = 0.8
    mod.iterations = 6
    bpy.ops.object.modifier_apply(modifier="Smooth")
    
    # Subdivision
    mod_sub = obj.modifiers.new("Subsurf", 'SUBSURF')
    mod_sub.levels = 1
    bpy.ops.object.modifier_apply(modifier="Subsurf")
    
    bpy.ops.object.shade_smooth()
    return obj

bpy.ops.wm.read_factory_settings(use_empty=True)
hand = create_stylized_5finger_hand()
print(f"Created 5-finger stylized hand with {len(hand.data.vertices)} vertices.")
