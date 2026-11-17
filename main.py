import logging
from telegram.ext import (Application, CommandHandler, MessageHandler, CallbackQueryHandler,
                          filters)
from config.env import BOT_TOKEN, ADMIN_ID, DATA_PATH, DATABASE_URL
from persistence_backend import make_persistence
from handlers import commands, messages, callbacks, admin
from handlers.add_tracker import add_tracker_conversation
from handlers.setup import first_setup_conversation
from notifications import sweep
from error_handlers import telegram_error_handler, configure_safe_logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
configure_safe_logging()


def build_application():
    if not BOT_TOKEN:
        raise RuntimeError('Set BOT_TOKEN in .env')
    if not ADMIN_ID:
        raise RuntimeError('Set ADMIN_ID in .env')
    persistence = make_persistence(DATA_PATH, DATABASE_URL, BOT_TOKEN)
    # Sending a message and receiving updates have separate HTTPX clients.
    # A longer TLS handshake deadline helps with slow proxies, but does not
    # compensate for an unreachable/broken proxy or network.
    app = (Application.builder().token(BOT_TOKEN)
           .connect_timeout(25).read_timeout(35).write_timeout(35)
           .get_updates_connect_timeout(25).get_updates_read_timeout(35)
           .persistence(persistence).build())
    app.add_error_handler(telegram_error_handler)
    app.add_handler(first_setup_conversation)
    app.add_handler(add_tracker_conversation)
    app.add_handler(CommandHandler('start', commands.start))
    app.add_handler(CommandHandler('cancel', commands.cancel))
    app.add_handler(CommandHandler('settings', commands.settings))
    app.add_handler(CommandHandler('today', commands.today))
    app.add_handler(CommandHandler('trackers', commands.trackers))
    app.add_handler(CommandHandler('k', commands.activate))
    app.add_handler(CommandHandler('admin', admin.admin_panel))
    app.add_handler(MessageHandler(filters.Document.ALL, admin.handle_admin_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle_reply))
    app.add_handler(CallbackQueryHandler(callbacks.button_callback))
    if app.job_queue is None:
        raise RuntimeError('Install python-telegram-bot[job-queue] for reminders')
    # One sweep at launch + every 30 seconds; operates on persistent user_data, not context.user_data.
    app.job_queue.run_repeating(sweep, interval=30, first=5, name='habit_reminder_sweep',
                                job_kwargs={'max_instances': 1, 'coalesce': True})
    return app


def main():
    logger.info('Starting Habit Tracker...')
    build_application().run_polling(allowed_updates=['message', 'callback_query'], drop_pending_updates=False)


if __name__ == '__main__':
    main()
