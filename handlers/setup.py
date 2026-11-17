"""First-run language and timezone setup."""
import asyncio
from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as M
from telegram.ext import (ConversationHandler, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters)
import storage
from config.env import ADMIN_ID
from config.texts import get_text
from utils import create_main_keyboard
from weather_api import get_timezone_info_by_city

CHOOSE_LANG, CHOOSE_TIMEZONE = range(2)

async def start_setup(update, context):
    uid = update.effective_user.id
    storage.register_user(context, uid, update.effective_user)
    lang = storage.get_user_setting(context, uid, 'language')
    if context.user_data.get('setup_complete'):
        text = get_text(lang, 'start', TIMEZONE=storage.format_timezone(storage.get_user_timezone(context, uid)))
        await update.message.reply_text(text, reply_markup=create_main_keyboard(uid, ADMIN_ID, lang))
        return ConversationHandler.END
    await update.message.reply_text('🎯 Добро пожаловать в Habit Tracker!\nВыберите язык / Choose language:',
                                    reply_markup=M([[B('Русский', callback_data='setup_lang_rus')],
                                                    [B('English', callback_data='setup_lang_eng')]]))
    return CHOOSE_LANG

async def choose_lang_callback(update, context):
    query = update.callback_query
    await query.answer()
    lang = 'rus' if query.data == 'setup_lang_rus' else 'eng'
    storage.set_user_setting(context, query.from_user.id, 'language', lang)
    text = ('🌍 Укажите часовой пояс один раз: число UTC (например, 3, -5 или 5.5) '
            'или название города (Москва, London):' if lang == 'rus' else
            '🌍 Set your timezone once: UTC offset (e.g., 3, -5 or 5.5) '
            'or a city (Moscow, London):')
    await query.edit_message_text(text)
    return CHOOSE_TIMEZONE

async def choose_timezone(update, context):
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    raw = update.message.text.strip()
    offset = storage.parse_timezone_offset(raw)
    zone_name = None
    if offset is None:
        info = await asyncio.to_thread(get_timezone_info_by_city, raw)
        if info is not None:
            offset, zone_name = info
    if offset is None:
        await update.message.reply_text('⚠️ ' + ('Не удалось определить часовой пояс. Попробуйте число или другой город.' if lang == 'rus'
                                                 else 'Could not find timezone. Try an offset or another city.'))
        return CHOOSE_TIMEZONE
    storage.set_user_timezone(context, uid, offset, zone_name)
    context.user_data['setup_complete'] = True
    await update.message.reply_text('✅ ' + ('Настройка завершена!' if lang == 'rus' else 'Setup complete!') +
                                    '\n🌍 ' + storage.format_timezone(offset),
                                    reply_markup=M([[B('❓ ' + ('Инструкция' if lang == 'rus' else 'Help'),
                                                       callback_data='setup_show_help')]]))
    await update.message.reply_text('🎯 ' + ('Можешь создавать свои привычки.' if lang == 'rus' else 'You can now create habits.'),
                                    reply_markup=create_main_keyboard(uid, ADMIN_ID, lang))
    return ConversationHandler.END

async def cancel_setup(update, context):
    await update.message.reply_text('❌ ' + 'Настройка прервана. Для продолжения отправь /start.')
    return ConversationHandler.END

first_setup_conversation = ConversationHandler(
    entry_points=[CommandHandler('start', start_setup)],
    states={CHOOSE_LANG: [CallbackQueryHandler(choose_lang_callback, pattern=r'^setup_lang_(rus|eng)$')],
            CHOOSE_TIMEZONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_timezone)]},
    fallbacks=[CommandHandler('cancel', cancel_setup)], allow_reentry=True)
