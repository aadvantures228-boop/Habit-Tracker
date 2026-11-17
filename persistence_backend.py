"""Choose file persistence or an optional PostgreSQL-backed snapshot.

Only a bot-owned, trusted PicklePersistence file can be migrated. Never unpickle
content from unknown users; the SQL database must be private to this bot.
"""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from telegram.ext import PicklePersistence

logger = logging.getLogger(__name__)


def is_postgres_url(value: str) -> bool:
    """Distinguish a PostgreSQL DSN from a local path, including Windows paths."""
    return urlsplit(value).scheme.lower() in ('postgres', 'postgresql')


def select_storage(data_path: str, database_url: str) -> tuple[str, str, str]:
    """Return backend, safe file path, DSN; never use a DSN as a filename."""
    path = (data_path or 'bot_data.pkl').strip()
    url = (database_url or '').strip()
    if is_postgres_url(path):
        if url and path != url:
            raise ValueError('DATA_PATH и DATABASE_URL содержат разные PostgreSQL URL. Оставьте только DATABASE_URL.')
        url, path = path, 'bot_data.pkl'
        logger.warning('PostgreSQL URL обнаружен в DATA_PATH; переключаюсь на PostgreSQL. '
                       'На будущее используйте DATABASE_URL, а DATA_PATH оставьте именем .pkl файла.')
    if '://' in path:
        raise ValueError('DATA_PATH должен быть путём к .pkl файлу, а не URL.')
    if url and not is_postgres_url(url):
        raise ValueError('DATABASE_URL должен начинаться с postgresql:// или postgres://.')
    return ('postgres' if url else 'file'), path, url


class PostgresPicklePersistence(PicklePersistence):
    """Persist the same PTB pickle snapshot in PostgreSQL BYTEA.

    The regular PicklePersistence serializer runs against an isolated temporary
    file so Telegram objects get handled by PTB's own serializer. Database
    writes are transactions; database errors do not silently switch to an
    ephemeral file. This is for a *single* running polling process.
    """

    def __init__(self, database_url: str, bot_token: str, legacy_file_path: str):
        self._db_url = ("postgresql://" + database_url[len("postgres://"):]
                        if database_url.startswith('postgres://') else database_url)
        # Telegram bot ID (digits before ':') stays the same when BotFather
        # issues a new token. v0.2.1 keyed snapshots by the *full* token,
        # which made all saved data invisible after token rotation.
        bot_id = bot_token.split(':', 1)[0]
        if not bot_id.isdecimal():
            raise ValueError('Invalid BOT_TOKEN: expected numeric bot ID before colon.')
        self._bot_key = hashlib.sha256(f'telegram-bot:{bot_id}'.encode()).hexdigest()[:32]
        self._legacy_bot_key = hashlib.sha256(bot_token.encode('utf-8')).hexdigest()[:32]
        self._allow_single_row_migration = os.getenv('MIGRATE_SINGLE_LEGACY_ROW', '') == '1'
        self._allow_new_store = os.getenv('HABIT_ALLOW_NEW_STORE', '') == '1'
        self._require_existing = os.getenv('HABIT_REQUIRE_EXISTING_DATA', '') == '1'
        self._scratch = tempfile.TemporaryDirectory(prefix='habit_tracker_pg_')
        self._legacy_file = Path(legacy_file_path)
        self._loaded = False
        super().__init__(filepath=Path(self._scratch.name) / 'snapshot.pkl', update_interval=30)

    def _open_db(self):
        try:
            import psycopg
        except ImportError:
            raise RuntimeError('PostgreSQL требует psycopg. Выполните pip install -r requirements.txt') from None
        try:
            return psycopg.connect(self._db_url, connect_timeout=10)
        except Exception as exc:
            # Connection strings contain passwords. Do not include the driver
            # error/DSN in public logs or in exceptions pasted into chats.
            raise RuntimeError('Нет подключения к PostgreSQL (' + type(exc).__name__ + '). '
                               'Проверьте DATABASE_URL, доступность сервера и учётные данные.') from None

    @staticmethod
    def _ensure_table(conn):
        conn.execute('''CREATE TABLE IF NOT EXISTS habit_tracker_state (
            bot_key VARCHAR(32) PRIMARY KEY,
            payload BYTEA NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )''')

    def _read_blob(self):
        """Resolve the right snapshot; never silently choose an unrelated row.

        In v0.2.1 a snapshot used SHA256(full token). In v0.2.2 the key
        changed to SHA256(bot id). Rotating the token *before* upgrading
        means the old key can't be reconstructed from the new token.
        Refuse to create a blank store when there are unidentified rows.
        """
        try:
            with self._open_db() as conn:
                self._ensure_table(conn)
                row = conn.execute('SELECT payload FROM habit_tracker_state WHERE bot_key = %s',
                                   (self._bot_key,)).fetchone()
                if row:
                    count = conn.execute('SELECT COUNT(*) FROM habit_tracker_state').fetchone()[0]
                    if count > 1:
                        logger.warning('PostgreSQL содержит %s снимков. Если привычки пропали после '
                                       'обновления, запустите python db_recovery.py (только чтение).', count)
                    return bytes(row[0])

                # The v0.2.1 key is recoverable ONLY if the same token is used.
                old_row = conn.execute('SELECT payload FROM habit_tracker_state WHERE bot_key = %s',
                                       (self._legacy_bot_key,)).fetchone()
                if old_row:
                    # Do not overwrite a row created concurrently by another process.
                    conn.execute('''INSERT INTO habit_tracker_state (bot_key, payload) VALUES (%s, %s)
                                    ON CONFLICT (bot_key) DO NOTHING''',
                                 (self._bot_key, bytes(old_row[0])))
                    current = conn.execute('SELECT payload FROM habit_tracker_state WHERE bot_key = %s',
                                           (self._bot_key,)).fetchone()
                    logger.info('Мигрирована запись PostgreSQL v0.2.1 (токен не менялся).')
                    return bytes(current[0])

                count = conn.execute('SELECT COUNT(*) FROM habit_tracker_state').fetchone()[0]
                if self._allow_single_row_migration and count == 1:
                    # Explicit legacy opt-in from 0.2.2; kept for compatibility.
                    # Prefer db_recovery.py, which names the source key explicitly.
                    _, payload = conn.execute(
                        'SELECT bot_key, payload FROM habit_tracker_state LIMIT 2').fetchone()
                    conn.execute('''INSERT INTO habit_tracker_state (bot_key, payload) VALUES (%s, %s)
                                    ON CONFLICT (bot_key) DO NOTHING''',
                                 (self._bot_key, bytes(payload)))
                    current = conn.execute('SELECT payload FROM habit_tracker_state WHERE bot_key = %s',
                                           (self._bot_key,)).fetchone()
                    logger.warning('Восстановлена единственная старая запись; уберите '
                                   'MIGRATE_SINGLE_LEGACY_ROW=1 после проверки.')
                    return bytes(current[0])

                if count:
                    if not self._allow_new_store:
                        raise RuntimeError(
                            'PostgreSQL содержит предыдущие снимки, но ни один не соответствует '
                            'текущему боту. Чтобы не создавать новый пустой снимок рядом со старыми, '
                            'запуск остановлен. Запустите python db_recovery.py. '
                            'Если это новый бот в общей базе, задайте HABIT_ALLOW_NEW_STORE=1.')
                    logger.warning('Создаётся новый пустой снимок в PostgreSQL с %s чужими/старыми '
                                   'снимками (HABIT_ALLOW_NEW_STORE=1).', count)
                elif self._require_existing:
                    raise RuntimeError(
                        'В указанной PostgreSQL-базе нет сохранённых снимков. '
                        'Проверьте DATABASE_URL; отключите HABIT_REQUIRE_EXISTING_DATA '
                        'только для нового бота.')
                else:
                    logger.warning('PostgreSQL-база пуста. Начинаем новое хранилище. '
                                   'Если ожидались старые данные, проверьте DATABASE_URL.')
                return None
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError('Ошибка чтения PostgreSQL (' + type(exc).__name__ + ').') from None

    @staticmethod
    def _insert_snapshot(conn, bot_key, blob):
        conn.execute('''INSERT INTO habit_tracker_state (bot_key, payload) VALUES (%s, %s)
                    ON CONFLICT (bot_key) DO UPDATE SET
                        payload = EXCLUDED.payload, updated_at = NOW()''',
                     (bot_key, blob))

    def _write_blob(self, blob: bytes):
        try:
            with self._open_db() as conn:
                self._ensure_table(conn)
                self._insert_snapshot(conn, self._bot_key, blob)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError('Ошибка записи PostgreSQL (' + type(exc).__name__ + ').') from None

    def _load_singlefile(self):
        if self._loaded:
            return
        blob = self._read_blob()
        import_legacy = blob is None and self._legacy_file.is_file()
        if import_legacy:
            blob = self._legacy_file.read_bytes()
        if blob is not None:
            self.filepath.write_bytes(blob)
        super()._load_singlefile()
        if import_legacy:
            # Only import after PTB successfully decoded the locally trusted file.
            self._write_blob(blob)
            logger.info('Импортирован локальный bot_data.pkl в PostgreSQL.')
        self._loaded = True

    def _dump_singlefile(self):
        super()._dump_singlefile()
        self._write_blob(self.filepath.read_bytes())


def resolve_data_path(file_path: str) -> Path:
    """Keep relative .pkl paths stable across different working directories.

    Older releases used the current working directory. If both the old CWD
    file and project file exist, refuse to guess rather than hide user data.
    """
    path = Path(file_path).expanduser()
    if path.is_absolute():
        return path
    project_path = Path(__file__).resolve().parent / path
    cwd_path = Path.cwd() / path
    if project_path.resolve() == cwd_path.resolve():
        return project_path
    if project_path.is_file() and cwd_path.is_file():
        raise RuntimeError(
            'Найдены ДВА файла данных с одинаковым именем: в папке бота и в '
            'рабочем каталоге. Укажите абсолютный DATA_PATH, чтобы не потерять данные.')
    return cwd_path if cwd_path.is_file() and not project_path.is_file() else project_path


def make_persistence(data_path: str, database_url: str, bot_token: str):
    backend, file_path, url = select_storage(data_path, database_url)
    path = resolve_data_path(file_path)
    if backend == 'postgres':
        logger.info('Хранилище: PostgreSQL (без отображения адреса и пароля).')
        return PostgresPicklePersistence(url, bot_token, str(path))
    if not path.parent.is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
    logger.info('Хранилище: локальный PicklePersistence.')
    return PicklePersistence(filepath=path, update_interval=30)
