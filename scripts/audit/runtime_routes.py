import importlib
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


def main():
    root = Path(__file__).resolve().parents[2]
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'audit/cycle-01'
    sys.path.insert(0, str(root / 'application'))
    records, failures = [], []
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}), patch('threading.Thread.start'):
        from flask import Blueprint
        import bridge_server
        app = bridge_server.app
        for source in sorted((root / 'application/routes').glob('*.py')):
            try:
                module = importlib.import_module(f'routes.{source.stem}')
                for blueprint in vars(module).values():
                    if isinstance(blueprint, Blueprint) and blueprint.name not in app.blueprints:
                        app.register_blueprint(blueprint)
            except Exception as exc:
                failures.append({'file': str(source.relative_to(root)), 'error': type(exc).__name__, 'message': str(exc)})
        for rule in sorted(app.url_map.iter_rules(), key=lambda rule: (rule.rule, rule.endpoint)):
            handler = inspect.unwrap(app.view_functions[rule.endpoint])
            filename = inspect.getsourcefile(handler)
            records.append({'path': rule.rule, 'methods': sorted(rule.methods), 'endpoint': rule.endpoint,
                            'file': str(Path(filename).relative_to(root)) if filename and Path(filename).is_relative_to(root) else 'external',
                            'line': inspect.getsourcelines(handler)[1]})
        probes = []
        client = app.test_client()
        for method, route in [('GET', '/api/cli/version'), ('POST', '/api/cli/auth'), ('GET', '/api/cli/mission/nonexistent/status')]:
            response = client.open(route, method=method)
            probes.append({'method': method, 'path': route, 'status': response.status_code})
    output.mkdir(parents=True, exist_ok=True)
    (output / 'runtime-routes.json').write_text(json.dumps({'routes': records, 'failures': failures, 'unauthenticated_probes': probes}, indent=2) + '\n')
    print(json.dumps({'registered_routes': len(records), 'failures': failures, 'unauthenticated_probes': probes}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
