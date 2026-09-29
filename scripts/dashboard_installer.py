#!/usr/bin/env python3
"""Checked, reversible dashboard/telemetry patch. No third-party Python modules."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import time

EDITS = [
    ('        self._shares = deque()               # (monotonic_ts, assigned_share_difficulty)',
     '        self._shares = deque()               # (monotonic_ts, assigned_share_difficulty)\n'
     '        self._share_difficulty_history = deque(maxlen=512)'),
    ('        self._shares.append((now, assigned_diff))',
     '        self._shares.append((now, assigned_diff))\n'
     '        self._share_difficulty_history.append((self.last_share_wall, achieved_diff))'),
    ('            "best_diff": self.best_diff,',
     '            "best_diff": self.best_diff,\n'
     '            "recent_share_difficulties": list(self._share_difficulty_history),'),
]
NAMES = ('stratum.py', 'status.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def base_stratum(source):
    if 'recent_share_difficulties' not in source:
        return source
    for old, new in reversed(EDITS):
        if source.count(new) != 1:
            raise ValueError('Unrecognized share telemetry; refusing to overwrite it')
        source = source.replace(new, old, 1)
    return source


def dashboard_node(tree):
    matches = [n for n in tree.body if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == 'DASHBOARD_HTML' for t in n.targets)]
    if len(matches) != 1 or not isinstance(matches[0].value, ast.Constant):
        raise ValueError('Unsupported dashboard template')
    return matches[0]


def status_fingerprint(source):
    tree = ast.parse(source)
    tree.body.remove(dashboard_node(tree))
    def canonical(value):
        if isinstance(value, ast.AST):
            # Python 3.12 added empty type_params to ordinary definitions.
            # Keep nonempty parameters and every other semantic field.
            return [type(value).__name__, [[name, canonical(item)]
                    for name, item in ast.iter_fields(value)
                    if not (name == 'type_params' and item == [])]]
        if isinstance(value, list):
            return [canonical(item) for item in value]
        return [type(value).__name__, repr(value)]
    return digest(json.dumps(canonical(tree), ensure_ascii=True,
                             separators=(',', ':')).encode())


def patch(sources, html, compatibility):
    plain = base_stratum(sources[0])
    if digest(plain.encode()) != compatibility['stratum_sha256']:
        raise ValueError('Unsupported stratum.py; supported upstream is SoloBCH Forge 1.1.3')
    if status_fingerprint(sources[1]) != compatibility['status_ast_sha256']:
        raise ValueError('Unsupported status.py; only its dashboard template may differ from 1.1.3')
    if '<!doctype html>' not in html.lower() or 'recent_share_difficulties' not in html:
        raise ValueError('Missing or invalid dashboard.html')
    out = plain
    for old, new in EDITS:
        if out.count(old) != 1:
            raise ValueError('Missing or ambiguous telemetry insertion point')
        out = out.replace(old, new, 1)
    if base_stratum(out) != plain:
        raise ValueError('Telemetry patch failed reversibility check')
    tree = ast.parse(sources[1])
    node = dashboard_node(tree)
    lines = sources[1].splitlines(keepends=True)
    status = ''.join(lines[:node.lineno-1]) + 'DASHBOARD_HTML = ' + repr(html) + '\n' + ''.join(lines[node.end_lineno:])
    if status_fingerprint(status) != status_fingerprint(sources[1]):
        raise ValueError('Unexpected change outside the dashboard template')
    for name, source in zip(NAMES, (out, status)):
        compile(source, name, 'exec')
    return [out.encode(), status.encode()]


def atomic_write(path, contents):
    tmp = path.with_name(path.name + '.solobch-dashboard-tmp')
    st = path.stat() if path.exists() else None
    try:
        with tmp.open('wb') as f:
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
        if st:
            os.chmod(tmp, st.st_mode)
            if hasattr(os, 'chown'):
                os.chown(tmp, st.st_uid, st.st_gid)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def read_record(state, current):
    record = json.loads((state / 'current.json').read_text())
    if record.get('schema') != 1 or set(record.get('files', {})) != set(NAMES):
        raise ValueError('Invalid backup manifest')
    directory = (state / record['directory']).resolve()
    if directory.parent != state.resolve():
        raise ValueError('Invalid backup directory')
    originals = []
    for name, value in zip(NAMES, current):
        entry = record['files'][name]
        if digest(value) not in (entry['before'], entry['after']):
            raise ValueError(f'{name} changed since installation; refusing to overwrite it')
        data = (directory / name).read_bytes()
        if digest(data) != entry['before']:
            raise ValueError(f'{name} backup checksum mismatch')
        originals.append(data)
    return record, originals


def run(action, server, state, package):
    paths = [server / name for name in NAMES]
    current = [p.read_bytes() for p in paths]
    if action == 'restore':
        record, wanted = read_record(state, current)
        for name, data in zip(NAMES, wanted):
            compile(data.decode(), name, 'exec')
    else:
        compatibility = json.loads((package / 'compatibility.json').read_text())
        wanted = patch([x.decode() for x in current],
                       (package / 'dashboard.html').read_text(encoding='utf-8'), compatibility)
        if action == 'check':
            return 'Compatibility checks passed. No running source files changed.'
        if wanted == current:
            return 'This dashboard version is already installed. No files changed.'
        state.mkdir(parents=True, exist_ok=True)
        if (state / 'current.json').exists():
            prior = json.loads((state / 'current.json').read_text())
            if prior.get('phase') == 'prepared':
                raise ValueError('Incomplete prior update: run restore before installing again')
        directory = 'backup-' + str(time.time_ns())
        (state / directory).mkdir()
        record = {'schema': 1, 'phase': 'prepared', 'directory': directory, 'files': {}}
        for name, before, after in zip(NAMES, current, wanted):
            atomic_write(state / directory / name, before)
            record['files'][name] = {'before': digest(before), 'after': digest(after)}
        # Journal before touching source: restore can recover an interrupted update.
        atomic_write(state / 'current.json', json.dumps(record, indent=2).encode())
    changed = []
    try:
        for path, before, after in zip(paths, current, wanted):
            if before != after:
                atomic_write(path, after)
                changed.append((path, before))
        record['phase'] = 'restored' if action == 'restore' else 'installed'
        atomic_write(state / 'current.json', json.dumps(record, indent=2).encode())
    except BaseException:
        for path, before in reversed(changed):
            atomic_write(path, before)
        raise
    return 'Dashboard ' + ('restored' if action == 'restore' else 'installed') + '. Restart Forge to apply.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'install', 'restore'))
    parser.add_argument('--server', type=Path, default=Path('/app/server'))
    parser.add_argument('--state', type=Path, default=Path('/data/solobch-dashboard-backups'))
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        print(run(args.action, args.server, args.state, args.package))
    except Exception as exc:
        print('Stopped: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
