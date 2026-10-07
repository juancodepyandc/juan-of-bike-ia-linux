"""Fault injection checks byte preservation; no Blender or GPU quality claims."""
import importlib.util
from pathlib import Path
import subprocess
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('perfection_gate',
    Path(__file__).resolve().parents[1] / 'application/python-services/perfection_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_mutated_mesh_is_restored_after_failure_timeout_or_worse_geometry(tmp_path):
    import pytest
    for failure in ['failed', 'timeout', 'worse']:
        path = tmp_path / (failure + '.glb')
        original = b'original mesh bytes retained exactly'
        path.write_bytes(original)
        def repair(filename):
            Path(filename).write_bytes(b'partially rewritten mesh')
            if failure == 'timeout':
                raise subprocess.TimeoutExpired('fixture-blender', 1)
            return {'ok': failure != 'failed'}
        with patch.object(gate, 'reboucher', side_effect=repair), \
             patch.object(gate, 'audit_trous', return_value={'bords_ouverts': 501}):
            result = gate.reparer_trous_sans_perte(str(path), {'bords_ouverts': 500})
        assert result['ok'] is False
        assert result['original_restored'] is True
        assert path.read_bytes() == original
    assert not list(tmp_path.glob('*.repair-*.glb'))


def test_successful_repair_keeps_valid_replacement(tmp_path):
    path = tmp_path / 'model.glb'
    path.write_bytes(b'original')
    def repair(filename):
        Path(filename).write_bytes(b'repaired')
        return {'ok': True}
    with patch.object(gate, 'reboucher', side_effect=repair), \
         patch.object(gate, 'audit_trous', return_value={'bords_ouverts': 100}):
        result = gate.reparer_trous_sans_perte(str(path), {'bords_ouverts': 500})
    assert result['ok'] is True
    assert path.read_bytes() == b'repaired'
    assert not list(tmp_path.glob('*.repair-*.glb'))


def test_failed_backup_never_replaces_original_with_partial_copy(tmp_path):
    path = tmp_path / 'model.glb'
    path.write_bytes(b'original')
    def fail_copy(source, target):
        Path(target).write_bytes(b'incomplete backup')
        raise OSError('copy failed')
    with patch('shutil.copy2', side_effect=fail_copy), patch.object(gate, 'reboucher') as repair:
        result = gate.reparer_trous_sans_perte(str(path), {'bords_ouverts': 500})
    assert result['ok'] is False and result['original_preserved'] is True
    assert path.read_bytes() == b'original'
    repair.assert_not_called()


def test_failed_restore_retains_complete_backup_and_reports_failure(tmp_path):
    path = tmp_path / 'model.glb'
    path.write_bytes(b'original')
    def repair(filename):
        Path(filename).write_bytes(b'partial')
        return {'ok': False}
    with patch.object(gate, 'reboucher', side_effect=repair), patch.object(gate.os, 'replace', side_effect=OSError('restore failed')):
        result = gate.reparer_trous_sans_perte(str(path), {'bords_ouverts': 500})
    assert result['ok'] is False and result['original_preserved'] is False
    assert Path(result['retained_backup']).read_bytes() == b'original'
