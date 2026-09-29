import ast
from collections import deque
import importlib.util
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch as mock_patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/dashboard_installer.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server = Path(self.tmp.name) / 'server'
        self.state = Path(self.tmp.name) / 'state'
        self.server.mkdir()
        self.originals = []
        for name in installer.NAMES:
            data = (ROOT / 'tests/fixtures' / name).read_text(encoding='utf-8').encode()
            (self.server / name).write_bytes(data)
            self.originals.append(data)

    def run_action(self, action):
        return installer.run(action, self.server, self.state, ROOT)

    def read_sources(self):
        return [(self.server / name).read_bytes() for name in installer.NAMES]

    def test_check_does_not_write(self):
        self.run_action('check')
        self.assertEqual(self.read_sources(), self.originals)
        self.assertFalse(self.state.exists())

    def test_install_and_restore_exactly(self):
        self.run_action('install')
        self.assertNotEqual(self.read_sources(), self.originals)
        self.run_action('restore')
        self.assertEqual(self.read_sources(), self.originals)

    def test_repeat_install_preserves_backup(self):
        self.run_action('install')
        manifest = (self.state / 'current.json').read_bytes()
        self.assertIn('already installed', self.run_action('install'))
        self.assertEqual((self.state / 'current.json').read_bytes(), manifest)
        self.run_action('restore')
        self.assertEqual(self.read_sources(), self.originals)

    def test_custom_dashboard_is_supported_and_restored(self):
        status = self.server / 'status.py'
        source = status.read_text(encoding='utf-8')
        tree = ast.parse(source)
        node = installer.dashboard_node(tree)
        lines = source.splitlines(keepends=True)
        custom = ''.join(lines[:node.lineno-1]) + "DASHBOARD_HTML = '<p>My old dashboard</p>'\n" + ''.join(lines[node.end_lineno:])
        status.write_text(custom, encoding='utf-8', newline='\n')
        before = status.read_bytes()
        self.run_action('install')
        self.run_action('restore')
        self.assertEqual(status.read_bytes(), before)

    def test_unsupported_stratum_refused(self):
        file = self.server / 'stratum.py'
        file.write_bytes(file.read_bytes() + b'\n# unrelated local customization\n')
        before = self.read_sources()
        with self.assertRaisesRegex(ValueError, 'Unsupported stratum'):
            self.run_action('install')
        self.assertEqual(before, self.read_sources())
        self.assertFalse(self.state.exists())

    def test_backend_change_in_status_refused(self):
        file = self.server / 'status.py'
        file.write_bytes(file.read_bytes().replace(b'REQUEST_TIMEOUT = 10.0', b'REQUEST_TIMEOUT = 99.0'))
        with self.assertRaisesRegex(ValueError, 'Unsupported status'):
            self.run_action('install')

    def test_restore_refuses_unrelated_change(self):
        self.run_action('install')
        file = self.server / 'status.py'
        file.write_bytes(file.read_bytes() + b'\n# later edit\n')
        before = self.read_sources()
        with self.assertRaisesRegex(ValueError, 'changed since installation'):
            self.run_action('restore')
        self.assertEqual(self.read_sources(), before)

    def test_restore_checks_backup_hash(self):
        self.run_action('install')
        record = json.loads((self.state / 'current.json').read_text())
        (self.state / record['directory'] / 'stratum.py').write_bytes(b'bad backup')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            self.run_action('restore')

    def test_transaction_rolls_back_second_write_failure(self):
        atomic = installer.atomic_write
        failed = False

        def fail_once(path, contents):
            nonlocal failed
            if path == self.server / 'status.py' and not failed:
                failed = True
                raise OSError('injected write failure')
            return atomic(path, contents)

        with mock_patch.object(installer, 'atomic_write', fail_once):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.run_action('install')
        self.assertEqual(self.read_sources(), self.originals)
        self.run_action('restore')
        self.assertEqual(self.read_sources(), self.originals)

    def test_restore_recovers_partial_interrupted_install(self):
        self.run_action('install')
        record = json.loads((self.state / 'current.json').read_text())
        record['phase'] = 'prepared'
        (self.state / 'current.json').write_text(json.dumps(record))
        (self.server / 'status.py').write_bytes(self.originals[1])
        with self.assertRaisesRegex(ValueError, 'Incomplete prior update'):
            self.run_action('install')
        self.run_action('restore')
        self.assertEqual(self.read_sources(), self.originals)

    def test_bounded_actual_difficulty_preserves_assigned_work(self):
        self.run_action('install')
        source = (self.server / 'stratum.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_record_accept')
        scope = {'time': time, 'SHARE_LOG_WINDOW': 3600}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<accept-method>', 'exec'), scope)
        calls = []

        def record(*args):
            calls.append(args)
            return False

        miner = SimpleNamespace(accepted=0, last_share_wall=None, best_diff=0,
            _shares=deque(), _share_difficulty_history=deque(maxlen=512), worker='demo-worker',
            jobs=SimpleNamespace(stats=SimpleNamespace(record_accept=record)))
        for i in range(600):
            scope['_record_accept'](miner, 10000+i, 5000)
        self.assertEqual(miner.accepted, 600)
        self.assertEqual(len(miner._share_difficulty_history), 512)
        self.assertEqual(miner._share_difficulty_history[-1][1], 10599)
        self.assertTrue(all(d == 5000 for _, d in miner._shares))
        self.assertEqual(calls[-1], (10599, 5000, 'demo-worker'))
        self.assertEqual(len(calls), 600)
        self.assertEqual(miner.best_diff, 10599)


if __name__ == '__main__':
    unittest.main()
