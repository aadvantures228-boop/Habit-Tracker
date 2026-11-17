"""Offline tests for selecting, saving, loading, and migrating persistence.

Does not use a network, real Telegram token, or live PostgreSQL. Run separately:
    python tests_persistence.py
"""
import pickle
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

# Run without PTB installed; emulate the file serialization that PTB provides.
try:
    from telegram.ext import PicklePersistence
except ImportError:
    tg = types.ModuleType('telegram')
    ext = types.ModuleType('telegram.ext')
    class PicklePersistence:
        def __init__(self, filepath, update_interval=30):
            self.filepath = Path(filepath)
            self.user_data = {}
            self.bot_data = {}
        def _dump_singlefile(self):
            self.filepath.write_bytes(pickle.dumps({'user_data': self.user_data, 'bot_data': self.bot_data}))
        def _load_singlefile(self):
            if self.filepath.exists():
                obj = pickle.loads(self.filepath.read_bytes())
                self.user_data = obj['user_data']
                self.bot_data = obj['bot_data']
    ext.PicklePersistence = PicklePersistence
    tg.ext = ext
    sys.modules['telegram'] = tg
    sys.modules['telegram.ext'] = ext

import persistence_backend as p


class FakePostgres:
    def __init__(self):
        self.rows = {}
        self.count = 0
        self.error = None

    def connect(self, url, **kwargs):
        assert url.startswith('postgresql://')
        assert kwargs['connect_timeout'] == 10
        if self.error:
            raise ValueError(self.error)
        self.count += 1
        return FakeConnection(self.rows)


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.found = None
        self.matches = []
        self.before = None
    def __enter__(self):
        self.before = dict(self.rows)
        return self
    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.rows.clear()
            self.rows.update(self.before)
        return False
    def execute(self, sql, params=None):
        self.found = None
        self.matches = []
        if sql.startswith('SELECT to_regclass'):
            self.found = 'habit_tracker_state'
        elif sql.startswith('SELECT COUNT(*)'):
            self.found = len(self.rows)
        elif sql.startswith('SELECT bot_key, octet_length'):
            from datetime import datetime, timezone
            self.matches = [(k, len(v), datetime(2026, 11, 16, tzinfo=timezone.utc))
                            for k, v in self.rows.items()]
        elif sql.startswith('SELECT bot_key, payload'):
            self.matches = list(self.rows.items())[:2]
            if self.matches:
                self.found = self.matches[0]
        elif sql.startswith('SELECT payload'):
            self.found = self.rows.get(params[0])
        elif sql.startswith('INSERT'):
            key, value = params
            if 'DO NOTHING' in sql:
                self.rows.setdefault(key, value)
            elif 'ON CONFLICT' in sql:
                self.rows[key] = value
            else:
                if key in self.rows:
                    raise AssertionError('Duplicate row')
                self.rows[key] = value
        elif 'CREATE TABLE' not in sql:
            raise AssertionError('Unexpected SQL ' + sql)
        return self
    def fetchone(self):
        if isinstance(self.found, tuple):
            return self.found
        return (self.found,) if self.found is not None else None
    def fetchall(self):
        return self.matches


def test_file_mode():
    assert p.select_storage('bot_data.pkl', '') == ('file', 'bot_data.pkl', '')
    with tempfile.TemporaryDirectory() as d:
        obj = p.make_persistence(str(Path(d) / 'nested' / 'bot.pkl'), '', '123456:fake-token')
        assert isinstance(obj, PicklePersistence)
        assert obj.filepath.parent.is_dir()


def test_postgres_url_in_data_path():
    url = 'postgresql://testuser:testsecret@somehost/db'
    backend, path, dsn = p.select_storage(url, '')
    assert (backend, path, dsn) == ('postgres', 'bot_data.pkl', url)
    assert p.select_storage('backup.pkl', url) == ('postgres', 'backup.pkl', url)
    assert p.select_storage('postgres://testuser@somehost/db', '')[0] == 'postgres'
    for bad in ('https://example.org/dump.pkl', 'sqlite:///storage.db'):
        try:
            p.select_storage(bad, '')
        except ValueError:
            pass
        else:
            raise AssertionError('DATA_PATH URL was not rejected')


def test_pg_roundtrip_and_legacy_migration():
    fake = FakePostgres()
    with patch.dict(sys.modules, {'psycopg': fake}):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / 'bot_data.pkl'
            old.write_bytes(pickle.dumps({'user_data': {1001: {'trackers': [{'id': 3}]}},
                                          'bot_data': {'activation_keys': {'hash': {}}}}))
            first = p.PostgresPicklePersistence('postgres://u:p@db/test', '123456:fake-token', str(old))
            first._load_singlefile()
            assert first.user_data[1001]['trackers'][0]['id'] == 3
            assert first.bot_data['activation_keys']
            assert len(fake.rows) == 1
            first.user_data[1001]['trackers'].append({'id': 4})
            first._dump_singlefile()
            # A restart without the local file restores the same user_data.
            old.unlink()
            second = p.PostgresPicklePersistence('postgresql://u:p@db/test', '123456:fake-token', str(old))
            second._load_singlefile()
            assert [t['id'] for t in second.user_data[1001]['trackers']] == [3, 4]
            assert second.bot_data['activation_keys']
            assert fake.count >= 3


def test_do_not_expose_password_on_connection_failure():
    fake = FakePostgres()
    fake.error = 'Failed: postgresql://u:secret-password@db/test'
    with patch.dict(sys.modules, {'psycopg': fake}):
        pg = p.PostgresPicklePersistence('postgresql://u:secret-password@db/test', '123456:other-fake-token', 'none.pkl')
        try:
            pg._load_singlefile()
        except RuntimeError as exc:
            assert 'secret-password' not in str(exc)
            assert 'PostgreSQL' in str(exc)
        else:
            raise AssertionError('Expected database connection failure')


def test_token_rotation_keeps_same_storage_key():
    a = p.PostgresPicklePersistence('postgresql://u:p@db/test', '12345:first', 'none.pkl')
    b = p.PostgresPicklePersistence('postgresql://u:p@db/test', '12345:rotated', 'none.pkl')
    assert a._bot_key == b._bot_key
    assert a._legacy_bot_key != b._legacy_bot_key


def test_automatic_migration_from_old_version():
    import hashlib
    fake = FakePostgres()
    token = '12345:original'
    legacy_key = hashlib.sha256(token.encode()).hexdigest()[:32]
    fake.rows[legacy_key] = pickle.dumps({'user_data': {1001: {'trackers': []}}, 'bot_data': {'registered_users': [1001]}})
    with patch.dict(sys.modules, {'psycopg': fake}):
        pg = p.PostgresPicklePersistence('postgresql://u:p@db/test', token, 'missing.pkl')
        pg._load_singlefile()
        assert pg._bot_key in fake.rows
        assert pg.user_data[1001]['trackers'] == []


def test_rotated_token_requires_explicit_optin_for_legacy_row():
    fake = FakePostgres()
    old_payload = pickle.dumps({'user_data': {1001: {'trackers': [{'id': 9}]}}, 'bot_data': {}})
    fake.rows['some-old-token-hash'] = old_payload
    with patch.dict(sys.modules, {'psycopg': fake}):
        with patch.dict('os.environ', {'MIGRATE_SINGLE_LEGACY_ROW': ''}):
            pg = p.PostgresPicklePersistence('postgresql://u:p@db/test', '12345:rotated', 'missing.pkl')
            try:
                pg._load_singlefile()
            except RuntimeError as exc:
                assert 'db_recovery.py' in str(exc)
            else:
                raise AssertionError('Must not silently create a new store')
            assert pg._bot_key not in fake.rows
        with patch.dict('os.environ', {'MIGRATE_SINGLE_LEGACY_ROW': '1'}):
            pg2 = p.PostgresPicklePersistence('postgresql://u:p@db/test', '12345:rotated', 'missing.pkl')
            pg2._load_singlefile()
            assert pg2.user_data[1001]['trackers'][0]['id'] == 9
            assert pg2._bot_key in fake.rows


def test_optin_does_not_migrate_shared_database():
    fake = FakePostgres()
    fake.rows['other-bot-1'] = b'other1'
    fake.rows['other-bot-2'] = b'other2'
    with patch.dict(sys.modules, {'psycopg': fake}):
        with patch.dict('os.environ', {'MIGRATE_SINGLE_LEGACY_ROW': '1'}):
            pg = p.PostgresPicklePersistence('postgresql://u:p@db/test', '12345:rotated', 'missing.pkl')
            try:
                pg._load_singlefile()
            except RuntimeError as exc:
                assert 'db_recovery.py' in str(exc)
            else:
                raise AssertionError('Must not silently use other bot snapshot')
            assert pg._bot_key not in fake.rows


def test_snapshot_survives_token_rotation():
    fake = FakePostgres()
    with patch.dict(sys.modules, {'psycopg': fake}):
        first = p.PostgresPicklePersistence('postgresql://u:p@db/test', '12345:first', 'none.pkl')
        first._load_singlefile()
        first.user_data = {1001: {'trackers': [{'id': 17}]}}
        first.bot_data = {'activation_keys': {'demo': {'used_by': None}}}
        first._dump_singlefile()
        second = p.PostgresPicklePersistence('postgresql://u:p@db/test', '12345:rotated', 'none.pkl')
        second._load_singlefile()
        assert second.user_data[1001]['trackers'][0]['id'] == 17
        assert 'demo' in second.bot_data['activation_keys']


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for test in tests:
        test()
        print('PASS', test.__name__)
    print(f'{len(tests)} persistence tests passed.')
