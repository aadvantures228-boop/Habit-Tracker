"""Persistence helpers. All user changes go through PTB user_data/bot_data."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from secrets import token_urlsafe
from config.defaults import DEFAULT_TIMEZONE_OFFSET
from config.env import ADMIN_ID, ADV_ACTIVATION_KEYS


INPUT_KEYS = ('awaiting_city_input', 'awaiting_time_input', 'awaiting_set_date_tracker_id',
              'awaiting_activation_key', 'new_tracker_name', 'new_tracker_days',
              'new_tracker_time', 'admin_input', 'last_view_source')


def reset_user_input_states(context, user_id):
    for key in INPUT_KEYS:
        context.user_data.pop(key, None)
    for key in ('admin_awaiting_broadcast', 'admin_importing'):
        if context.bot_data.get(key) == user_id:
            context.bot_data.pop(key, None)


def register_user(context, user_id, user=None):
    users = context.bot_data.setdefault('registered_users', [])
    if user_id not in users:
        users.append(user_id)
    profile = context.user_data.setdefault('profile', {})
    if user is not None:
        profile['username'] = user.username or ''
        profile['first_name'] = user.first_name or ''
    profile.setdefault('created_at', datetime.now(timezone.utc).isoformat())
    profile['last_active'] = datetime.now(timezone.utc).isoformat()
    if user_id == ADMIN_ID:
        context.user_data['level'] = 'adv'


def get_user_settings(context, user_id):
    settings = context.user_data.setdefault('settings', {})
    settings.setdefault('language', 'rus')
    if 'timezone_offset' not in settings:
        settings['timezone_offset'] = context.user_data.get('timezone_offset', DEFAULT_TIMEZONE_OFFSET)
    return settings


def get_user_setting(context, user_id, key):
    return get_user_settings(context, user_id).get(key)


def set_user_setting(context, user_id, key, value):
    settings = get_user_settings(context, user_id)
    settings[key] = value
    if key == 'timezone_offset':
        context.user_data['timezone_offset'] = value  # migrate old persistence data


def get_user_timezone(context, user_id):
    settings = get_user_settings(context, user_id)
    if settings.get('timezone_name'):
        dt = local_datetime_for_settings(settings)
        return int(dt.utcoffset().total_seconds())
    return int(settings['timezone_offset'])


def set_user_timezone(context, user_id, offset, zone_name=None):
    if not -12 * 3600 <= int(offset) <= 14 * 3600:
        raise ValueError('UTC offset out of range')
    set_user_setting(context, user_id, 'timezone_offset', int(offset))
    if zone_name:
        try:
            ZoneInfo(zone_name)
            set_user_setting(context, user_id, 'timezone_name', zone_name)
        except ZoneInfoNotFoundError:
            context.user_data['settings'].pop('timezone_name', None)
    else:
        context.user_data['settings'].pop('timezone_name', None)


def format_timezone(offset):
    sign = '+' if offset >= 0 else '-'
    hours, remainder = divmod(abs(int(offset)), 3600)
    minutes = remainder // 60
    return f'UTC{sign}{hours}' + (f':{minutes:02d}' if minutes else '')


def parse_timezone_offset(value):
    value = value.strip().upper().removeprefix('UTC').strip().replace(',', '.')
    try:
        if ':' in value:
            a, b = value.split(':', 1)
            offset = (abs(int(a)) * 3600 + int(b) * 60) * (-1 if a.startswith('-') else 1)
            if not (0 <= int(b) <= 59):
                return None
        else:
            offset = round(float(value) * 3600)
    except (ValueError, TypeError):
        return None
    return int(offset) if -43200 <= offset <= 50400 and offset % 60 == 0 else None


def local_datetime(offset, now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(timezone(timedelta(seconds=int(offset))))


def local_datetime_for_settings(settings, now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    if settings.get('timezone_name'):
        try:
            return now_utc.astimezone(ZoneInfo(settings['timezone_name']))
        except ZoneInfoNotFoundError:
            pass
    return local_datetime(settings.get('timezone_offset', DEFAULT_TIMEZONE_OFFSET), now_utc)


def user_local_datetime(context, user_id, now_utc=None):
    return local_datetime_for_settings(get_user_settings(context, user_id), now_utc)


def get_user_trackers(context, user_id):
    return context.user_data.setdefault('trackers', [])


def get_next_tracker_id(context):
    counter = context.bot_data.get('tracker_id_counter', 1)
    # Protect against imports / old persistence counters.
    all_ids = [int(t.get('id', 0)) for u in context.application.user_data.values()
               for t in u.get('trackers', [])]
    next_id = max(counter, max(all_ids, default=0) + 1)
    context.bot_data['tracker_id_counter'] = next_id + 1
    return next_id


def tracker_name_exists(context, user_id, name):
    return any(t['name'].casefold() == name.casefold() for t in get_user_trackers(context, user_id))


def add_tracker(context, user_id, tracker_data):
    data = dict(tracker_data)
    data['id'] = get_next_tracker_id(context)
    data['history'] = {}
    data['created_at'] = user_local_datetime(context, user_id).date().isoformat()
    data['last_reconciled'] = (date.fromisoformat(data['created_at']) - timedelta(days=1)).isoformat()
    get_user_trackers(context, user_id).append(data)
    return data


def get_tracker_by_id(context, user_id, tracker_id):
    return next((t for t in get_user_trackers(context, user_id) if t['id'] == tracker_id), None)


def delete_tracker(context, user_id, tracker_id):
    context.user_data['trackers'] = [t for t in get_user_trackers(context, user_id) if t['id'] != tracker_id]


def update_tracker_history(context, user_id, tracker_id, for_date, status):
    tracker = get_tracker_by_id(context, user_id, tracker_id)
    if not tracker or status not in ('done', 'failed', 'skipped'):
        return False
    day = date.fromisoformat(for_date)
    today = user_local_datetime(context, user_id).date()
    if day > today or day.isoweekday() not in tracker.get('days_of_week', []):
        return False
    if day < tracker_start_date(tracker, today):
        return False
    tracker.setdefault('history', {})[for_date] = status
    return True


def update_tracker_time(context, user_id, tracker_id, new_time):
    tracker = get_tracker_by_id(context, user_id, tracker_id)
    if tracker:
        tracker['notify_time'] = new_time
        tracker.pop('last_notification_date', None)


def tracker_start_date(tracker, today):
    raw = tracker.get('created_at')
    if raw:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            pass
    dates = []
    for k in tracker.get('history', {}):
        try:
            dates.append(date.fromisoformat(k))
        except ValueError:
            pass
    # Legacy data has no creation date. Don't assume it existed before earliest record.
    return min(dates) if dates else today


def reconcile_tracker(tracker, today):
    """Close all *past scheduled* days at local midnight, idempotent after restarts."""
    history = tracker.setdefault('history', {})
    start = tracker_start_date(tracker, today)
    last = tracker.get('last_reconciled')
    try:
        next_day = max(start, date.fromisoformat(last) + timedelta(days=1)) if last else start
    except ValueError:
        next_day = start
    stop = today - timedelta(days=1)
    if next_day <= stop:
        scheduled = set(tracker.get('days_of_week', []))
        while next_day <= stop:
            if next_day.isoweekday() in scheduled:
                history.setdefault(next_day.isoformat(), 'failed')
            next_day += timedelta(days=1)
        tracker['last_reconciled'] = stop.isoformat()
    return tracker


def reconcile_user(context, user_id, now_utc=None):
    today = user_local_datetime(context, user_id, now_utc).date()
    for tracker in get_user_trackers(context, user_id):
        reconcile_tracker(tracker, today)


def calculate_tracker_streak(tracker, today):
    """Consecutive *scheduled* completed days (today may still be pending)."""
    days = set(tracker.get('days_of_week', []))
    if not days:
        return 0
    start = tracker_start_date(tracker, today)
    history = tracker.get('history', {})
    cur = today
    # Today's unmarked goal is pending until the next midnight.
    if cur.isoweekday() not in days or cur.isoformat() not in history:
        cur -= timedelta(days=1)
    streak = 0
    while cur >= start:
        if cur.isoweekday() in days:
            if history.get(cur.isoformat()) != 'done':
                break
            streak += 1
        cur -= timedelta(days=1)
    return streak


def get_trackers_for_today(context, user_id):
    reconcile_user(context, user_id)
    weekday = user_local_datetime(context, user_id).isoweekday()
    return [t for t in get_user_trackers(context, user_id) if weekday in t.get('days_of_week', [])]


def get_user_level(context, user_id):
    return 'adv' if user_id == ADMIN_ID else context.user_data.get('level', 'free')


def set_user_level(context, user_id, level):
    if level not in ('adv', 'free'):
        raise ValueError('Unknown access level')
    if user_id == ADMIN_ID and level == 'free':
        return False
    udata = context.application.user_data.get(user_id)
    if udata is None:
        return False
    udata['level'] = level
    if hasattr(context.application, 'mark_data_for_update_persistence'):
        context.application.mark_data_for_update_persistence(user_ids=[user_id])
    return True


def create_activation_key(context):
    """Generate an individual, single-use key; only its SHA256 digest is persisted."""
    key = 'ADV-' + token_urlsafe(18).replace('-', 'X').replace('_', 'Y').upper()
    digest = sha256(key.encode()).hexdigest()
    context.bot_data.setdefault('activation_keys', {})[digest] = {'level': 'adv', 'used_by': None}
    return key


def activate_key(context, user_id, key):
    normalized = key.strip().upper()
    if not normalized:
        return 'invalid'
    if get_user_level(context, user_id) == 'adv':
        return 'already_adv'
    if normalized in ADV_ACTIVATION_KEYS:
        set_user_level(context, user_id, 'adv')
        return 'activated'
    digest = sha256(normalized.encode()).hexdigest()
    record = context.bot_data.setdefault('activation_keys', {}).get(digest)
    if record is None:
        return 'invalid'
    if record['used_by'] is not None:
        return 'used'
    record['used_by'] = user_id
    set_user_level(context, user_id, 'adv')
    return 'activated'
