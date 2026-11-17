"""Centralized error reporting without exposing the bot token/DB password."""
from __future__ import annotations

import logging
import re
import traceback
from telegram.error import NetworkError

logger = logging.getLogger(__name__)

# Telegram API tokens appear in the URL of EVERY Bot API call.
_TOKEN_URL = re.compile(r"(https?://api\.telegram\.org/bot)[0-9]+:[A-Za-z0-9_-]+")
_DB_URL = re.compile(r"\bpostgres(?:ql)?://[^\s\"'<>]+", flags=re.IGNORECASE)


def redact_secrets(text: str) -> str:
    """Mask sensitive URLs before displaying an exception or a log message."""
    return _DB_URL.sub('postgresql://[REDACTED]',
                       _TOKEN_URL.sub(r'\1[REDACTED]', str(text)))


class SensitiveLogFilter(logging.Filter):
    def filter(self, record):
        # Render interpolation ourselves to avoid secret-bearing 'args' later.
        clean = redact_secrets(record.getMessage())
        record.msg, record.args = clean, ()
        return True


def configure_safe_logging():
    """Hide HTTP request URLs and mask credentials in our root console logger."""
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(f, SensitiveLogFilter) for f in handler.filters):
            handler.addFilter(SensitiveLogFilter())


async def telegram_error_handler(update, context):
    """PTB forwards network errors here instead of logging a huge traceback."""
    err = context.error
    kind = type(err).__name__
    if isinstance(err, NetworkError):
        logger.warning('Telegram connection problem (%s). Check network/proxy; action may not have reached Telegram.', kind)
        return
    # Keep a stack trace for actual code defects; remove secrets from the text.
    detail = ''.join(traceback.format_exception(type(err), err, err.__traceback__))
    logger.error('Unhandled bot error (%s):\n%s', kind, redact_secrets(detail))
