"""Host-independent reminder sweep: one periodic job, no per-user jobs to lose on restart."""
import logging
from datetime import datetime, timezone
from html import escape
from telegram.error import TelegramError
from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as M
import storage
from config.texts import get_text

logger = logging.getLogger(__name__)
MAX_LATE_MINUTES = 30


def due_notification(tracker, local_now):
    """True only when the scheduled local time has just arrived and no response exists."""
    if local_now.isoweekday() not in tracker.get('days_of_week', []):
        return False
    scheduled = tracker.get('notify_time')
    if not scheduled:
        return False
    try:
        hour, minute = map(int, scheduled.split(':'))
        if hour > 23 or minute > 59 or hour < 0 or minute < 0:
            return False
    except (ValueError, AttributeError):
        return False
    elapsed = local_now.hour * 60 + local_now.minute - (hour * 60 + minute)
    today = local_now.date().isoformat()
    return (0 <= elapsed < MAX_LATE_MINUTES and
            tracker.get('last_notification_date') != today and
            today not in tracker.get('history', {}))


def notification_keyboard(tracker_id, lang, day):
    return M([
        [B('✅ ' + ('Да' if lang == 'rus' else 'Yes'), callback_data=f'notif_yes_{tracker_id}_{day}')],
        [B('❌ ' + ('Нет' if lang == 'rus' else 'No'), callback_data=f'notif_no_{tracker_id}_{day}')],
        [B('⏸️ ' + ('Пропустить' if lang == 'rus' else 'Skip'), callback_data=f'notif_skip_{tracker_id}_{day}')],
    ])


async def sweep(context, now_utc=None):
    utc_now = now_utc or datetime.now(timezone.utc)
    for uid, ud in list(context.application.user_data.items()):
        if not ud.get('setup_complete'):
            continue
        try:
            settings = ud.get('settings', {})
            settings.setdefault('timezone_offset', ud.get('timezone_offset', 10800))
            local_now = storage.local_datetime_for_settings(settings, utc_now)
            lang = ud.get('settings', {}).get('language', 'rus')
            for tracker in ud.get('trackers', []):
                # This also closes past, unanswered scheduled days just after local midnight.
                before = len(tracker.get('history', {}))
                storage.reconcile_tracker(tracker, local_now.date())
                if len(tracker.get('history', {})) != before and hasattr(context.application, 'mark_data_for_update_persistence'):
                    context.application.mark_data_for_update_persistence(user_ids=[uid])
                if not due_notification(tracker, local_now):
                    continue
                today = local_now.date().isoformat()
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=get_text(lang, 'notification_text', NAME=escape(tracker['name'])),
                    parse_mode='HTML',
                    reply_markup=notification_keyboard(tracker['id'], lang, today),
                )
                tracker['last_notification_date'] = today
                if hasattr(context.application, 'mark_data_for_update_persistence'):
                    context.application.mark_data_for_update_persistence(user_ids=[uid])
                logger.info('Sent reminder to user=%s tracker=%s local_date=%s', uid, tracker['id'], today)
        except TelegramError as exc:
            logger.warning('Reminder send failed for uid=%s: %s', uid, exc)
        except Exception:
            logger.exception('Reminder sweep error for uid=%s', uid)
