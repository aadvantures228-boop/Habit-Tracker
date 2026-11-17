"""Add a habit: name -> weekdays -> notification time; timezone is set only at onboarding."""
from datetime import datetime
from html import escape
from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as M
from telegram.ext import (ConversationHandler, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters)
import storage
from utils import create_days_keyboard, create_time_keyboard
from config.texts import get_text
from config.emojis import ADD

NAME, DAYS, TIME = range(3)


def clear_draft(context):
    for key in ('new_tracker_name', 'new_tracker_days', 'new_tracker_time'):
        context.user_data.pop(key, None)


async def start_add_tracker(update, context):
    clear_draft(context)
    lang = storage.get_user_setting(context, update.effective_user.id, 'language')
    await update.message.reply_text(get_text(lang, 'add_tracker_name'))
    return NAME


async def get_name(update, context):
    from handlers.messages import is_menu_button, handle_menu
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    text = update.message.text.strip()
    if is_menu_button(text, lang):
        clear_draft(context)
        if text.endswith(('Добавить трекер', 'Add tracker')):
            return await start_add_tracker(update, context)
        await handle_menu(update, context)
        return ConversationHandler.END
    if not text or len(text) > 60:
        await update.message.reply_text('⚠️ Название должно содержать от 1 до 60 символов.' if lang == 'rus' else '⚠️ Name must be 1–60 characters.')
        return NAME
    if storage.tracker_name_exists(context, uid, text):
        await update.message.reply_text('⚠️ Такая привычка уже существует.' if lang == 'rus' else '⚠️ This habit already exists.')
        return NAME
    context.user_data['new_tracker_name'] = text
    context.user_data['new_tracker_days'] = []
    await update.message.reply_text(get_text(lang, 'add_tracker_days', NAME=escape(text)),
                                    reply_markup=create_days_keyboard([], lang, True), parse_mode='HTML')
    return DAYS


async def back_to_name(update, context):
    query = update.callback_query
    await query.answer()
    lang = storage.get_user_setting(context, query.from_user.id, 'language')
    clear_draft(context)
    await query.edit_message_text(get_text(lang, 'add_tracker_name'))
    return NAME


async def toggle_day(update, context):
    query = update.callback_query
    await query.answer()
    lang = storage.get_user_setting(context, query.from_user.id, 'language')
    days = set(context.user_data.get('new_tracker_days', []))
    d = int(query.data.rsplit('_', 1)[1])
    if d in days: days.remove(d)
    else: days.add(d)
    context.user_data['new_tracker_days'] = sorted(days)
    await query.edit_message_reply_markup(reply_markup=create_days_keyboard(sorted(days), lang, True))
    return DAYS


async def select_days(update, context):
    query = update.callback_query
    await query.answer()
    lang = storage.get_user_setting(context, query.from_user.id, 'language')
    days = set(context.user_data.get('new_tracker_days', []))
    group = set(range(1, 6)) if query.data == 'select_weekdays' else set(range(1, 8))
    days = days - group if group <= days else days | group
    context.user_data['new_tracker_days'] = sorted(days)
    await query.edit_message_reply_markup(reply_markup=create_days_keyboard(sorted(days), lang, True))
    return DAYS


async def days_ready(update, context):
    query = update.callback_query
    lang = storage.get_user_setting(context, query.from_user.id, 'language')
    if not context.user_data.get('new_tracker_days'):
        await query.answer('⚠️ Выберите хотя бы один день.' if lang == 'rus' else '⚠️ Choose at least one day.', show_alert=True)
        return DAYS
    await query.answer()
    await query.edit_message_text(get_text(lang, 'add_tracker_time'), reply_markup=create_time_keyboard(lang))
    return TIME


async def back_to_days(update, context):
    query = update.callback_query
    await query.answer()
    lang = storage.get_user_setting(context, query.from_user.id, 'language')
    await query.edit_message_text(get_text(lang, 'add_tracker_days', NAME=escape(context.user_data.get('new_tracker_name',''))),
                                  reply_markup=create_days_keyboard(context.user_data.get('new_tracker_days', []), lang, True), parse_mode='HTML')
    return DAYS


async def get_time(update, context):
    from handlers.messages import is_menu_button, handle_menu
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    value = update.message.text.strip().lower()
    if is_menu_button(update.message.text, lang):
        clear_draft(context)
        if update.message.text.endswith(('Добавить трекер', 'Add tracker')):
            return await start_add_tracker(update, context)
        await handle_menu(update, context)
        return ConversationHandler.END
    if value in ('нет', 'no', 'отключить', 'disable'):
        notify_time = None
    else:
        try:
            parsed = datetime.strptime(value, '%H:%M')
            notify_time = parsed.strftime('%H:%M')
        except ValueError:
            await update.message.reply_text(get_text(lang, 'wrong_time_format'), parse_mode='HTML',
                                            reply_markup=create_time_keyboard(lang))
            return TIME
    name = context.user_data.get('new_tracker_name')
    days = context.user_data.get('new_tracker_days')
    if not name or not days:
        await update.message.reply_text('⚠️ Черновик устарел. Начните создание заново.')
        clear_draft(context)
        return ConversationHandler.END
    storage.add_tracker(context, uid, {'name': name, 'days_of_week': days, 'notify_time': notify_time})
    clear_draft(context)
    tz_str = storage.format_timezone(storage.get_user_timezone(context, uid))
    await update.message.reply_text(get_text(lang, 'tracker_created', NAME=escape(name),
                                            TIME_TEXT=notify_time or get_text(lang, 'disabled'), TIMEZONE=tz_str),
                                    parse_mode='HTML')
    return ConversationHandler.END


async def cancel_add(update, context):
    clear_draft(context)
    lang = storage.get_user_setting(context, update.effective_user.id, 'language')
    await update.message.reply_text(get_text(lang, 'cancel'))
    return ConversationHandler.END


add_tracker_conversation = ConversationHandler(
    entry_points=[CommandHandler('add_tracker', start_add_tracker),
                  MessageHandler(filters.Regex(r'^(➕ Добавить трекер|➕ Add tracker)$'), start_add_tracker)],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        DAYS: [CallbackQueryHandler(toggle_day, pattern=r'^toggle_day_[1-7]$'),
               CallbackQueryHandler(select_days, pattern=r'^(select_weekdays|select_all_days)$'),
               CallbackQueryHandler(days_ready, pattern=r'^days_ready$'),
               CallbackQueryHandler(back_to_name, pattern=r'^add_back_name$')],
        TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time),
               CallbackQueryHandler(back_to_days, pattern=r'^add_back_days$')],
    },
    fallbacks=[CommandHandler('cancel', cancel_add)],
    allow_reentry=True,
)
