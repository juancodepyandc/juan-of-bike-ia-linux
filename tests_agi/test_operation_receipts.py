import json
from unittest.mock import patch

import pytest

from agi_core.operation_receipts import read_receipt, receipt_path, write_receipt


def test_complete_result_survives_loss_of_consumer_and_is_bound_to_actual_bytes(tmp_path):
    asset = tmp_path / 'asset.bin'
    asset.write_bytes(b'actual bytes')
    write_receipt(tmp_path, 'operation', 'original request', 'producer', {'ok': True}, [asset])
    assert read_receipt(tmp_path, 'operation', 'original request', 'producer')['artifacts'][0]['size_bytes'] == 12
    for request, producer in [('other goal', 'producer'), ('original request', 'other engine')]:
        with pytest.raises(ValueError, match='identity'):
            read_receipt(tmp_path, 'operation', request, producer)
    asset.write_bytes(b'changed bytes')
    with pytest.raises(ValueError, match='bytes'):
        read_receipt(tmp_path, 'operation', 'original request', 'producer')


def test_failed_engine_and_partial_files_never_count_as_completed(tmp_path):
    asset = tmp_path / 'partial.bin'; asset.write_bytes(b'partial')
    write_receipt(tmp_path, 'operation', 'goal', 'engine', {'ok': False}, [asset])
    with pytest.raises(ValueError, match='completion'):
        read_receipt(tmp_path, 'operation', 'goal', 'engine')


def test_interrupted_atomic_replace_preserves_previous_receipt(tmp_path):
    asset = tmp_path / 'asset.bin'; asset.write_bytes(b'bytes')
    original = write_receipt(tmp_path, 'operation', 'goal', 'engine', {'ok': True}, [asset])
    with patch('agi_core.operation_receipts.os.replace', side_effect=OSError('simulated crash')):
        with pytest.raises(OSError):
            write_receipt(tmp_path, 'operation', 'goal', 'engine', {'ok': False})
    assert json.loads(receipt_path(tmp_path, 'operation').read_text()) == original
    assert not list(receipt_path(tmp_path, 'operation').parent.glob('.receipt-*'))


def test_artifact_path_cannot_escape_operation_directory(tmp_path):
    root = tmp_path / 'run'; root.mkdir()
    outside = tmp_path / 'outside.bin'; outside.write_bytes(b'not this project')
    with pytest.raises(ValueError, match='outside'):
        write_receipt(root, 'operation', 'goal', 'engine', {'ok': True}, [outside])
