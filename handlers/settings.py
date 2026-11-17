from telegram import Update
from utils import create_settings_keyboard
import storage
from config.texts import get_text

async def show_settings_menu(update: Update, context):
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    tz = storage.format_timezone(storage.get_user_timezone(context, uid))
    display_lang = 'Русский' if lang == 'rus' else 'English'
    text = get_text(lang, 'settings', LANGUAGE_NAME=display_lang, TIMEZONE=tz)
    text += '\n🔑 ' + ('Уровень' if lang == 'rus' else 'Tier') + ': ' + storage.get_user_level(context, uid).upper()
    kb = create_settings_keyboard(lang)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode='HTML')
