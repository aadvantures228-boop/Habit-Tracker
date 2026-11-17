"""Owner-only Telegram admin interface (weather-bot-inspired)."""
import asyncio
import io
import json
import logging
from html import escape
from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as M, InputFile
from telegram.error import TelegramError
from config.env import ADMIN_ID
from config.texts import get_text
import storage

logger = logging.getLogger(__name__)


def tr(lang, ru, en):
    return ru if lang == 'rus' else en


def back(lang, callback):
    return [B(tr(lang, '⬅️ Назад', '⬅️ Back'), callback_data=callback)]


async def edit(query, text, keyboard=None):
    await query.edit_message_text(text, reply_markup=M(keyboard or []) if keyboard is not None else None, parse_mode='HTML')


def admin_keyboard(lang):
    return [
        [B(tr(lang, '📢 Рассылка всем', '📢 Broadcast to all'), callback_data='admin_broadcast')],
        [B(tr(lang, '✉️ Сообщение пользователю', '✉️ Message a user'), callback_data='admin_message_id')],
        [B(tr(lang, '👥 Все пользователи', '👥 All users'), callback_data='admin_users_0')],
        [B(tr(lang, '🔑 Ключи ADV', '🔑 ADV keys'), callback_data='admin_keys')],
        [B(tr(lang, '📊 Статистика', '📊 Statistics'), callback_data='admin_view_data')],
        [B(tr(lang, '💾 Экспорт JSON', '💾 Export JSON'), callback_data='admin_export_data'),
         B(tr(lang, '📥 Импорт JSON', '📥 Import JSON'), callback_data='admin_import_data')],
    ]


async def admin_panel(update, context):
    user = update.effective_user
    if user.id != ADMIN_ID:
        if update.callback_query:
            await update.callback_query.answer('⛔ Доступ запрещён.', show_alert=True)
        elif update.message:
            await update.message.reply_text('⛔ Доступ запрещён.')
        return
    lang = storage.get_user_setting(context, user.id, 'language')
    text = get_text(lang, 'admin_panel')
    if update.callback_query:
        await edit(update.callback_query, text, admin_keyboard(lang))
    else:
        await update.message.reply_text(text, reply_markup=M(admin_keyboard(lang)), parse_mode='HTML')


def users_list(context):
    registered = set(int(uid) for uid in context.bot_data.get('registered_users', []))
    registered.update(int(uid) for uid in context.application.user_data if int(uid) > 0)
    return sorted(registered)


async def user_detail(query, context, target_id, page=0):
    lang = storage.get_user_setting(context, query.from_user.id, 'language')
    profile = context.application.user_data.get(target_id, {}).get('profile', {})
    ud = context.application.user_data.get(target_id, {})
    name = escape(profile.get('first_name') or '—')
    uname = escape(profile.get('username') or '—')
    level = 'ADV' if target_id == ADMIN_ID else ud.get('level', 'free').upper()
    text = (f'👤 <b>{target_id}</b>\n\n'
            f'{tr(lang,"Имя","Name")}: {name}\n'
            f'Username: @{uname}\n'
            f'{tr(lang,"Уровень","Level")}: {level}\n'
            f'{tr(lang,"Привычек","Habits")}: {len(ud.get("trackers", []))}\n'
            f'{tr(lang,"Регистрация","Registered")}: {escape(profile.get("created_at", "—")[:19])}')
    kb = [[B(tr(lang, '✉️ Написать', '✉️ Message'), callback_data=f'admin_dm_{target_id}_{page}')]]
    if target_id != ADMIN_ID:
        if level == 'ADV':
            kb.append([B(tr(lang, '⬇️ Сделать Free', '⬇️ Set Free'), callback_data=f'admin_free_{target_id}_{page}')])
        else:
            kb.append([B(tr(lang, '⬆️ Выдать ADV', '⬆️ Grant ADV'), callback_data=f'admin_adv_{target_id}_{page}')])
    kb.append(back(lang, f'admin_users_{page}'))
    await edit(query, text, kb)


async def handle_admin_callback(update, context):
    query = update.callback_query
    data = query.data
    if query.from_user.id != ADMIN_ID:
        await query.answer('⛔ Доступ запрещён.', show_alert=True)
        return
    lang = storage.get_user_setting(context, ADMIN_ID, 'language')
    context.user_data.pop('admin_input', None)
    if data in ('admin_panel', 'admin_back_to_panel'):
        await admin_panel(update, context)
    elif data.startswith('admin_users_'):
        page = max(0, int(data.rsplit('_', 1)[1]))
        users = users_list(context)
        size = 10
        max_page = max(0, (len(users)-1)//size)
        page = min(page, max_page)
        kb = []
        for uid in users[page*size:(page+1)*size]:
            profile = context.application.user_data.get(uid, {}).get('profile', {})
            nick = profile.get('first_name') or profile.get('username') or str(uid)
            kb.append([B(f'👤 {nick[:25]} ({uid})', callback_data=f'admin_user_{uid}_{page}')])
        pager = []
        if page: pager.append(B('◀️', callback_data=f'admin_users_{page-1}'))
        if page < max_page: pager.append(B('▶️', callback_data=f'admin_users_{page+1}'))
        if pager: kb.append(pager)
        kb.append(back(lang, 'admin_panel'))
        await edit(query, f'👥 <b>{tr(lang,"Пользователи","Users")}</b>: {len(users)}\n{page+1}/{max_page+1}', kb)
    elif data.startswith('admin_user_'):
        _, _, uid, page = data.split('_')
        await user_detail(query, context, int(uid), int(page))
    elif data.startswith(('admin_adv_', 'admin_free_')):
        _, level, uid, page = data.split('_')
        changed = storage.set_user_level(context, int(uid), 'adv' if level == 'adv' else 'free')
        if not changed:
            await query.answer('⚠️ Не удалось изменить уровень пользователя.', show_alert=True)
        await user_detail(query, context, int(uid), int(page))
    elif data.startswith('admin_dm_'):
        _, _, uid, page = data.split('_')
        context.user_data['admin_input'] = {'mode': 'dm', 'target_id': int(uid), 'page': int(page)}
        await edit(query, tr(lang, f'✉️ Введите сообщение для пользователя {uid}.\nОтмена: /cancel',
                             f'✉️ Enter a message for {uid}.\nCancel: /cancel'), [back(lang, f'admin_user_{uid}_{page}')])
    elif data == 'admin_message_id':
        context.user_data['admin_input'] = {'mode': 'dm_id'}
        await edit(query, tr(lang, '✉️ Введите Telegram ID получателя:', '✉️ Enter recipient Telegram ID:'), [back(lang, 'admin_panel')])
    elif data == 'admin_broadcast':
        context.user_data['admin_input'] = {'mode': 'broadcast'}
        await edit(query, get_text(lang, 'broadcast_mode'), [back(lang, 'admin_panel')])
    elif data == 'admin_keys':
        keys = list(context.bot_data.get('activation_keys', {}).values())
        used = sum(k.get('used_by') is not None for k in keys)
        await edit(query, f'🔑 ADV\n{tr(lang,"Всего ключей","Total keys")}: {len(keys)}\n'
                          f'{tr(lang,"Использовано","Used")}: {used}\n'
                          f'{tr(lang,"Свободно","Available")}: {len(keys)-used}',
                   [[B(tr(lang, '➕ Создать ключ', '➕ Generate key'), callback_data='admin_create_key')],
                    back(lang, 'admin_panel')])
    elif data == 'admin_create_key':
        key = storage.create_activation_key(context)
        await edit(query, tr(lang, '🔑 Новый одноразовый ключ ADV:', '🔑 New single-use ADV key:') +
                   f'\n\n<code>{escape(key)}</code>\n\n' +
                   tr(lang, 'Сохрани его: повторно показать нельзя.', 'Save it: cannot display again.'),
                   [back(lang, 'admin_keys')])
    elif data == 'admin_view_data':
        users = users_list(context)
        trackers = sum(len(u.get('trackers', [])) for u in context.application.user_data.values())
        adv = sum(1 for uid in users if uid == ADMIN_ID or context.application.user_data.get(uid, {}).get('level') == 'adv')
        await edit(query, f'📊 {tr(lang,"Пользователи","Users")}: {len(users)}\n'
                          f'🎯 {tr(lang,"Привычки","Habits")}: {trackers}\nADV: {adv}',
                   [back(lang, 'admin_panel')])
    elif data == 'admin_export_data':
        payload = {'version': 2, 'users': {str(uid): dict(ud) for uid, ud in context.application.user_data.items()},
                   'registered_users': users_list(context)}
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
        await query.message.reply_document(document=InputFile(io.BytesIO(raw), filename='habit_tracker_backup.json'),
                                            caption=tr(lang, '💾 Резервная копия данных. Храни её приватно.', '💾 Backup data. Keep it private.'))
        await edit(query, tr(lang, '✅ Экспорт завершён.', '✅ Export complete.'), [back(lang, 'admin_panel')])
    elif data == 'admin_import_data':
        context.user_data['admin_input'] = {'mode': 'import'}
        await edit(query, tr(lang, '📥 Отправь файл .json, экспортированный из этого бота.\n'
                                   'Импорт заменит данные совпадающих пользователей. /cancel — отмена.',
                                   '📥 Send the .json file exported by this bot.\n'
                                   'Import replaces matching user data. /cancel — cancel.'),
                   [back(lang, 'admin_panel')])
    else:
        await query.answer('Unknown action', show_alert=True)


async def handle_admin_text(update, context):
    """Return True if an admin input message was processed."""
    if update.effective_user.id != ADMIN_ID:
        return False
    state = context.user_data.get('admin_input')
    if not state:
        return False
    lang = storage.get_user_setting(context, ADMIN_ID, 'language')
    mode = state['mode']
    text = update.message.text or ''
    if mode == 'import':
        await update.message.reply_text(tr(lang, '📥 Пришли файл JSON документом.', '📥 Send a JSON document.'))
        return True
    if mode == 'dm_id':
        try:
            uid = int(text.strip())
            if uid <= 0 or uid not in users_list(context):
                raise ValueError
        except ValueError:
            await update.message.reply_text(tr(lang, '⚠️ Введите ID существующего пользователя.', '⚠️ Enter a known user ID.'))
            return True
        state.update(mode='dm', target_id=uid, page=0)
        await update.message.reply_text(tr(lang, f'✉️ Введите сообщение для {uid}:', f'✉️ Enter a message for {uid}:'))
        return True
    context.user_data.pop('admin_input', None)
    if mode == 'dm':
        uid = state['target_id']
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            result = tr(lang, f'✅ Сообщение отправлено пользователю {uid}.', f'✅ Message sent to {uid}.')
        except TelegramError as exc:
            logger.warning('DM failed to %s: %s', uid, exc)
            result = tr(lang, '❌ Отправить сообщение не удалось.', '❌ Message delivery failed.')
        await update.message.reply_text(result, reply_markup=M([back(lang, f'admin_user_{uid}_{state.get("page",0)}')]))
        return True
    if mode == 'broadcast':
        ok = fail = 0
        for uid in users_list(context):
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                ok += 1
            except TelegramError as exc:
                fail += 1
                logger.warning('Broadcast failed for %s: %s', uid, exc)
            await asyncio.sleep(0.04)
        await update.message.reply_text(tr(lang, f'📢 Доставлено: {ok}, ошибок: {fail}.',
                                               f'📢 Delivered: {ok}, failed: {fail}.'),
                                        reply_markup=M([back(lang, 'admin_panel')]))
        return True
    return False


async def handle_admin_document(update, context):
    if update.effective_user.id != ADMIN_ID or context.user_data.get('admin_input', {}).get('mode') != 'import':
        return
    lang = storage.get_user_setting(context, ADMIN_ID, 'language')
    document = update.message.document
    if document.file_size and document.file_size > 1024 * 1024:
        await update.message.reply_text('⚠️ Файл слишком большой (максимум 1 МБ).')
        return
    try:
        f = await document.get_file()
        content = await f.download_as_bytearray()
        if len(content) > 1024 * 1024:
            raise ValueError('file too large')
        payload = json.loads(bytes(content).decode('utf-8'))
        if not isinstance(payload, dict) or payload.get('version') != 2 or not isinstance(payload.get('users'), dict):
            raise ValueError('unknown backup format')
        restored = {}
        for uid, udata in payload['users'].items():
            user_id = int(uid)
            if user_id <= 0 or not isinstance(udata, dict) or not isinstance(udata.get('trackers', []), list):
                raise ValueError('invalid user payload')
            restored[user_id] = udata
        # PTB exposes user_data as a read-only mapping of mutable per-user dicts.
        # Restoring never-seen users requires its backing mapping on this version.
        backing = getattr(context.application, '_user_data', context.application.user_data)
        for uid, ud in restored.items():
            backing.setdefault(uid, {}).clear()
            backing[uid].update(ud)
        context.bot_data['registered_users'] = sorted(set(users_list(context)) | set(restored))
        if hasattr(context.application, 'mark_data_for_update_persistence'):
            context.application.mark_data_for_update_persistence(user_ids=list(restored))
        context.user_data.pop('admin_input', None)
        await update.message.reply_text(tr(lang, f'✅ Восстановлено пользователей: {len(restored)}.',
                                               f'✅ Restored users: {len(restored)}.'),
                                        reply_markup=M([back(lang, 'admin_panel')]))
    except (ValueError, UnicodeError, json.JSONDecodeError, TelegramError) as exc:
        logger.warning('Import rejected: %s', exc)
        await update.message.reply_text(tr(lang, '❌ Не удалось импортировать файл. Проверь формат.',
                                               '❌ Import failed. Check the format.'))
