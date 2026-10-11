from pathlib import Path
import pytest
from application.asset_access import public_generated_asset


def test_public_generated_roots_and_private_sources(tmp_path):
    app=tmp_path/'app';app.mkdir();outside=tmp_path/'private.json';outside.write_text('fixture')
    output=app/'output';output.mkdir();(output/'image.png').write_bytes(b'fixture')
    assert public_generated_asset(output/'image.png',app)
    assert not public_generated_asset(app/'.aurora'/'devices.json',app)
    assert not public_generated_asset(app/'.env',app)
    assert not public_generated_asset(app/'../private.json',app)
    assert not public_generated_asset(output/'engineering-design'/'design_fixture'/'viewer.html',app)
    assert public_generated_asset(output/'engineering'/'eng_fixture'/'viewer.html',app)
    try:(output/'escape.png').symlink_to(outside)
    except OSError:pytest.skip('Creating symlinks is unavailable on this system.')
    assert not public_generated_asset(output/'escape.png',app)
