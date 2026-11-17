from config import emojis

# ТЕКСТЫ НА РУССКОМ
TEXTS_RUS = {
    "start": (
        "{TARGET} Добро пожаловать в Трекер Привычек!\n"
        "Я помогу тебе достигать целей и формировать полезные привычки.\n\n"
        "{USER} Твой часовой пояс: {GLOBE} {TIMEZONE}\n\n"
        "Используй кнопки ниже для управления:"
    ),
    "no_trackers": "{WARNING} У вас пока нет трекеров. Нажмите '{ADD} Добавить трекер'",
    "my_trackers": "{EXTRA_DATA} Ваши активные трекеры:",
    "today_goals": "{TARGET} Ваши цели на сегодня, {DATE}:",
    "no_goals_today": "{INFO} На сегодня целей нет! Отличный повод отдохнуть.",
    "tracker_stats": (
        "{STATS} <b>Статистика: {NAME}</b>\n\n"
        "{CALENDAR} Всего дней: {TOTAL}\n"
        "{CHECK} Выполнено: {DONE}\n"
        "{FAILED} Не выполнено: {FAILED_COUNT}\n"
        "{SKIPPED} Пропущено: {SKIPPED_COUNT}\n"
        "{FIRE} Текущая серия: {STREAK} дней!"
    ),
    "settings": (
        "{SETTINGS} <b>Настройки</b>\n\n"
        "{LANGUAGE} Язык: {LANGUAGE_NAME}\n"
        "{GLOBE} Часовой пояс: {TIMEZONE}"
    ),
    "language_menu": "{LANGUAGE} <b>Выберите язык / Choose language:</b>",
    "language_changed_ru": "{CHECK} Язык изменен на Русский",
    "language_changed_en": "{CHECK} Language changed to English",
    "help": (
        "{QUESTION} <b>Помощь</b>\n\n"
        "• <b>{ADD} Добавить трекер</b>: создайте новую привычку.\n"
        "• <b>{EXTRA_DATA} Мои трекеры</b>: статистика и управление.\n"
        "• <b>{TARGET} Цели на сегодня</b>: отмечайте прогресс.\n\n"
        "{BROADCAST} <b>Новости:</b> @weather_worldmap\n"
        "{MANAGER} <b>Поддержка:</b> @apchi10"
    ),
    "add_tracker_name": "{TARGET} Введите название новой привычки (например, 'Читать 30 минут'):",
    "add_tracker_days": "Отлично! В какие дни недели выполнять цель '<b>{NAME}</b>'?",
    "add_tracker_time": "{CLOCK} В какое время присылать напоминание? (например, '21:00'. Напишите 'нет', если не нужно):",
    "add_tracker_city": "{GLOBE} В каком городе вы находитесь? (Я определю часовой пояс автоматически):",
    "tracker_created": "{CHECK} Трекер '<b>{NAME}</b>' создан!\nНапоминания: {TIME_TEXT} ({TIMEZONE}).",
    "cancel": "{CANCEL} Добавление отменено.",
    "wrong_time_format": "{WARNING} Неверный формат. Введите время как <b>ЧЧ:ММ</b> или напишите 'отключить'.",
    "city_not_found": "{WARNING} Не удалось найти город '<b>{CITY}</b>'. Попробуйте еще раз.",
    "timezone_changed": "{CHECK} Часовой пояс успешно изменен на {TIMEZONE}!",
    "time_changed": "{CHECK} Время уведомления изменено на <b>{TIME}</b>.",
    "notifications_disabled": "{CHECK} Уведомления отключены.",
    "delete_confirm": "{WARNING} <b>Вы уверены?</b>\n\nУдаление трекера '<b>{NAME}</b>' и всей его истории необратимо.",
    "deleted": "{CHECK} Трекер успешно удален!",
    "goal_marked_done": "{CHECK} Цель выполнена! Так держать!",
    "goal_skipped": "{SKIPPED} Цель пропущена.",
    "admin_panel": "{ADMIN} <b>Административная панель</b>\nВыберите действие:",
    "broadcast_mode": (
        "{BROADCAST} <b>Режим рассылки</b>\n\n"
        "Отправьте мне текст (или перешлите сообщение), которое нужно разослать всем пользователям.\n\n"
        "Для отмены нажмите /cancel"
    ),
    "broadcast_sent": "{CHECK} Рассылка завершена! Сообщение доставлено {SUCCESS} из {TOTAL} пользователям.",
    "admin_data_view": (
        "{VIEW_DATA} <b>Сводка данных</b>\n\n"
        "{USER} Всего пользователей в боте: {USERS}\n"
        "{TARGET} Всего создано трекеров: {TRACKERS}"
    ),
    "admin_all_trackers": "{EXTRA_DATA} <b>Все трекеры пользователей</b>\n\n{LIST}",
    "notification_text": "{TARGET} <b>Напоминание: {NAME}</b>\n\nВы уже выполнили эту цель?",
    "yes": "Да",
    "no": "Нет",
    "skip": "Пропустить",
    "back": "{BACK} Назад",
    "change_timezone": "{GLOBE} <b>Текущий часовой пояс:</b> {TIMEZONE}\n\nВыберите действие:",
    "enter_city": "{GLOBE} Введите название города (например, <b>Екатеринбург</b>):",
    "change_time_menu": "{CLOCK} <b>Настройка уведомлений</b>\n\nТекущее время: <b>{TIME}</b>",
    "enter_new_time": "{CLOCK} Введите новое время в формате <b>ЧЧ:ММ</b> (например, <b>09:30</b>):",
    "disabled": "Отключено",
    "all_trackers_empty": "{INFO} Трекеров пока нет"
}

# TEXTS IN ENGLISH
TEXTS_ENG = {
    "start": (
        "{TARGET} Welcome to Habit Tracker!\n"
        "I'll help you achieve goals and build good habits.\n\n"
        "{USER} Your timezone: {GLOBE} {TIMEZONE}\n\n"
        "Use the buttons below to manage:"
    ),
    "no_trackers": "{WARNING} You have no trackers yet. Click '{ADD} Add tracker'",
    "my_trackers": "{EXTRA_DATA} Your active trackers:",
    "today_goals": "{TARGET} Your goals for today, {DATE}:",
    "no_goals_today": "{INFO} No goals for today! A great reason to rest.",
    "tracker_stats": (
        "{STATS} <b>Statistics: {NAME}</b>\n\n"
        "{CALENDAR} Total days: {TOTAL}\n"
        "{CHECK} Completed: {DONE}\n"
        "{FAILED} Failed: {FAILED_COUNT}\n"
        "{SKIPPED} Skipped: {SKIPPED_COUNT}\n"
        "{FIRE} Current streak: {STREAK} days!"
    ),
    "settings": (
        "{SETTINGS} <b>Settings</b>\n\n"
        "{LANGUAGE} Language: {LANGUAGE_NAME}\n"
        "{GLOBE} Timezone: {TIMEZONE}"
    ),
    "language_menu": "{LANGUAGE} <b>Choose language / Выберите язык:</b>",
    "language_changed_ru": "{CHECK} Language changed to Russian",
    "language_changed_en": "{CHECK} Language changed to English",
    "help": (
        "{QUESTION} <b>Help</b>\n\n"
        "• <b>{ADD} Add tracker</b>: create a new habit.\n"
        "• <b>{EXTRA_DATA} My trackers</b>: statistics and management.\n"
        "• <b>{TARGET} Today's goals</b>: mark your progress.\n\n"
        "{BROADCAST} <b>News:</b> @weather_worldmap\n"
        "{MANAGER} <b>Support:</b> @apchi10"
    ),
    "add_tracker_name": "{TARGET} Enter the name of your new habit (e.g., 'Read 30 minutes'):",
    "add_tracker_days": "Great! On which days of the week to complete '<b>{NAME}</b>'?",
    "add_tracker_time": "{CLOCK} What time to send a reminder? (e.g., '21:00'. Write 'no' if not needed):",
    "add_tracker_city": "{GLOBE} What city are you in? (I'll determine your timezone automatically):",
    "tracker_created": "{CHECK} Tracker '<b>{NAME}</b>' created!\nReminders: {TIME_TEXT} ({TIMEZONE}).",
    "cancel": "{CANCEL} Adding cancelled.",
    "wrong_time_format": "{WARNING} Wrong format. Enter time as <b>HH:MM</b> or write 'disable'.",
    "city_not_found": "{WARNING} Could not find city '<b>{CITY}</b>'. Try again.",
    "timezone_changed": "{CHECK} Timezone successfully changed to {TIMEZONE}!",
    "time_changed": "{CHECK} Notification time changed to <b>{TIME}</b>.",
    "notifications_disabled": "{CHECK} Notifications disabled.",
    "delete_confirm": "{WARNING} <b>Are you sure?</b>\n\nDeleting tracker '<b>{NAME}</b>' and all its history is irreversible.",
    "deleted": "{CHECK} Tracker successfully deleted!",
    "goal_marked_done": "{CHECK} Goal completed! Keep it up!",
    "goal_skipped": "{SKIPPED} Goal skipped.",
    "admin_panel": "{ADMIN} <b>Admin Panel</b>\nChoose action:",
    "broadcast_mode": (
        "{BROADCAST} <b>Broadcast mode</b>\n\n"
        "Send me text (or forward a message) to broadcast to all users.\n\n"
        "To cancel press /cancel"
    ),
    "broadcast_sent": "{CHECK} Broadcast complete! Message delivered to {SUCCESS} out of {TOTAL} users.",
    "admin_data_view": (
        "{VIEW_DATA} <b>Data summary</b>\n\n"
        "{USER} Total users in bot: {USERS}\n"
        "{TARGET} Total trackers created: {TRACKERS}"
    ),
    "admin_all_trackers": "{EXTRA_DATA} <b>All user trackers</b>\n\n{LIST}",
    "notification_text": "{TARGET} <b>Reminder: {NAME}</b>\n\nHave you completed this goal?",
    "yes": "Yes",
    "no": "No",
    "skip": "Skip",
    "back": "{BACK} Back",
    "change_timezone": "{GLOBE} <b>Current timezone:</b> {TIMEZONE}\n\nChoose action:",
    "enter_city": "{GLOBE} Enter city name (e.g., <b>Yekaterinburg</b>):",
    "change_time_menu": "{CLOCK} <b>Notification settings</b>\n\nCurrent time: <b>{TIME}</b>",
    "enter_new_time": "{CLOCK} Enter new time in <b>HH:MM</b> format (e.g., <b>09:30</b>):",
    "disabled": "Disabled",
    "all_trackers_empty": "{INFO} No trackers yet"
}

def get_text(lang: str, key: str, **kwargs) -> str:
    """Получить текст по ключу и языку с подстановкой переменных"""
    texts = TEXTS_ENG if lang == "eng" else TEXTS_RUS
    template = texts.get(key, f"MISSING: {key}")
    
    # Добавляем все константы из emojis в kwargs
    emojis_dict = {
        'TARGET': emojis.TARGET,
        'SETTINGS': emojis.SETTINGS,
        'ADD': emojis.ADD,
        'EXTRA_DATA': emojis.EXTRA_DATA,
        'ADMIN': emojis.ADMIN,
        'DELETE': emojis.DELETE,
        'BACK': emojis.BACK,
        'CANCEL': emojis.CANCEL,
        'CHECK': emojis.CHECK,
        'CROSS': emojis.CROSS,
        'WARNING': emojis.WARNING,
        'INFO': emojis.INFO,
        'QUESTION': emojis.QUESTION,
        'LANGUAGE': emojis.LANGUAGE,
        'GLOBE': emojis.GLOBE,
        'CALENDAR': emojis.CALENDAR,
        'CLOCK': emojis.CLOCK,
        'STATS': emojis.STATS,
        'FIRE': emojis.FIRE,
        'SKIPPED': emojis.SKIPPED,
        'DONE': emojis.DONE,
        'FAILED': emojis.FAILED,
        'BROADCAST': emojis.BROADCAST,
        'VIEW_DATA': emojis.VIEW_DATA,
        'EXPORT': emojis.EXPORT,
        'IMPORT': emojis.IMPORT,
        'USER': emojis.USER,
        'MANAGER': emojis.MANAGER
    }
    
    # Объединяем с переданными kwargs
    all_kwargs = {**emojis_dict, **kwargs}
    
    return template.format(**all_kwargs)