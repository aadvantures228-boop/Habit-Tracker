"""Safe, opt-in PostgreSQL snapshot inspector / recovery tool for Habit Tracker.

Inspection never unpickles payloads and never modifies database contents.
Restore copies explicitly selected source to stable key, preserving old source
and saving an existing target to a separate backup row in the same transaction.

Run only with a PRIVATE bot-owned database. Stop all bot instances before restore.
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

from persistence_backend import PostgresPicklePersistence, select_storage


def get_backend():
    from config.env import BOT_TOKEN, DATA_PATH, DATABASE_URL
    backend, path, url = select_storage(DATA_PATH, DATABASE_URL)
    if backend != 'postgres':
        raise RuntimeError('Включено локальное файловое хранилище, PostgreSQL не настроен. '
                           'Проверьте DATABASE_URL в .env и переменные окружения.')
    if not BOT_TOKEN:
        raise RuntimeError('Отсутствует BOT_TOKEN в .env.')
    return PostgresPicklePersistence(url, BOT_TOKEN, str(path))


def inspect(conn, backend):
    """Read-only query; refuse to create a table automatically."""
    if conn.execute("SELECT to_regclass('habit_tracker_state')").fetchone()[0] is None:
        print('Таблица habit_tracker_state отсутствует в этой базе данных.')
        return []
    rows = conn.execute('''SELECT bot_key, octet_length(payload), updated_at
                           FROM habit_tracker_state ORDER BY updated_at DESC, bot_key''').fetchall()
    if not rows:
        print('Таблица есть, но снимков нет. Проверьте, ту ли базу вы подключили.')
        return []
    active = backend._bot_key
    print(f'Найдено снимков: {len(rows)}. Ключ активного бота: {active}')
    print('KEY                               BYTES     LAST_UPDATED                  TYPE')
    for key, size, updated in rows:
        status = ('CURRENT' if key == active else
                  'LEGACY_CURRENT_TOKEN' if key == backend._legacy_bot_key else
                  'OTHER_OR_OLD_TOKEN')
        updated_iso = updated.isoformat(timespec='seconds') if hasattr(updated, 'isoformat') else str(updated)
        print(f'{key:<33} {size:>9}  {updated_iso:<29} {status}')
    if any(key != active for key, _, _ in rows):
        print('Старые строки НЕ удаляйте. Если данные пропали после смены токена, '
              'старая версия может иметь статус OTHER_OR_OLD_TOKEN.')
    return rows


def export_snapshot(conn, key: str, destination: str):
    row = conn.execute('SELECT payload FROM habit_tracker_state WHERE bot_key = %s', (key,)).fetchone()
    if row is None:
        raise RuntimeError('Снимок с таким ключом не найден.')
    path = Path(destination).expanduser()
    # Exclusive create: never accidentally overwrite the only backup.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(bytes(row[0]))
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    print(f'Резервная копия снимка сохранена: {path} (храните приватно).')


def recover_snapshot(conn, backend, source_key: str, replace_existing: bool = False):
    """Copy a specific old row; never delete it; back up target on overwrite.

    Caller must stop bot before recovery. Transaction commits only on clean exit
    from psycopg connection context. Use SELECT FOR UPDATE to protect rows.
    """
    target_key = backend._bot_key
    if source_key == target_key:
        raise RuntimeError('Это уже активный ключ: восстановление не требуется.')
    source = conn.execute('SELECT payload FROM habit_tracker_state WHERE bot_key = %s FOR UPDATE',
                          (source_key,)).fetchone()
    if not source:
        raise RuntimeError('Указанный старый ключ не найден. Запустите диагностику.')
    target = conn.execute('SELECT payload FROM habit_tracker_state WHERE bot_key = %s FOR UPDATE',
                          (target_key,)).fetchone()
    source_blob = bytes(source[0])
    if target and bytes(target[0]) == source_blob:
        print('Активный снимок уже совпадает с выбранным: изменения не требуются.')
        return None
    if target and not replace_existing:
        raise RuntimeError('Активная запись уже существует и отличается. '
                           'Сначала сделайте резервную копию базы. Затем повторите '
                           'с --replace-existing, если точно выбрали нужный старый снимок.')
    backup_key = None
    if target:
        backup_key = 'bkp' + secrets.token_hex(14) + 'x'  # exactly 32 chars
        conn.execute('INSERT INTO habit_tracker_state (bot_key, payload) VALUES (%s, %s)',
                     (backup_key, bytes(target[0])))
    # Intentionally INSERT/UPSERT only the destination key; source survives.
    backend._insert_snapshot(conn, target_key, source_blob)
    print(f'Снимок {source_key} скопирован для текущего бота.')
    if backup_key:
        print(f'Предыдущая активная запись сохранена как отдельная резервная строка: {backup_key}')
    print('Старый источник не изменён. Перезапустите бота и проверьте привычки.')
    return backup_key


def main():
    parser = argparse.ArgumentParser(description='Диагностика и восстановление PostgreSQL Habit Tracker')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--recover', metavar='SOURCE_KEY', help='Скопировать конкретный старый снимок в активный ключ')
    action.add_argument('--export', nargs=2, metavar=('SOURCE_KEY', 'FILE'),
                        help='Сохранить .pkl резервную копию выбранного снимка, не перезаписывая файл')
    parser.add_argument('--replace-existing', action='store_true',
                        help='Разрешить восстановление поверх текущего снимка с автоматическим резервным копированием')
    args = parser.parse_args()
    if args.replace_existing and not args.recover:
        parser.error('--replace-existing можно использовать только с --recover')
    try:
        backend = get_backend()
        print('Режим хранения: PostgreSQL (адрес, пароль и токен не выводятся).')
        with backend._open_db() as conn:
            rows = inspect(conn, backend)
            if args.recover:
                if not rows:
                    raise RuntimeError('Снимков в базе нет.')
                recover_snapshot(conn, backend, args.recover, args.replace_existing)
            elif args.export:
                if not rows:
                    raise RuntimeError('Снимков в базе нет.')
                export_snapshot(conn, args.export[0], args.export[1])
    except Exception as exc:
        # Never print exception detail from driver, which may include DSN/password.
        if isinstance(exc, RuntimeError):
            print('Ошибка:', str(exc), file=sys.stderr)
        else:
            print('Ошибка работы с базой:', type(exc).__name__,
                  '(проверьте доступ, права и соединение; не публикуйте строку подключения)', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
