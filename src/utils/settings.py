"""
WinClare — Настройки приложения
"""
import json
import os

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".winclare", "settings.json")

DEFAULTS = {
    # Общие
    "theme": "dark",
    "language": "ru",
    "start_minimized": False,
    "auto_scan_on_start": False,
    "confirm_before_delete": True,
    "show_notifications": True,
    # Автозапуск
    "run_on_startup": False,
    # Авто-очистка по расписанию
    "auto_clean_enabled": False,
    "auto_clean_interval": "weekly",   # "daily" | "weekly" | "monthly"
    "auto_clean_categories": ["user_temp", "win_temp", "thumbnails", "recycle_bin"],
    # Журнал
    "log_level": "INFO",               # "DEBUG" | "INFO" | "WARNING"
    "log_keep_days": 14,
}


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULTS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULTS, **data}
    except Exception:
        return DEFAULTS.copy()


def save_settings(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
