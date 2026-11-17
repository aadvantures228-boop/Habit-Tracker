"""Offline migration regression tests for v0.2.1 -> v0.2.2 -> v0.2.3.

Uses an in-memory PostgreSQL mock, never real passwords or a network.
"""
import contextlib
import io
import os
import pickle
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests_persistence import FakePostgres
import persistence_backend as p
import db_recovery as recovery


def test_rotated_token_existing_empty_new_row_recovery():
    """The precise missing test from 0.2.2: two rows, old full and new empty."""
    fake = FakePostgres()
    old_blob = pickle.dumps({'user_data': {101: {'trackers': [{'id': 11, 'name': 'Читать'}]}},
                             'bot_data': {'activation_keys': {'A': {'used_by': None}}}})
    blank = pickle.dumps({'user_data': {}, 'bot_data': {}})
    fake.rows['some_old_full_token_key'] = old_blob
    with patch.dict('sys.modules', {'psycopg': fake}):
        pg = p.PostgresPicklePersistence('postgresql://u:secret@db/test', '12345:rotated', 'none.pkl')
        fake.rows[pg._bot_key] = blank
        pg._load_singlefile()
        assert pg.user_data == {}  # Confirm the actual 0.2.2 failure is reproduced.
        with fake.connect('postgresql://u:secret@db/test', connect_timeout=10) as conn:
            state_before = dict(fake.rows)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rows = recovery.inspect(conn, pg)
            assert len(rows) == 2 and 'some_old_full_token_key' in out.getvalue()
            assert fake.rows == state_before  # Inspect is read-only.
            try:
                recovery.recover_snapshot(conn, pg, 'some_old_full_token_key')
            except RuntimeError as exc:
                assert '--replace-existing' in str(exc)
            else:
                raise AssertionError('Must refuse overwrite without permission')
        with fake.connect('postgresql://u:secret@db/test', connect_timeout=10) as conn:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                backup_key = recovery.recover_snapshot(conn, pg, 'some_old_full_token_key', True)
            assert len(backup_key) == 32
            assert fake.rows[backup_key] == blank
            assert fake.rows[pg._bot_key] == old_blob
            assert fake.rows['some_old_full_token_key'] == old_blob
            assert 'резервная' in out.getvalue()
        recovered = p.PostgresPicklePersistence('postgresql://u:secret@db/test', '12345:rotated2', 'none.pkl')
        recovered._load_singlefile()
        assert recovered.user_data[101]['trackers'][0]['id'] == 11
        assert 'activation_keys' in recovered.bot_data


def test_restore_without_existing_target():
    fake = FakePostgres()
    blob = pickle.dumps({'user_data': {50: {'trackers': [1]}}, 'bot_data': {}})
    fake.rows['oldsource'] = blob
    with patch.dict('sys.modules', {'psycopg': fake}):
        pg = p.PostgresPicklePersistence('postgresql://u:password@db/test', '12345:rotated', 'none.pkl')
        with fake.connect('postgresql://u:password@db/test', connect_timeout=10) as conn:
            with contextlib.redirect_stdout(io.StringIO()):
                assert recovery.recover_snapshot(conn, pg, 'oldsource') is None
        assert fake.rows[pg._bot_key] == blob
        assert fake.rows['oldsource'] == blob


def test_no_unknown_old_row_silent_boot():
    fake = FakePostgres()
    fake.rows['legacy_other_token'] = pickle.dumps({'user_data': {3: {}}, 'bot_data': {}})
    with patch.dict('sys.modules', {'psycopg': fake}):
        with patch.dict('os.environ', {'MIGRATE_SINGLE_LEGACY_ROW': '', 'HABIT_ALLOW_NEW_STORE': ''}):
            pg = p.PostgresPicklePersistence('postgresql://u:pass@db/test', '12345:new', 'none.pkl')
            try:
                pg._load_singlefile()
            except RuntimeError as exc:
                assert 'python db_recovery.py' in str(exc)
                assert 'pass@' not in str(exc)
            else:
                raise AssertionError('Must fail closed with old data')
            assert pg._bot_key not in fake.rows


def test_new_bot_shared_database_requires_optin():
    fake = FakePostgres()
    fake.rows['some-other-key'] = b'other-bot-data'
    with patch.dict('sys.modules', {'psycopg': fake}), \
         patch.dict('os.environ', {'HABIT_ALLOW_NEW_STORE': '1', 'MIGRATE_SINGLE_LEGACY_ROW': ''}):
        pg = p.PostgresPicklePersistence('postgresql://u:pass@db/test', '33333:new', 'none.pkl')
        pg._load_singlefile()
        assert pg._bot_key not in fake.rows  # Nothing saved until first actual update.
        pg.user_data = {77: {'trackers': [{'id': 12}]}}
        pg._dump_singlefile()
        assert pg._bot_key in fake.rows
        assert fake.rows['some-other-key'] == b'other-bot-data'


def test_strict_mode_empty_database():
    fake = FakePostgres()
    with patch.dict('sys.modules', {'psycopg': fake}), \
         patch.dict('os.environ', {'HABIT_REQUIRE_EXISTING_DATA': '1'}):
        pg = p.PostgresPicklePersistence('postgresql://u:pass@db/test', '12345:new', 'none.pkl')
        try:
            pg._load_singlefile()
        except RuntimeError as exc:
            assert 'нет сохранённых снимков' in str(exc)
        else:
            raise AssertionError('Should reject wrong empty DB')


def test_readonly_export_file_doesnt_overwrite():
    fake = FakePostgres()
    fake.rows['oldsource'] = b'example-sensitive-snapshot'
    with patch.dict('sys.modules', {'psycopg': fake}):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'archive.pkl'
            with fake.connect('postgresql://u:pass@db/test', connect_timeout=10) as conn:
                with contextlib.redirect_stdout(io.StringIO()):
                    recovery.export_snapshot(conn, 'oldsource', str(path))
                assert path.read_bytes() == fake.rows['oldsource']
                try:
                    recovery.export_snapshot(conn, 'oldsource', str(path))
                except FileExistsError:
                    pass
                else:
                    raise AssertionError('Must not overwrite backup')
            assert path.read_bytes() == b'example-sensitive-snapshot'


def test_file_path_cwd_backward_compatibility_and_ambiguity_guard():
    import uuid
    filename = 'test_habit_storage_' + uuid.uuid4().hex + '.pkl'
    project_path = Path(p.__file__).parent / filename
    with tempfile.TemporaryDirectory() as d:
        cwd_file = Path(d) / filename
        with patch('os.getcwd', return_value=d):
            assert p.resolve_data_path(filename) == project_path
            cwd_file.write_bytes(b'legacy')
            assert p.resolve_data_path(filename) == cwd_file
            try:
                project_path.write_bytes(b'new project file')
                try:
                    p.resolve_data_path(filename)
                except RuntimeError as exc:
                    assert 'ДВА файла' in str(exc)
                else:
                    raise AssertionError('Must reject ambiguous files')
            finally:
                project_path.unlink(missing_ok=True)


def test_current_source_no_recovery():
    fake = FakePostgres()
    with patch.dict('sys.modules', {'psycopg': fake}):
        pg = p.PostgresPicklePersistence('postgresql://u:pass@db/test', '12345:new', 'none.pkl')
        fake.rows[pg._bot_key] = b'payload'
        with fake.connect('postgresql://u:pass@db/test', connect_timeout=10) as conn:
            try:
                recovery.recover_snapshot(conn, pg, pg._bot_key, True)
            except RuntimeError as exc:
                assert 'активный ключ' in str(exc)
            else:
                raise AssertionError('Must not recover current from itself')


if __name__ == '__main__':
    tests = [v for name, v in sorted(globals().items()) if name.startswith('test_')]
    for test in tests:
        test()
        print('PASS', test.__name__)
    print(f'{len(tests)} recovery tests passed.')
