"""Boundary selection contracts; actual Blender repair is validated separately."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('mesh_boundary_repair',
    Path(__file__).resolve().parents[1] / 'application/python-services/mesh_boundary_repair.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def ring(size, offset=0):
    return [(offset + i, offset + (i + 1) % size) for i in range(size)]


def test_only_small_closed_unbranched_boundaries_are_selected():
    small = ring(4)
    oversized = ring(65, 100)
    open_chain = [(200,201),(201,202),(202,203)]
    branched = ring(3,300) + ring(3,302)
    loops = repair.small_boundary_loops(small + oversized + open_chain + branched,64)
    assert len(loops) == 1 and set(loops[0]) == set(range(4))


def test_multiple_small_holes_and_exact_size_limit_are_retained():
    loops = repair.small_boundary_loops(ring(3) + ring(64,100),64)
    assert sorted(map(len,loops)) == [3,64]
    assert set(index for loop in loops for index in loop) == set(range(67))
