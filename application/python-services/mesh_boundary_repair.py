"""Select small simple boundary loops before asking Blender to fill holes.

Blender's holes_fill builds faces before applying its sides limit. Supplying
all mesh edges can therefore spend minutes traversing a large open boundary
that will be discarded anyway. Branches and oversized openings stay intact.
"""
from collections import defaultdict


def small_boundary_loops(edge_vertices, max_sides=64):
    if type(max_sides) is not int or max_sides < 3:
        raise ValueError('max_sides must be an integer of at least 3')
    adjacency = defaultdict(list)
    for index, (first, second) in enumerate(edge_vertices):
        adjacency[first].append(index)
        adjacency[second].append(index)
    seen, loops = set(), []
    for start in range(len(edge_vertices)):
        if start in seen:
            continue
        pending, edges, vertices = [start], [], set()
        seen.add(start)
        while pending:
            index = pending.pop()
            edges.append(index)
            for vertex in edge_vertices[index]:
                if vertex in vertices:
                    continue
                vertices.add(vertex)
                for neighbour in adjacency[vertex]:
                    if neighbour not in seen:
                        seen.add(neighbour)
                        pending.append(neighbour)
        if 3 <= len(edges) <= max_sides and all(len(adjacency[v]) == 2 for v in vertices):
            loops.append(edges)
    return loops


def repair_small_boundary_holes(bm, max_sides=64):
    import bmesh
    boundaries = [edge for edge in bm.edges if edge.is_boundary]
    loops = small_boundary_loops([tuple(edge.verts) for edge in boundaries], max_sides)
    candidates = [boundaries[index] for loop in loops for index in loop]
    result = bmesh.ops.holes_fill(bm, edges=candidates, sides=max_sides) if candidates else {'faces': []}
    return {'boundary_edges':len(boundaries), 'selected_edges':len(candidates),
            'selected_loops':len(loops), 'filled_faces':len(result['faces'])}
