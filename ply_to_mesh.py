import open3d as o3d
import trimesh
import numpy as np
import sys

def main():
    ply_path = "application/output/3d/conversations/test_monobloc_world/clean_city.ply"
    out_path = "application/output/3d/conversations/test_monobloc_world/clean_city_solid.glb"
    
    print("Loading point cloud...")
    pcd = o3d.io.read_point_cloud(ply_path)
    
    # Check if normals exist, if not estimate them
    if not pcd.has_normals():
        print("Estimating normals...")
        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        pcd.orient_normals_consistent_tangent_plane(100)
    
    print("Running Poisson Surface Reconstruction...")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=10)
    
    # Filter low density vertices to remove artifacts
    vertices_to_remove = densities < np.quantile(densities, 0.05)
    mesh.remove_vertices_by_mask(vertices_to_remove)
    
    print(f"Mesh generated with {len(mesh.vertices)} vertices.")
    
    # Save to ply temporarily, then use trimesh to save as glb
    temp_ply = "temp_mesh.ply"
    o3d.io.write_triangle_mesh(temp_ply, mesh)
    
    print("Converting to GLB...")
    t_mesh = trimesh.load(temp_ply)
    
    # Flip Y and Z axes to match Blender/GLTF conventions if needed, but keeping as is for now
    
    t_mesh.export(out_path)
    print(f"Solid mesh saved to {out_path}")

if __name__ == "__main__":
    main()
