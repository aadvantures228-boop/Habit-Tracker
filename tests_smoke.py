"""Offline smoke tests; use `python tests_smoke.py`, no Telegram token required."""
import asyncio
import sys
import types
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace as NS

# Provide small PTB shells only if the real dependency isn't available.
try:
    import telegram
except ImportError:
    tg = types.ModuleType('telegram')
    ext = types.ModuleType('telegram.ext')
    err = types.ModuleType('telegram.error')
    class TelegramError(Exception): pass
    class BadRequest(TelegramError): pass
    class NetworkError(TelegramError): pass
    class TimedOut(NetworkError): pass
    err.BadRequest = BadRequest
    err.TelegramError = TelegramError
    err.NetworkError = NetworkError
    err.TimedOut = TimedOut
    tg.error = err
    class Button:
        def __init__(self, text, callback_data): self.text, self.callback_data = text, callback_data
    class Markup:
        def __init__(self, inline_keyboard): self.inline_keyboard = inline_keyboard
    class ReplyMarkup:
        def __init__(self, keyboard, **kw): self.keyboard = keyboard
    class InputFile:
        def __init__(self, obj, filename): self.obj, self.filename = obj, filename
    tg.InlineKeyboardButton = Button
    tg.InlineKeyboardMarkup = Markup
    tg.ReplyKeyboardMarkup = ReplyMarkup
    tg.InputFile = InputFile
    tg.Update = type('Update', (), {})
    ext.CallbackContext = object
    ext.ConversationHandler = type('Conv', (), {'END': -1, '__init__': lambda self, *a, **kw: None})
    for key in ('CommandHandler', 'MessageHandler', 'CallbackQueryHandler'):
        setattr(ext, key, type(key, (), {'__init__': lambda self, *a, **kw: None}))
    class F:
        def __and__(self, other): return self
        def __invert__(self): return self
        def __getattr__(self, _): return self
        def Regex(self, *_): return self
    ext.filters = F()
    sys.modules['telegram'] = tg
    sys.modules['telegram.ext'] = ext
    sys.modules['telegram.error'] = err

import storage
import notifications
from utils import create_tracker_list_keyboard, create_tracker_detail_keyboard
from handlers.callbacks import button_callback
from handlers.admin import handle_admin_callback

class Context:
    def __init__(self, uid=111):
        self.bot_data = {'registered_users': []}
        self.application = NS(user_data={uid: {}}, mark_data_for_update_persistence=lambda **kw: None)
        self.user_data = self.application.user_data[uid]
        self.job_queue = None
        self.messages = []
        async def send_message(**kw): self.messages.append(kw)
        self.bot = NS(send_message=send_message)
        self.user = NS(id=uid, username='test', first_name='Test')
        storage.register_user(self, uid, self.user)
        self.user_data['setup_complete'] = True
        storage.set_user_timezone(self, uid, 3*3600)

class Query:
    def __init__(self, uid, data):
        self.from_user = NS(id=uid)
        self.data = data
        self.text = None
        self.markup = None
        self.answers = []
    async def answer(self, *a, **kw): self.answers.append((a, kw))
    async def edit_message_text(self, text, reply_markup=None, **kw):
        self.text = text
        self.markup = reply_markup


def cbs(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_midnight_and_streak():
    t = {'days_of_week': [1, 3, 5], 'history': {'2026-11-09':'done', '2026-11-11':'done'},
         'created_at': '2026-11-09'}
    assert storage.calculate_tracker_streak(t, date(2026,11,12)) == 2  # Thursday off
    assert storage.calculate_tracker_streak(t, date(2026,11,13)) == 2  # Friday still pending
    storage.reconcile_tracker(t, date(2026,11,14))
    assert t['history']['2026-11-13'] == 'failed'
    assert storage.calculate_tracker_streak(t, date(2026,11,14)) == 0
    t['history']['2026-11-13'] = 'done'
    assert storage.calculate_tracker_streak(t, date(2026,11,14)) == 3
    t['history']['2026-11-13'] = 'skipped'
    assert storage.calculate_tracker_streak(t, date(2026,11,14)) == 0


def test_timezone():
    assert storage.format_timezone(19800) == 'UTC+5:30'
    assert storage.parse_timezone_offset('UTC+5:30') == 19800
    assert storage.parse_timezone_offset('-3.5') == -12600
    assert storage.parse_timezone_offset('25') is None
    instant = datetime(2026, 11, 16, 22, 30, tzinfo=timezone.utc)
    assert storage.local_datetime(10800, instant).date() == date(2026, 11, 17)
    assert storage.local_datetime(-18000, instant).date() == date(2026, 11, 16)


def test_legacy_and_dedupe():
    ctx = Context()
    storage.set_user_timezone(ctx, 111, 0)
    assert ctx.user_data['settings']['timezone_offset'] == 0
    assert ctx.user_data['timezone_offset'] == 0
    assert storage.get_user_timezone(ctx, 111) == 0
    storage.add_tracker(ctx, 111, {'name':'Read','days_of_week':[1,2,3,4,5,6,7], 'notify_time':'13:00'})
    assert not storage.tracker_name_exists(ctx, 111, 'sleep')
    assert storage.tracker_name_exists(ctx, 111, 'READ')
    assert storage.get_next_tracker_id(ctx) == 2


def test_key():
    ctx = Context()
    ctx.application.user_data[222] = {'setup_complete': True}
    key = storage.create_activation_key(ctx)
    assert storage.activate_key(ctx, 111, key) == 'activated'
    assert storage.get_user_level(ctx, 111) == 'adv'
    ctx.user_data = ctx.application.user_data[222]
    assert storage.activate_key(ctx, 222, key) == 'used'
    assert storage.get_user_level(ctx, 222) == 'free'


def test_notifications():
    t = {'id':4, 'name':'Read', 'days_of_week':[1], 'notify_time':'09:15', 'history':{}}
    now = datetime(2026, 11, 16, 9, 15, tzinfo=timezone.utc)
    assert notifications.due_notification(t, now)
    t['last_notification_date'] = '2026-11-16'
    assert not notifications.due_notification(t, now)
    t.pop('last_notification_date')
    assert not notifications.due_notification(t, now + timedelta(minutes=32))


def test_navigation_and_admin_security():
    ctx = Context(111)
    today = storage.user_local_datetime(ctx, 111).date()
    t = {'id': 9, 'name':'Read','days_of_week':[1,2,3,4,5,6,7], 'notify_time':None,
         'history':{}, 'created_at':today.isoformat()}
    ctx.user_data['trackers'] = [t]
    kb = create_tracker_list_keyboard([t], 'rus', today)
    assert 'view_tracker_9_list' in cbs(kb)
    assert 'delete_tracker_confirm_9_listing' in cbs(kb)
    query = Query(111, 'view_tracker_9_list')
    asyncio.run(button_callback(NS(callback_query=query), ctx))
    assert 'show_my_trackers_list' in cbs(query.markup)
    query = Query(111, 'view_tracker_9_today')
    asyncio.run(button_callback(NS(callback_query=query), ctx))
    assert 'refresh_today_goals' in cbs(query.markup)
    query = Query(111, 'delete_tracker_confirm_9_listing')
    asyncio.run(button_callback(NS(callback_query=query), ctx))
    assert 'show_my_trackers_list' in cbs(query.markup)
    query = Query(111, 'menu_change_time_9_today')
    asyncio.run(button_callback(NS(callback_query=query), ctx))
    assert 'view_tracker_9_today' in cbs(query.markup)
    query = Query(111, 'admin_create_key')
    asyncio.run(button_callback(NS(callback_query=query), ctx))
    assert len(ctx.bot_data.get('activation_keys', {})) == 0
    assert query.answers[-1][1].get('show_alert') is True


def test_sweep_delivery_and_idempotence():
    ctx = Context()
    now = datetime(2026, 11, 16, 6, 15, tzinfo=timezone.utc)  # UTC+3 => Monday 09:15
    ctx.user_data['trackers'] = [{'id':1, 'name':'Read', 'days_of_week':[1,2,3,4,5,6,7],
                                 'notify_time':'09:15', 'history':{}, 'created_at':'2026-11-16'}]
    asyncio.run(notifications.sweep(ctx, now))
    asyncio.run(notifications.sweep(ctx, now + timedelta(seconds=30)))
    assert len(ctx.messages) == 1
    assert ctx.messages[0]['chat_id'] == 111
    assert ctx.user_data['trackers'][0]['last_notification_date'] == '2026-11-16'
    assert 'notif_yes_1_2026-11-16' in cbs(ctx.messages[0]['reply_markup'])


def test_sweep_restarts_catch_up():
    ctx = Context()
    ctx.user_data['trackers'] = [{'id':1,'name':'Read','days_of_week':[1,2,3,4,5,6,7],
                                 'notify_time':None,'history':{},'created_at':'2026-11-15'}]
    # Bot was offline all day yesterday and starts at 00:00 of user's local date.
    utc = datetime(2026,11,15,21,0,0,tzinfo=timezone.utc)
    asyncio.run(notifications.sweep(ctx, utc))
    assert ctx.user_data['trackers'][0]['history']['2026-11-15'] == 'failed'
    assert storage.calculate_tracker_streak(ctx.user_data['trackers'][0], date(2026,11,16)) == 0


def test_dst_zoneinfo():
    summer = datetime(2026,7,10,22,30,tzinfo=timezone.utc)
    winter = datetime(2026,1,10,22,30,tzinfo=timezone.utc)
    zone = {'timezone_name':'Europe/Amsterdam','timezone_offset':3600}
    assert storage.local_datetime_for_settings(zone, summer).date() == date(2026,7,11)
    assert storage.local_datetime_for_settings(zone, winter).date() == date(2026,1,10)


def test_invalid_time_keeps_input_state():
    from handlers.messages import handle_reply
    ctx = Context()
    today = storage.user_local_datetime(ctx, 111).date()
    ctx.user_data['trackers'] = [{'id':6,'name':'Read','days_of_week':list(range(1,8)),
                                  'notify_time':None, 'history':{}, 'created_at':today.isoformat()}]
    ctx.user_data['awaiting_time_input'] = (6,'today')
    class Message:
        text = 'not a time'
        responses = []
        async def reply_text(self, text, **kw): self.responses.append(text)
    msg = Message()
    asyncio.run(handle_reply(NS(effective_user=ctx.user, message=msg), ctx))
    assert ctx.user_data['awaiting_time_input'] == (6,'today')
    msg.text = '14:20'
    asyncio.run(handle_reply(NS(effective_user=ctx.user, message=msg), ctx))
    assert 'awaiting_time_input' not in ctx.user_data
    assert ctx.user_data['trackers'][0]['notify_time'] == '14:20'


def test_goal_callbacks_do_not_mark_overnight():
    ctx = Context()
    today = storage.user_local_datetime(ctx, 111).date()
    t = {'id':8,'name':'Read','days_of_week':list(range(1,8)),
         'notify_time':None, 'history':{}, 'created_at':today.isoformat()}
    ctx.user_data['trackers'] = [t]
    query = Query(111,'notif_yes_8_2020-01-01')
    asyncio.run(button_callback(NS(callback_query=query), ctx))
    assert not t['history']
    assert 'устарело' in query.text


def test_back_to_home_clears_wait_states():
    ctx = Context()
    ctx.user_data['awaiting_city_input'] = True
    ctx.user_data['awaiting_activation_key'] = True
    query = Query(111,'go_home')
    asyncio.run(button_callback(NS(callback_query=query), ctx))
    assert 'awaiting_city_input' not in ctx.user_data
    assert 'awaiting_activation_key' not in ctx.user_data
    assert 'Добро пожаловать' in query.text



def test_midnight_on_different_user_timezone():
    ctx = Context()
    t = {'id': 70, 'name': 'Exercise', 'days_of_week': list(range(1, 8)),
         'notify_time': None, 'history': {'2026-11-15': 'done'}, 'created_at': '2026-11-15'}
    ctx.user_data['trackers'] = [t]
    # UTC+3: 20:59 UTC is Sunday 23:59; 21:00 UTC is Monday 00:00.
    asyncio.run(notifications.sweep(ctx, datetime(2026, 11, 15, 20, 59, tzinfo=timezone.utc)))
    assert '2026-11-16' not in t['history']
    asyncio.run(notifications.sweep(ctx, datetime(2026, 11, 16, 21, 0, tzinfo=timezone.utc)))
    assert t['history']['2026-11-16'] == 'failed'
    assert storage.calculate_tracker_streak(t, date(2026, 11, 17)) == 0


def test_reminder_timeout_retries_on_next_sweep():
    from telegram.error import TimedOut
    ctx = Context()
    t = {'id': 72, 'name': 'Read', 'days_of_week': list(range(1, 8)),
         'notify_time': '09:15', 'history': {}, 'created_at': '2026-11-16'}
    ctx.user_data['trackers'] = [t]
    calls = []
    async def flaky_send(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise TimedOut('fake network outage')
        ctx.messages.append(kwargs)
    ctx.bot = NS(send_message=flaky_send)
    now = datetime(2026, 11, 16, 6, 15, tzinfo=timezone.utc)
    asyncio.run(notifications.sweep(ctx, now))
    assert t.get('last_notification_date') is None
    asyncio.run(notifications.sweep(ctx, now + timedelta(seconds=30)))
    assert t['last_notification_date'] == '2026-11-16'
    assert len(calls) == 2
    asyncio.run(notifications.sweep(ctx, now + timedelta(seconds=60)))
    assert len(calls) == 2


def test_network_error_handler_and_masking():
    from error_handlers import redact_secrets, telegram_error_handler, configure_safe_logging
    from telegram.error import TimedOut
    import logging, io
    raw = ('POST https://api.telegram.org/bot123456:TESTSECRET/getUpdates '
           'postgresql://username:DBSECRET@host/db')
    cleaned = redact_secrets(raw)
    assert 'TESTSECRET' not in cleaned
    assert 'DBSECRET' not in cleaned
    assert '[REDACTED]' in cleaned
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    log = logging.getLogger('network_test')
    log.setLevel(logging.WARNING)
    log.addHandler(handler)
    handler.addFilter(__import__('error_handlers').SensitiveLogFilter())
    try:
        log.warning(raw)
        assert 'TESTSECRET' not in stream.getvalue()
        assert 'DBSECRET' not in stream.getvalue()
    finally:
        log.removeHandler(handler)
    configure_safe_logging()
    assert logging.getLogger('httpx').level >= logging.WARNING
    asyncio.run(telegram_error_handler(None, NS(error=TimedOut('masked test'))))


def test_callback_timeout_is_network_not_history_failure():
    from telegram.error import TimedOut
    from error_handlers import telegram_error_handler
    ctx = Context()
    q = Query(111, 'settings_language')
    async def failing_edit(*a, **kw):
        raise TimedOut('fake proxy TLS connect timeout')
    q.edit_message_text = failing_edit
    try:
        asyncio.run(button_callback(NS(callback_query=q), ctx))
    except TimedOut as exc:
        asyncio.run(telegram_error_handler(None, NS(error=exc)))
    else:
        raise AssertionError('Expected a simulated network timeout')
    assert q.answers  # callback was acknowledged before Telegram lost connection
    assert 'settings' in ctx.user_data


def test_back_settings_time_state_cleanup():
    ctx = Context()
    ctx.user_data['awaiting_city_input'] = True
    ctx.user_data['awaiting_activation_key'] = True
    q = Query(111, 'settings_menu_back')
    asyncio.run(button_callback(NS(callback_query=q, effective_user=ctx.user), ctx))
    assert 'awaiting_city_input' not in ctx.user_data
    assert 'awaiting_activation_key' not in ctx.user_data
    assert q.text is not None


if __name__ == '__main__':
    tests = [v for k,v in sorted(globals().items()) if k.startswith('test_')]
    for test in tests:
        test()
        print('PASS', test.__name__)
    print(f'{len(tests)} tests passed.')
