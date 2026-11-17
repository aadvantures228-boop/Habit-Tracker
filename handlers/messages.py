"""Reply keyboard and text-driven menus."""
import asyncio
from datetime import datetime
from html import escape
from telegram import InlineKeyboardMarkup as M, InlineKeyboardButton as B
from config.env import ADMIN_ID
from config.emojis import SETTINGS, EXTRA_DATA, TARGET, ADD, ADMIN, WARNING
from config.texts import get_text
from utils import create_tracker_list_keyboard, create_today_goals_keyboard, create_main_keyboard
from handlers.settings import show_settings_menu
from handlers.admin import admin_panel, handle_admin_text
from weather_api import get_timezone_info_by_city
import storage

MENU_BUTTONS_RUS = [f'{SETTINGS} Настройки', f'{EXTRA_DATA} Мои трекеры',
                    f'{TARGET} Цели на сегодня', f'{ADD} Добавить трекер', f'{ADMIN} Админ-панель']
MENU_BUTTONS_ENG = [f'{SETTINGS} Settings', f'{EXTRA_DATA} My trackers',
                    f"{TARGET} Today's goals", f'{ADD} Add tracker', f'{ADMIN} Admin panel']


def is_menu_button(text, lang):
    return text in MENU_BUTTONS_RUS + MENU_BUTTONS_ENG


async def show_my_trackers(update, context):
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    storage.reconcile_user(context, uid)
    trackers = storage.get_user_trackers(context, uid)
    keyboard = create_tracker_list_keyboard(trackers, lang, storage.user_local_datetime(context, uid).date()) if trackers else None
    await update.message.reply_text(get_text(lang, 'my_trackers') if trackers else get_text(lang, 'no_trackers'),
                                    reply_markup=keyboard, parse_mode='HTML')


async def show_today_goals(update, context):
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    trackers = storage.get_trackers_for_today(context, uid)
    now = storage.user_local_datetime(context, uid)
    await update.message.reply_text(get_text(lang, 'today_goals', DATE=now.strftime('%d.%m.%Y')) if trackers else get_text(lang, 'no_goals_today'),
                                    reply_markup=create_today_goals_keyboard(trackers, now.date().isoformat(), lang) if trackers else None,
                                    parse_mode='HTML')


async def handle_menu(update, context):
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    text = update.message.text.strip()
    storage.reset_user_input_states(context, uid)
    if text in (MENU_BUTTONS_RUS[0], MENU_BUTTONS_ENG[0]):
        await show_settings_menu(update, context)
    elif text in (MENU_BUTTONS_RUS[1], MENU_BUTTONS_ENG[1]):
        await show_my_trackers(update, context)
    elif text in (MENU_BUTTONS_RUS[2], MENU_BUTTONS_ENG[2]):
        await show_today_goals(update, context)
    elif text in (MENU_BUTTONS_RUS[3], MENU_BUTTONS_ENG[3]):
        # Reply keyboard entry point is handled by ConversationHandler.
        from handlers.add_tracker import start_add_tracker
        await start_add_tracker(update, context)
    elif text in (MENU_BUTTONS_RUS[4], MENU_BUTTONS_ENG[4]):
        await admin_panel(update, context)


async def handle_reply(update, context):
    uid = update.effective_user.id
    text = update.message.text.strip()
    lang = storage.get_user_setting(context, uid, 'language')
    storage.register_user(context, uid, update.effective_user)
    if is_menu_button(text, lang):
        await handle_menu(update, context)
        return
    if not context.user_data.get('setup_complete'):
        await update.message.reply_text('⚠️ ' + ('Завершите настройку командой /start.' if lang == 'rus' else 'Complete setup with /start.'))
        return
    if await handle_admin_text(update, context):
        return
    if context.user_data.get('awaiting_activation_key'):
        context.user_data.pop('awaiting_activation_key', None)
        await show_activation_result(update, context, text)
        return
    if 'awaiting_time_input' in context.user_data:
        state = context.user_data['awaiting_time_input']
        tid, source = state if isinstance(state, tuple) else (state, 'list')
        try:
            fmt = datetime.strptime(text, '%H:%M').strftime('%H:%M')
        except ValueError:
            await update.message.reply_text(get_text(lang, 'wrong_time_format'), parse_mode='HTML')
            return
        context.user_data.pop('awaiting_time_input', None)
        if not storage.get_tracker_by_id(context, uid, tid):
            await update.message.reply_text('⚠️ Привычка не найдена.')
            return
        storage.update_tracker_time(context, uid, tid, fmt)
        await update.message.reply_text(get_text(lang, 'time_changed', TIME=fmt), parse_mode='HTML',
                                        reply_markup=M([[B(get_text(lang,'back'), callback_data=f'menu_change_time_{tid}_{source}')]]))
        return
    if context.user_data.get('awaiting_city_input'):
        offset = storage.parse_timezone_offset(text)
        zone_name = None
        if offset is None:
            info = await asyncio.to_thread(get_timezone_info_by_city, text)
            if info is not None:
                offset, zone_name = info
        if offset is None:
            await update.message.reply_text(get_text(lang, 'city_not_found', CITY=escape(text)), parse_mode='HTML',
                                            reply_markup=M([[B(get_text(lang,'back'), callback_data='settings_timezone')]]))
            return
        context.user_data.pop('awaiting_city_input', None)
        storage.set_user_timezone(context, uid, offset, zone_name)
        await update.message.reply_text(get_text(lang, 'timezone_changed', TIMEZONE=storage.format_timezone(storage.get_user_timezone(context, uid))),
                                        reply_markup=M([[B(get_text(lang,'back'), callback_data='settings_timezone')]]))
        return
    await update.message.reply_text('⚠️ ' + ('Используйте кнопки меню.' if lang == 'rus' else 'Use the menu buttons.'),
                                    reply_markup=create_main_keyboard(uid, ADMIN_ID, lang))


async def show_activation_result(update, context, key):
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    result = storage.activate_key(context, uid, key)
    messages = {
        'activated': ('✅ Ключ принят! Уровень ADV активирован.', '✅ Key accepted! ADV is active.'),
        'invalid': ('❌ Ключ недействителен.', '❌ Invalid activation key.'),
        'used': ('❌ Этот ключ уже использован.', '❌ This key has already been used.'),
        'already_adv': ('ℹ️ У вас уже активирован ADV.', 'ℹ️ ADV is already active.'),
    }
    await update.message.reply_text(messages[result][0 if lang == 'rus' else 1])
