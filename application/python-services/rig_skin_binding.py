"""Blender-only binding verification and weight transfer from a disposable proxy.

Only weights are transferred to the authored mesh. No remeshing, welding,
decimation or atlas edits are applied to its geometry. Coverage is a necessary
binding check, not anatomical or collision certification.
"""
def bind_verified(mesh,rig):
    import bpy
    import bmesh
    def coverage(obj):
        deform={g.index for g in obj.vertex_groups if g.name in rig.data.bones and rig.data.bones[g.name].use_deform}
        return sum(any(g.group in deform and g.weight>1e-6 for g in v.groups) for v in obj.data.vertices)/max(len(obj.data.vertices),1)
    bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.object and bpy.context.object.mode!='OBJECT' else None
    def parent(obj):
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True)
        bpy.context.view_layer.objects.active=rig
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    parent(mesh)
    initial=coverage(mesh)
    if initial>=.999:return {'coverage':initial,'method':'native_heat'}
    print('PROGRESS:rig:liaison native insuffisante — calcul des poids sur copie de travail',flush=True)
    proxy=mesh.copy();proxy.data=mesh.data.copy();bpy.context.scene.collection.objects.link(proxy)
    try:
        proxy.parent=None;proxy.matrix_world=mesh.matrix_world.copy()
        for modifier in list(proxy.modifiers):proxy.modifiers.remove(modifier)
        for group in list(proxy.vertex_groups):proxy.vertex_groups.remove(group)
        bm=bmesh.new();bm.from_mesh(proxy.data)
        bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=max(max(mesh.dimensions)*1e-6,1e-8))
        bm.to_mesh(proxy.data);bm.free()
        bpy.ops.object.select_all(action='DESELECT');proxy.select_set(True);bpy.context.view_layer.objects.active=proxy
        if len(proxy.data.polygons)>120000:
            dec=proxy.modifiers.new('weight_proxy','DECIMATE');dec.ratio=120000/len(proxy.data.polygons)
            bpy.ops.object.modifier_apply(modifier=dec.name)
        parent(proxy)
        if coverage(proxy)<.999:
            print('PROGRESS:rig:résolution de peau — reconstruction fermée de la copie seule',flush=True)
            bpy.ops.object.select_all(action='DESELECT');proxy.select_set(True);bpy.context.view_layer.objects.active=proxy
            for modifier in list(proxy.modifiers):proxy.modifiers.remove(modifier)
            for group in list(proxy.vertex_groups):proxy.vertex_groups.remove(group)
            remesh=proxy.modifiers.new('closed_weight_proxy','REMESH');remesh.mode='VOXEL';remesh.voxel_size=max(max(mesh.dimensions)/400,1e-6)
            bpy.ops.object.modifier_apply(modifier=remesh.name)
            parent(proxy)
        if coverage(proxy)<.999:raise RuntimeError('Automatic weight solver did not bind enough of the working skin; original mesh preserved')
        print('PROGRESS:rig:transfert des poids calculés, géométrie et atlas natifs conservés',flush=True)
        for group in list(mesh.vertex_groups):mesh.vertex_groups.remove(group)
        for group in proxy.vertex_groups:mesh.vertex_groups.new(name=group.name)
        bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);bpy.context.view_layer.objects.active=mesh
        transfer=mesh.modifiers.new('verified_skin_transfer','DATA_TRANSFER');transfer.object=proxy
        transfer.use_vert_data=True;transfer.data_types_verts={'VGROUP_WEIGHTS'};transfer.vert_mapping='POLYINTERP_NEAREST'
        transfer.layers_vgroup_select_src='ALL';transfer.layers_vgroup_select_dst='NAME';transfer.mix_mode='REPLACE';transfer.mix_factor=1
        bpy.ops.object.modifier_apply(modifier=transfer.name)
        final=coverage(mesh)
        if final<.999:raise RuntimeError('Transferred binding incomplete: %.4f'%final)
        return {'coverage':final,'method':'proxy_surface_transfer','initial_coverage':initial}
    finally:
        data=proxy.data;bpy.data.objects.remove(proxy,do_unlink=True)
        if not data.users:bpy.data.meshes.remove(data)
