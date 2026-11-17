from telegram.ext import ConversationHandler
import storage
from utils import create_main_keyboard
from config.env import ADMIN_ID
from config.texts import get_text

async def start(update, context):
    from handlers.setup import start_setup
    await start_setup(update, context)

async def cancel(update, context):
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    storage.reset_user_input_states(context, uid)
    await update.message.reply_text('❌ ' + ('Все операции отменены.' if lang == 'rus' else 'All operations cancelled.'),
                                    reply_markup=create_main_keyboard(uid, ADMIN_ID, lang))
    return ConversationHandler.END

async def settings(update, context):
    from handlers.settings import show_settings_menu
    await show_settings_menu(update, context)

async def today(update, context):
    from handlers.messages import show_today_goals
    await show_today_goals(update, context)

async def trackers(update, context):
    from handlers.messages import show_my_trackers
    await show_my_trackers(update, context)

async def activate(update, context):
    uid = update.effective_user.id
    lang = storage.get_user_setting(context, uid, 'language')
    if not context.user_data.get('setup_complete'):
        await update.message.reply_text('⚠️ Сначала /start.')
        return
    if context.args:
        from handlers.messages import show_activation_result
        await show_activation_result(update, context, ' '.join(context.args))
    else:
        context.user_data['awaiting_activation_key'] = True
        await update.message.reply_text('🔑 ' + ('Введите ключ ADV:' if lang == 'rus' else 'Enter your ADV key:'))
