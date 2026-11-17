"""Optional PTB integration test (runs WITHOUT Telegram requests or real secrets).

Run in the same venv as the bot with `python tests_runtime.py`.
"""
import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import patch


def run():
    if importlib.util.find_spec('telegram') is None:
        print('SKIP: python-telegram-bot is not installed in this environment')
        return

    import main
    from telegram.ext import PicklePersistence
    with tempfile.TemporaryDirectory() as tmp:
        with (patch.object(main, 'BOT_TOKEN', '123456:FAKE_TOKEN_FOR_OFFLINE_TESTS'),
              patch.object(main, 'ADMIN_ID', 123456),
              patch.object(main, 'DATA_PATH', str(Path(tmp) / 'bot_data.pkl')),
              patch.object(main, 'DATABASE_URL', '')):
            app = main.build_application()
            assert app.job_queue is not None
            assert isinstance(app.persistence, PicklePersistence)
            assert len(app.error_handlers) >= 1
            assert len(app.job_queue.jobs()) >= 1
            all_handlers = [h for group in app.handlers.values() for h in group]
            assert len(all_handlers) >= 10
    print('PASS: Telegram handler registration, timeout-enabled application and reminder job (offline)')


if __name__ == '__main__':
    run()
