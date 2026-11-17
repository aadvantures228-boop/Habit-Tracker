from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from config.emojis import *
from config.texts import get_text
from datetime import date, datetime, timedelta
import storage
from html import escape

def create_main_keyboard(user_id: int, admin_id: int, lang: str):
    if lang == "eng":
        keyboard = [
            [f"{SETTINGS} Settings", f"{ADD} Add tracker"],
            [f"{EXTRA_DATA} My trackers", f"{TARGET} Today's goals"]
        ]
    else:
        keyboard = [
            [f"{SETTINGS} Настройки", f"{ADD} Добавить трекер"],
            [f"{EXTRA_DATA} Мои трекеры", f"{TARGET} Цели на сегодня"]
        ]
    if user_id == admin_id:
        if lang == "eng":
            keyboard.append([f"{ADMIN} Admin panel"])
        else:
            keyboard.append([f"{ADMIN} Админ-панель"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_settings_keyboard(lang: str):
    if lang == "eng":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{LANGUAGE} Change language", callback_data="settings_language")],
            [InlineKeyboardButton(f"{GLOBE} Change timezone", callback_data="settings_timezone")],
            [InlineKeyboardButton(f"{QUESTION} Help", callback_data="settings_help")],
            [InlineKeyboardButton("🔑 Activate ADV key", callback_data="activation_prompt")],
            [InlineKeyboardButton("⬅️ Back", callback_data="go_home")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{LANGUAGE} Сменить язык", callback_data="settings_language")],
            [InlineKeyboardButton(f"{GLOBE} Сменить часовой пояс", callback_data="settings_timezone")],
            [InlineKeyboardButton(f"{QUESTION} Помощь", callback_data="settings_help")],
            [InlineKeyboardButton("🔑 Активировать ключ ADV", callback_data="activation_prompt")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="go_home")]
        ])

def create_tracker_list_keyboard(trackers: list, lang: str, today: date = None):
    keyboard = []
    for tracker in trackers:
        streak = storage.calculate_tracker_streak(tracker, today or date.today())
        if lang == "eng":
            streak_text = f" ({FIRE} {streak} days)" if streak > 0 else ""
        else:
            streak_text = f" ({FIRE} {streak} дн.)" if streak > 0 else ""
        keyboard.append([
            InlineKeyboardButton(f"{TARGET} {tracker['name']}{streak_text}", callback_data=f"view_tracker_{tracker['id']}_list"),
            InlineKeyboardButton(f"{DELETE}", callback_data=f"delete_tracker_confirm_{tracker['id']}_listing")
        ])
    return InlineKeyboardMarkup(keyboard)

def create_tracker_detail_keyboard(tracker_id: int, current_time: str, lang: str, today_status: str = None, back_callback: str = "show_my_trackers_list", source: str = "list"):
    back = get_text(lang, "back")
    time_display = current_time if current_time else get_text(lang, "disabled")
    
    today_status_text = ""
    if today_status == "done":
        today_status_text = f"\n{CHECK} Сегодня: выполнено" if lang == "rus" else f"\n{CHECK} Today: completed"
    elif today_status == "failed":
        today_status_text = f"\n{CROSS} Сегодня: не выполнено" if lang == "rus" else f"\n{CROSS} Today: failed"
    elif today_status == "skipped":
        today_status_text = f"\n{SKIPPED} Сегодня: пропущено" if lang == "rus" else f"\n{SKIPPED} Today: skipped"
    else:
        today_status_text = f"\n{WARNING} Сегодня: не отмечено" if lang == "rus" else f"\n{WARNING} Today: not marked"
    
    if lang == "eng":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{CLOCK} Change time ({time_display})", callback_data=f"menu_change_time_{tracker_id}_{source}")],
            [InlineKeyboardButton(f"{DELETE} Delete tracker", callback_data=f"delete_tracker_confirm_{tracker_id}_{source}")],
            [InlineKeyboardButton(f"{BACK} Back", callback_data=back_callback)]
        ]), today_status_text
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{CLOCK} Изменить время ({time_display})", callback_data=f"menu_change_time_{tracker_id}_{source}")],
            [InlineKeyboardButton(f"{DELETE} Удалить трекер", callback_data=f"delete_tracker_confirm_{tracker_id}_{source}")],
            [InlineKeyboardButton(f"{BACK} К списку трекеров", callback_data=back_callback)]
        ]), today_status_text

def create_change_time_menu(tracker_id: int, current_time: str, lang: str, source: str = "list"):
    time_display = current_time if current_time else get_text(lang, "disabled")
    
    if lang == "eng":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{CLOCK} Enter new time", callback_data=f"prompt_time_{tracker_id}_{source}")],
            [InlineKeyboardButton(f"{CROSS} Disable notifications", callback_data=f"disable_time_{tracker_id}_{source}")],
            [InlineKeyboardButton(f"{BACK}", callback_data=f"view_tracker_{tracker_id}_{source}")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{CLOCK} Ввести новое время", callback_data=f"prompt_time_{tracker_id}_{source}")],
            [InlineKeyboardButton(f"{CROSS} Отключить уведомления", callback_data=f"disable_time_{tracker_id}_{source}")],
            [InlineKeyboardButton(f"{BACK}", callback_data=f"view_tracker_{tracker_id}_{source}")]
        ])

def create_change_timezone_menu(current_offset: int, lang: str):
    hours = current_offset // 3600
    tz_str = f"UTC{'+' if hours >= 0 else ''}{hours}"
    back = get_text(lang, "back")
    
    if lang == "eng":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{GLOBE} Enter new city", callback_data="prompt_city")],
            [InlineKeyboardButton(f"{BACK}", callback_data="settings_menu_back")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{GLOBE} Ввести новый город", callback_data="prompt_city")],
            [InlineKeyboardButton(f"{BACK}", callback_data="settings_menu_back")]
        ])

def create_today_goals_keyboard(trackers: list, today_date: str, lang: str):
    """
    ИСПРАВЛЕНИЕ 3: убрана кнопка "Проставить за дату"
    """
    keyboard = []
    for tracker in trackers:
        status = tracker['history'].get(today_date)
        name = tracker['name']
        t_id = tracker['id']

        if status:
            # Статус установлен — одна строка с названием и статусом
            if status == "done":
                status_icon = CHECK
                status_word = "Выполнено" if lang == "rus" else "Completed"
            elif status == "failed":
                status_icon = CROSS
                status_word = "Не выполнено" if lang == "rus" else "Failed"
            else:
                status_icon = SKIPPED
                status_word = "Пропущено" if lang == "rus" else "Skipped"
            
            keyboard.append([
                InlineKeyboardButton(f"{TARGET} {name} ({status_icon} {status_word})", callback_data=f"goal_toggle_{t_id}")
            ])
        else:
            # Статус не установлен — две строки
            # Строка 1: название (ведёт к статистике трекера)
            keyboard.append([
                InlineKeyboardButton(f"{TARGET} {name}", callback_data=f"view_tracker_{t_id}_today")
            ])
            # Строка 2: три кнопки действий
            if lang == "eng":
                keyboard.append([
                    InlineKeyboardButton(f"{CHECK} Done", callback_data=f"goal_mark_done_{t_id}"),
                    InlineKeyboardButton(f"{CROSS} Failed", callback_data=f"goal_failed_{t_id}"),
                    InlineKeyboardButton(f"{SKIPPED} Skip", callback_data=f"goal_skip_{t_id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(f"{CHECK} Выполнено", callback_data=f"goal_mark_done_{t_id}"),
                    InlineKeyboardButton(f"{CROSS} Не выполнено", callback_data=f"goal_failed_{t_id}"),
                    InlineKeyboardButton(f"{SKIPPED} Пропустить", callback_data=f"goal_skip_{t_id}")
                ])
    
    return InlineKeyboardMarkup(keyboard)
def create_days_keyboard(selected_days: list, lang: str, show_back: bool = False):
    if lang == "eng":
        days_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        ready_text = f"{CHECK} Ready"
        weekdays_text = "Weekdays"
        all_days_text = "All days"
        restart_text = f"{CANCEL} Start over"
    else:
        days_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        ready_text = f"{CHECK} Готово"
        weekdays_text = "Все будни"
        all_days_text = "Все дни"
        restart_text = f"{CANCEL} Начать заново"
    
    keyboard = []
    row = []
    for i, day in enumerate(days_names):
        prefix = f"{CHECK} " if (i + 1) in selected_days else ""
        row.append(InlineKeyboardButton(f"{prefix}{day}", callback_data=f"toggle_day_{i+1}"))
        if (i + 1) % 4 == 0 or i == 6:
            keyboard.append(row)
            row = []
    
    keyboard.append([
        InlineKeyboardButton(weekdays_text, callback_data="select_weekdays"),
        InlineKeyboardButton(all_days_text, callback_data="select_all_days")
    ])
    keyboard.append([InlineKeyboardButton(ready_text, callback_data="days_ready")])
    
    if show_back:
        keyboard.append([InlineKeyboardButton(f"{BACK} " + ("Назад" if lang == "rus" else "Back"), callback_data="add_back_name")])
    
    return InlineKeyboardMarkup(keyboard)

def create_time_keyboard(lang: str):
    restart_text = f"{CANCEL} Начать заново" if lang == "rus" else f"{CANCEL} Start over"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(restart_text, callback_data="add_back_days")]
    ])

def create_city_keyboard(lang: str):
    restart_text = f"{CANCEL} Начать заново" if lang == "rus" else f"{CANCEL} Start over"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(restart_text, callback_data="add_back_days")]
    ])

def create_notification_keyboard(tracker_id: int, lang: str):
    if lang == "eng":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{CHECK} Yes", callback_data=f"notif_yes_{tracker_id}")],
            [InlineKeyboardButton(f"{CROSS} No", callback_data=f"notif_no_{tracker_id}")],
            [InlineKeyboardButton(f"{SKIPPED} Skip", callback_data=f"notif_skip_{tracker_id}")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{CHECK} Да", callback_data=f"notif_yes_{tracker_id}")],
            [InlineKeyboardButton(f"{CROSS} Нет", callback_data=f"notif_no_{tracker_id}")],
            [InlineKeyboardButton(f"{SKIPPED} Пропустить", callback_data=f"notif_skip_{tracker_id}")]
        ])

def calculate_streak(history: dict) -> int:
    """Backward compatible calendar streak; tracker UI uses storage.calculate_tracker_streak."""
    return storage.calculate_tracker_streak({'history': history, 'days_of_week': list(range(1, 8))}, date.today())
