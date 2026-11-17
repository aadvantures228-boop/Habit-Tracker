"""Inline navigation and habit actions."""
import logging
from datetime import datetime
from html import escape
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from telegram.ext import CallbackContext
from telegram.error import BadRequest
import storage
from utils import (create_tracker_detail_keyboard, create_today_goals_keyboard,
                   create_change_time_menu, create_change_timezone_menu,
                   create_notification_keyboard, create_tracker_list_keyboard)
from config.texts import get_text
from handlers import admin

logger = logging.getLogger(__name__)


def back(lang, callback):
    return [B(get_text(lang, 'back'), callback_data=callback)]


async def edit(query, text, keyboard=None):
    try:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
    except BadRequest as exc:
        if 'not modified' not in str(exc).lower():
            raise


async def _show_trackers_inline(update, context):
    query = update.callback_query
    uid = query.from_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    storage.reconcile_user(context, uid)
    trackers = storage.get_user_trackers(context, uid)
    keyboard = create_tracker_list_keyboard(trackers, lang, storage.user_local_datetime(context, uid).date()) if trackers else None
    await edit(query, get_text(lang, 'my_trackers') if trackers else get_text(lang, 'no_trackers'), keyboard)


async def _refresh_today_goals(update, context):
    query = update.callback_query
    uid = query.from_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    now = storage.user_local_datetime(context, uid)
    trackers = storage.get_trackers_for_today(context, uid)
    if not trackers:
        await edit(query, get_text(lang, 'no_goals_today'))
        return
    await edit(query, get_text(lang, 'today_goals', DATE=now.strftime('%d.%m.%Y')),
               create_today_goals_keyboard(trackers, now.date().isoformat(), lang))


async def _show_tracker(update, context, tracker_id, source):
    query = update.callback_query
    uid = query.from_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    storage.reconcile_user(context, uid)
    tracker = storage.get_tracker_by_id(context, uid, tracker_id)
    if not tracker:
        await edit(query, '⚠️ Трекер не найден.', M([back(lang, 'show_my_trackers_list')]))
        return
    history = tracker.get('history', {})
    today = storage.user_local_datetime(context, uid).date()
    streak = storage.calculate_tracker_streak(tracker, today)
    back_to = 'refresh_today_goals' if source == 'today' else 'show_my_trackers_list'
    keyboard, status = create_tracker_detail_keyboard(tracker_id, tracker.get('notify_time'), lang,
                                                     history.get(today.isoformat()), back_to, source)
    txt = get_text(lang, 'tracker_stats', NAME=escape(tracker['name']), TOTAL=len(history),
                   DONE=sum(s == 'done' for s in history.values()),
                   FAILED_COUNT=sum(s == 'failed' for s in history.values()),
                   SKIPPED_COUNT=sum(s == 'skipped' for s in history.values()), STREAK=streak)
    await edit(query, txt+status, keyboard)


async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data or ''
    uid = query.from_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    await query.answer()

    if data.startswith('admin_'):
        await admin.handle_admin_callback(update, context)
        return
    if data == 'go_home':
        storage.reset_user_input_states(context, uid)
        await edit(query, get_text(lang, 'start', TIMEZONE=storage.format_timezone(storage.get_user_timezone(context, uid))))
    elif data == 'setup_show_help':
        await edit(query, get_text(lang, 'help'), M([back(lang, 'setup_finish')]))
    elif data == 'setup_finish':
        await edit(query, '✅ ' + ('Настройка завершена.' if lang == 'rus' else 'Setup complete.'),
                   M([back(lang, 'setup_show_help')]))
    elif data == 'settings_language':
        await edit(query, get_text(lang, 'language_menu'), M([
            [B('Русский', callback_data='set_lang_ru')],
            [B('English', callback_data='set_lang_en')], back(lang, 'settings_menu_back')]))
    elif data in ('set_lang_ru', 'set_lang_en'):
        lang = 'rus' if data == 'set_lang_ru' else 'eng'
        storage.set_user_setting(context, uid, 'language', lang)
        from handlers.settings import show_settings_menu
        await show_settings_menu(update, context)
    elif data == 'settings_timezone':
        context.user_data.pop('awaiting_city_input', None)
        offset = storage.get_user_timezone(context, uid)
        await edit(query, get_text(lang, 'change_timezone', TIMEZONE=storage.format_timezone(offset)),
                   create_change_timezone_menu(offset, lang))
    elif data == 'settings_menu_back':
        context.user_data.pop('awaiting_activation_key', None)
        context.user_data.pop('awaiting_city_input', None)
        from handlers.settings import show_settings_menu
        await show_settings_menu(update, context)
    elif data == 'prompt_city':
        context.user_data['awaiting_city_input'] = True
        await edit(query, get_text(lang, 'enter_city'), M([back(lang, 'settings_timezone')]))
    elif data == 'settings_help':
        await edit(query, get_text(lang, 'help'), M([back(lang, 'settings_menu_back')]))
    elif data == 'activation_prompt':
        context.user_data['awaiting_activation_key'] = True
        await edit(query, ('🔑 Введите ключ ADV или используйте /k КЛЮЧ:' if lang == 'rus' else
                           '🔑 Enter ADV key or use /k KEY:'), M([back(lang, 'settings_menu_back')]))
    elif data in ('show_my_trackers_list', 'refresh_today_goals'):
        if data == 'show_my_trackers_list':
            await _show_trackers_inline(update, context)
        else:
            await _refresh_today_goals(update, context)
    elif data.startswith('view_tracker_'):
        parts = data.split('_')
        await _show_tracker(update, context, int(parts[2]), parts[3] if len(parts) > 3 else 'list')
    elif data.startswith('menu_change_time_'):
        context.user_data.pop('awaiting_time_input', None)
        parts = data.split('_')
        tid, source = int(parts[3]), (parts[4] if len(parts) > 4 else 'list')
        tracker = storage.get_tracker_by_id(context, uid, tid)
        if tracker:
            time = tracker.get('notify_time')
            await edit(query, get_text(lang, 'change_time_menu', TIME=time or get_text(lang,'disabled')),
                       create_change_time_menu(tid, time, lang, source))
    elif data.startswith('prompt_time_'):
        parts = data.split('_')
        tid, source = int(parts[2]), (parts[3] if len(parts) > 3 else 'list')
        context.user_data['awaiting_time_input'] = (tid, source)
        await edit(query, get_text(lang, 'enter_new_time'), M([back(lang, f'menu_change_time_{tid}_{source}')]))
    elif data.startswith('disable_time_'):
        parts = data.split('_')
        tid, source = int(parts[2]), (parts[3] if len(parts) > 3 else 'list')
        context.user_data.pop('awaiting_time_input', None)
        storage.update_tracker_time(context, uid, tid, None)
        await edit(query, get_text(lang, 'notifications_disabled'), M([back(lang, f'menu_change_time_{tid}_{source}')]))
    elif data.startswith('delete_tracker_confirm_'):
        parts = data.split('_')
        tid, source = int(parts[3]), (parts[4] if len(parts) > 4 else 'list')
        tracker = storage.get_tracker_by_id(context, uid, tid)
        if tracker:
            return_callback = 'show_my_trackers_list' if source == 'listing' else f'view_tracker_{tid}_{source}'
            await edit(query, get_text(lang, 'delete_confirm', NAME=escape(tracker['name'])), M([
                [B('✅ ' + ('Да' if lang == 'rus' else 'Yes'), callback_data=f'delete_tracker_yes_{tid}')],
                back(lang, return_callback)]))
    elif data.startswith('delete_tracker_yes_'):
        tid = int(data.split('_')[3])
        storage.delete_tracker(context, uid, tid)
        await _show_trackers_inline(update, context)
    elif data.startswith(('goal_mark_done_', 'goal_failed_', 'goal_skip_', 'goal_toggle_')):
        tid = int(data.rsplit('_', 1)[1])
        today = storage.user_local_datetime(context, uid).date()
        tracker = storage.get_tracker_by_id(context, uid, tid)
        if not tracker or today.isoweekday() not in tracker.get('days_of_week', []):
            await query.answer('⚠️ Привычка не запланирована на сегодня.', show_alert=True)
            return
        if data.startswith('goal_toggle_'):
            tracker.get('history', {}).pop(today.isoformat(), None)
        else:
            status = 'done' if data.startswith('goal_mark_done_') else 'failed' if data.startswith('goal_failed_') else 'skipped'
            storage.update_tracker_history(context, uid, tid, today.isoformat(), status)
        await _refresh_today_goals(update, context)
    elif data.startswith(('notif_yes_', 'notif_no_', 'notif_skip_')):
        # notification callback encodes the *scheduled date*: buttons must not mark a new day accidentally.
        parts = data.split('_')
        tid = int(parts[2])
        sent_date = parts[3] if len(parts) > 3 else None
        local_today = storage.user_local_datetime(context, uid).date().isoformat()
        day = sent_date or local_today
        if day != local_today:
            await edit(query, '⌛ ' + ('Это уведомление устарело.' if lang == 'rus' else 'This reminder has expired.'))
            return
        status = 'done' if data.startswith('notif_yes_') else 'failed' if data.startswith('notif_no_') else 'skipped'
        ok = storage.update_tracker_history(context, uid, tid, day, status)
        await edit(query, (get_text(lang, 'goal_marked_done') if status == 'done' else
                           get_text(lang, 'goal_skipped') if status == 'skipped' else
                           ('❌ Не выполнено.' if lang == 'rus' else '❌ Failed.')) if ok else '⚠️ Невозможно отметить.')
    elif data == 'ignore':
        return
    else:
        logger.warning('Unknown callback %s for user %s', data, uid)
        await query.answer('⚠️ Кнопка устарела. Откройте нужный раздел заново.', show_alert=True)
