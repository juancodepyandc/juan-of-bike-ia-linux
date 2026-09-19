import trimesh
import numpy as np

def main():
    print("Loading meshes...")
    try:
        caine = trimesh.load("application/output/3d/conversations/caine_scene/caine.glb")
        tent = trimesh.load("application/output/3d/conversations/caine_scene/tent.glb")
        ground = trimesh.load("application/output/3d/conversations/caine_scene/ground.glb")
    except Exception as e:
        print(f"Error loading meshes: {e}")
        return

    # Helper function to get the actual mesh or scene
    def get_mesh(obj):
        if isinstance(obj, trimesh.Scene):
            # concatenate all geometry into one mesh
            if len(obj.geometry) == 0:
                return trimesh.Trimesh()
            return trimesh.util.concatenate(list(obj.geometry.values()))
        return obj

    caine_mesh = get_mesh(caine)
    tent_mesh = get_mesh(tent)
    ground_mesh = get_mesh(ground)

    # 1. Setup Ground
    ground_mesh.apply_translation(-ground_mesh.bounds[0]) # Move to origin
    # Center ground on X and Y
    center = ground_mesh.centroid
    ground_mesh.apply_translation([-center[0], -center[1], 0])
    # Scale ground to be large
    ground_scale = 5.0 / max(ground_mesh.extents)
    ground_mesh.apply_scale(ground_scale)
    
    # 2. Setup Tent
    tent_mesh.apply_translation(-tent_mesh.bounds[0])
    tent_scale = 3.0 / max(tent_mesh.extents)
    tent_mesh.apply_scale(tent_scale)
    # Move tent to the back
    tent_mesh.apply_translation([0, 1.5, 0])
    
    # 3. Setup Caine
    caine_mesh.apply_translation(-caine_mesh.bounds[0])
    caine_scale = 1.0 / max(caine_mesh.extents)
    caine_mesh.apply_scale(caine_scale)
    # Move Caine to the front
    caine_mesh.apply_translation([0, -1.0, 0])
    
    # Create the scene
    scene = trimesh.Scene([ground_mesh, tent_mesh, caine_mesh])
    
    # Export
    out_path = "application/output/3d/conversations/caine_scene/caine_circus_composed.glb"
    scene.export(out_path)
    print(f"Exported scene to {out_path}")

if __name__ == "__main__":
    main()
