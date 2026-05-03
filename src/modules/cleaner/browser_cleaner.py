"""
WinClare — Модуль очистки браузеров
Поддерживаемые браузеры: Chrome, Edge, Firefox, Opera, Opera GX,
                          Brave, Vivaldi, Yandex Browser
"""
import os
import shutil
import sqlite3
import stat
from dataclasses import dataclass, field
from typing import Callable, Optional
from utils.logger import logger

LOCAL  = os.path.join(os.path.expanduser("~"), "AppData", "Local")
ROAMING = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")


# ─── Описание браузера ────────────────────────────────────────────────────────

@dataclass
class BrowserProfile:
    """Один профиль браузера (папка с данными)."""
    browser_key: str
    browser_name: str
    profile_name: str
    base_path: str           # корневая папка профиля
    found_size: int = 0
    cleaned_size: int = 0
    skipped_count: int = 0
    db_locked: bool = False  # True если SQLite был заблокирован браузером


@dataclass
class CleanCategory:
    """Тип данных для очистки (кэш, куки и т.д.)."""
    key: str
    name: str
    description: str
    enabled: bool = True
    found_size: int = 0
    cleaned_size: int = 0


# ─── Определения браузеров ────────────────────────────────────────────────────

BROWSERS = [
    {
        "key":   "chrome",
        "name":  "Google Chrome",
        "icon":  "🌐",
        "paths": [
            os.path.join(LOCAL, "Google", "Chrome", "User Data"),
        ],
    },
    {
        "key":   "edge",
        "name":  "Microsoft Edge",
        "icon":  "🔷",
        "paths": [
            os.path.join(LOCAL, "Microsoft", "Edge", "User Data"),
        ],
    },
    {
        "key":   "brave",
        "name":  "Brave Browser",
        "icon":  "🦁",
        "paths": [
            os.path.join(LOCAL, "BraveSoftware", "Brave-Browser", "User Data"),
        ],
    },
    {
        "key":   "opera",
        "name":  "Opera",
        "icon":  "🔴",
        "paths": [
            os.path.join(ROAMING, "Opera Software", "Opera Stable"),
        ],
    },
    {
        "key":   "opera_gx",
        "name":  "Opera GX",
        "icon":  "🎮",
        "paths": [
            os.path.join(ROAMING, "Opera Software", "Opera GX Stable"),
        ],
    },
    {
        "key":   "vivaldi",
        "name":  "Vivaldi",
        "icon":  "🌸",
        "paths": [
            os.path.join(LOCAL, "Vivaldi", "User Data"),
        ],
    },
    {
        "key":   "yandex",
        "name":  "Яндекс Браузер",
        "icon":  "🟡",
        "paths": [
            os.path.join(LOCAL, "Yandex", "YandexBrowser", "User Data"),
        ],
    },
    {
        "key":   "firefox",
        "name":  "Mozilla Firefox",
        "icon":  "🦊",
        "paths": [
            os.path.join(ROAMING, "Mozilla", "Firefox", "Profiles"),
        ],
        "is_firefox": True,
    },
]

# Процессы браузеров для определения открытых
BROWSER_PROCESSES: dict[str, list[str]] = {
    "chrome":    ["chrome.exe"],
    "edge":      ["msedge.exe"],
    "brave":     ["brave.exe"],
    "opera":     ["opera.exe"],
    "opera_gx":  ["opera.exe"],
    "vivaldi":   ["vivaldi.exe"],
    "yandex":    ["browser.exe"],
    "firefox":   ["firefox.exe"],
}


def get_running_browsers() -> set[str]:
    """Возвращает ключи браузеров, которые сейчас запущены."""
    try:
        import psutil
        running = {p.info["name"].lower()
                   for p in psutil.process_iter(["name"])
                   if p.info["name"]}
        locked: set[str] = set()
        for key, procs in BROWSER_PROCESSES.items():
            if any(proc.lower() in running for proc in procs):
                locked.add(key)
        return locked
    except Exception:
        return set()


# Папки кэша внутри профиля Chromium-браузера
CHROMIUM_CACHE_DIRS = [
    "Cache",
    "Cache2",
    "Code Cache",
    "GPUCache",
    "ShaderCache",
    "DawnCache",
    "Service Worker" + os.sep + "CacheStorage",
    "Service Worker" + os.sep + "ScriptCache",
    "Pepper Data",
    "Media Cache",
]

# Папки кэша в профиле Firefox
FIREFOX_CACHE_DIRS = [
    "cache2",
    "startupCache",
    "OfflineCache",
    "shader-cache",
]

# Файлы истории Chromium (SQLite — очищаем через SQL, не удаляем файл)
CHROMIUM_HISTORY_DBS = ["History", "Visited Links"]

# Файлы куки Chromium
CHROMIUM_COOKIE_FILES = ["Cookies", "Cookies-journal"]

# Firefox: файлы истории и куки
FIREFOX_HISTORY_FILES = ["places.sqlite", "places.sqlite-wal", "places.sqlite-shm"]
FIREFOX_COOKIE_FILES  = ["cookies.sqlite",  "cookies.sqlite-wal",  "cookies.sqlite-shm"]


# ─── Вспомогательные функции ─────────────────────────────────────────────────

def _folder_size(path: str) -> int:
    total = 0
    try:
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _remove_folder_contents(path: str) -> tuple[int, int]:
    """Удаляет содержимое папки. Возвращает (freed, skipped)."""
    freed = skipped = 0
    if not os.path.isdir(path):
        return 0, 0
    for item in os.listdir(path):
        fp = os.path.join(path, item)
        try:
            if os.path.isfile(fp) or os.path.islink(fp):
                size = _file_size(fp)
                os.chmod(fp, stat.S_IWRITE)
                os.remove(fp)
                freed += size
            elif os.path.isdir(fp):
                size = _folder_size(fp)
                shutil.rmtree(fp, ignore_errors=True)
                if not os.path.exists(fp):
                    freed += size
                else:
                    skipped += 1
        except (PermissionError, OSError):
            skipped += 1
    return freed, skipped


def _clear_sqlite_table(db_path: str, table: str) -> tuple[int, bool]:
    """
    Очищает таблицу в SQLite-файле.
    Возвращает (freed_bytes, was_locked).
    VACUUM запускается отдельно — вне транзакции (isolation_level=None).
    """
    if not os.path.isfile(db_path):
        return 0, False
    before = _file_size(db_path)
    try:
        # isolation_level=None = autocommit; это позволяет VACUUM без транзакции
        con = sqlite3.connect(db_path, timeout=2, isolation_level=None)
        con.execute(f"DELETE FROM {table}")
        con.execute("VACUUM")
        con.close()
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "locked" in msg or "readonly" in msg or "permission" in msg:
            logger.warning(f"SQLite заблокирован [{db_path}]: {e}")
            return 0, True          # база заблокирована браузером
        logger.warning(f"SQLite [{db_path}]: {e}")
        return 0, False
    except Exception as e:
        logger.warning(f"SQLite [{db_path}]: {e}")
        return 0, False
    after = _file_size(db_path)
    return max(0, before - after), False


def _remove_file(path: str) -> int:
    """Удаляет файл. Возвращает его размер, если успешно."""
    if not os.path.isfile(path):
        return 0
    size = _file_size(path)
    try:
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)
        return size
    except (PermissionError, OSError):
        return 0


# ─── Обнаружение профилей ─────────────────────────────────────────────────────

def _find_chromium_profiles(base_path: str, browser_key: str, browser_name: str) -> list[BrowserProfile]:
    profiles = []
    if not os.path.isdir(base_path):
        return profiles
    for item in os.listdir(base_path):
        if item in ("Default",) or item.startswith("Profile"):
            full = os.path.join(base_path, item)
            if os.path.isdir(full):
                profiles.append(BrowserProfile(
                    browser_key=browser_key,
                    browser_name=browser_name,
                    profile_name=item,
                    base_path=full,
                ))
    # Если нет профилей — добавляем корень как единственный профиль
    if not profiles and os.path.isdir(base_path):
        profiles.append(BrowserProfile(
            browser_key=browser_key,
            browser_name=browser_name,
            profile_name="Default",
            base_path=os.path.join(base_path, "Default")
            if os.path.isdir(os.path.join(base_path, "Default")) else base_path,
        ))
    return profiles


def _find_firefox_profiles(base_path: str) -> list[BrowserProfile]:
    profiles = []
    if not os.path.isdir(base_path):
        return profiles
    for item in os.listdir(base_path):
        full = os.path.join(base_path, item)
        if os.path.isdir(full) and "." in item:
            profiles.append(BrowserProfile(
                browser_key="firefox",
                browser_name="Mozilla Firefox",
                profile_name=item,
                base_path=full,
            ))
    return profiles


# ─── Главный класс ────────────────────────────────────────────────────────────

class BrowserCleaner:
    """
    Сканирует и очищает данные браузеров.

    Пример:
        cleaner = BrowserCleaner()
        cleaner.scan(progress_cb=...)
        cleaner.clean(progress_cb=...)
    """

    # Категории очистки
    CATEGORIES: list[CleanCategory] = []

    def __init__(self):
        self.categories = [
            CleanCategory("cache",   "Кэш браузеров",
                          "Временные файлы страниц, изображений, скриптов"),
            CleanCategory("cookies", "Куки (cookies)",
                          "Файлы отслеживания и авторизации сайтов"),
            CleanCategory("history", "История посещений",
                          "Список открытых страниц"),
            CleanCategory("logs",    "Лог-файлы браузеров",
                          "Диагностические и служебные файлы"),
        ]
        self.profiles: list[BrowserProfile] = []
        self.detected_browsers: list[dict] = []
        self.total_found:   int = 0
        self.total_cleaned: int = 0

    # ── Вкл/выкл категорий ───────────────────────────────────────

    def get_categories(self) -> list[CleanCategory]:
        return self.categories

    def set_category_enabled(self, key: str, enabled: bool):
        for cat in self.categories:
            if cat.key == key:
                cat.enabled = enabled

    def _cat_enabled(self, key: str) -> bool:
        for cat in self.categories:
            if cat.key == key:
                return cat.enabled
        return True

    # ── Определение браузеров ────────────────────────────────────

    def detect_browsers(self) -> list[dict]:
        """Возвращает список найденных браузеров с профилями."""
        self.detected_browsers = []
        self.profiles = []

        for bdef in BROWSERS:
            found_profiles = []
            for path in bdef["paths"]:
                if not os.path.isdir(path):
                    continue
                if bdef.get("is_firefox"):
                    found_profiles += _find_firefox_profiles(path)
                else:
                    found_profiles += _find_chromium_profiles(
                        path, bdef["key"], bdef["name"])

            if found_profiles:
                self.profiles.extend(found_profiles)
                self.detected_browsers.append({
                    "key":      bdef["key"],
                    "name":     bdef["name"],
                    "icon":     bdef["icon"],
                    "profiles": found_profiles,
                    "enabled":  True,
                    "is_firefox": bdef.get("is_firefox", False),
                })

        return self.detected_browsers

    def set_browser_enabled(self, key: str, enabled: bool):
        for b in self.detected_browsers:
            if b["key"] == key:
                b["enabled"] = enabled

    # ── Размер кэша конкретного профиля ──────────────────────────

    def _scan_chromium_profile(self, profile: BrowserProfile) -> int:
        total = 0
        base  = profile.base_path

        if self._cat_enabled("cache"):
            for cache_dir in CHROMIUM_CACHE_DIRS:
                full = os.path.join(base, cache_dir)
                total += _folder_size(full)

        if self._cat_enabled("cookies"):
            for f in CHROMIUM_COOKIE_FILES:
                total += _file_size(os.path.join(base, f))

        if self._cat_enabled("history"):
            for f in CHROMIUM_HISTORY_DBS:
                total += _file_size(os.path.join(base, f))

        if self._cat_enabled("logs"):
            for f in os.listdir(base) if os.path.isdir(base) else []:
                if f.endswith((".log", ".old")):
                    total += _file_size(os.path.join(base, f))

        profile.found_size = total
        return total

    def _scan_firefox_profile(self, profile: BrowserProfile) -> int:
        total = 0
        base  = profile.base_path

        if self._cat_enabled("cache"):
            cache_root = os.path.join(os.path.expanduser("~"),
                                      "AppData", "Local", "Mozilla",
                                      "Firefox", "Profiles", os.path.basename(base))
            for d in FIREFOX_CACHE_DIRS:
                total += _folder_size(os.path.join(cache_root, d))
                total += _folder_size(os.path.join(base, d))

        if self._cat_enabled("cookies"):
            for f in FIREFOX_COOKIE_FILES:
                total += _file_size(os.path.join(base, f))

        if self._cat_enabled("history"):
            for f in FIREFOX_HISTORY_FILES:
                total += _file_size(os.path.join(base, f))

        profile.found_size = total
        return total

    # ── Очистка конкретного профиля ──────────────────────────────

    def _clean_chromium_profile(self, profile: BrowserProfile) -> int:
        freed = 0
        locked = False
        base  = profile.base_path

        if self._cat_enabled("cache"):
            for cache_dir in CHROMIUM_CACHE_DIRS:
                full = os.path.join(base, cache_dir)
                f, sk = _remove_folder_contents(full)
                freed += f
                if sk:
                    profile.skipped_count += sk

        if self._cat_enabled("cookies"):
            for fname in CHROMIUM_COOKIE_FILES:
                freed += _remove_file(os.path.join(base, fname))

        if self._cat_enabled("history"):
            hist_path = os.path.join(base, "History")
            b1, lk1 = _clear_sqlite_table(hist_path, "visits")
            b2, lk2 = _clear_sqlite_table(hist_path, "urls")
            freed += b1 + b2
            if lk1 or lk2:
                locked = True
                profile.skipped_count += 1
            freed += _remove_file(os.path.join(base, "Visited Links"))

        if self._cat_enabled("logs"):
            if os.path.isdir(base):
                for f in os.listdir(base):
                    if f.endswith((".log", ".old")):
                        freed += _remove_file(os.path.join(base, f))

        profile.cleaned_size = freed
        profile.db_locked = locked
        return freed

    def _clean_firefox_profile(self, profile: BrowserProfile) -> int:
        freed = 0
        locked = False
        base  = profile.base_path

        if self._cat_enabled("cache"):
            cache_root = os.path.join(os.path.expanduser("~"),
                                      "AppData", "Local", "Mozilla",
                                      "Firefox", "Profiles", os.path.basename(base))
            for d in FIREFOX_CACHE_DIRS:
                f1, _ = _remove_folder_contents(os.path.join(cache_root, d))
                f2, _ = _remove_folder_contents(os.path.join(base, d))
                freed += f1 + f2

        if self._cat_enabled("cookies"):
            for fname in FIREFOX_COOKIE_FILES:
                freed += _remove_file(os.path.join(base, fname))

        if self._cat_enabled("history"):
            hist = os.path.join(base, "places.sqlite")
            b1, lk1 = _clear_sqlite_table(hist, "moz_historyvisits")
            b2, lk2 = _clear_sqlite_table(hist, "moz_places")
            freed += b1 + b2
            if lk1 or lk2:
                locked = True
                profile.skipped_count += 1
            for f in FIREFOX_HISTORY_FILES[1:]:
                freed += _remove_file(os.path.join(base, f))

        profile.cleaned_size = freed
        profile.db_locked = locked
        return freed

    # ── Публичный API ─────────────────────────────────────────────

    def scan(self, progress_cb: Optional[Callable[[float, str], None]] = None) -> int:
        if not self.detected_browsers:
            self.detect_browsers()

        # Сброс
        self.total_found = 0
        for cat in self.categories:
            cat.found_size = 0

        enabled_profiles = [
            (p, b.get("is_firefox", False))
            for b in self.detected_browsers if b["enabled"]
            for p in b["profiles"]
        ]
        total = len(enabled_profiles) or 1

        for i, (profile, is_ff) in enumerate(enabled_profiles):
            if progress_cb:
                progress_cb(i / total,
                            f"Сканирую {profile.browser_name} ({profile.profile_name})...")
            if is_ff:
                self._scan_firefox_profile(profile)
            else:
                self._scan_chromium_profile(profile)
            self.total_found += profile.found_size
            logger.info(f"Браузер [{profile.browser_name}/{profile.profile_name}]: "
                        f"{profile.found_size / 1024**2:.1f} МБ")

        if progress_cb:
            progress_cb(1.0, "Сканирование завершено")
        return self.total_found

    def clean(self, progress_cb: Optional[Callable[[float, str], None]] = None
              ) -> tuple[int, list[str]]:
        """
        Запускает очистку.
        Возвращает (total_cleaned_bytes, locked_browser_names).
        locked_browser_names — браузеры, у которых история была заблокирована
        (браузер нужно закрыть перед очисткой истории).
        """
        self.total_cleaned = 0
        locked_names: list[str] = []

        enabled_profiles = [
            (p, b.get("is_firefox", False), b["name"])
            for b in self.detected_browsers if b["enabled"]
            for p in b["profiles"]
            if p.found_size > 0
        ]
        total = len(enabled_profiles) or 1

        for i, (profile, is_ff, bname) in enumerate(enabled_profiles):
            if progress_cb:
                progress_cb(i / total,
                            f"Очищаю {profile.browser_name} ({profile.profile_name})...")
            if is_ff:
                self._clean_firefox_profile(profile)
            else:
                self._clean_chromium_profile(profile)
            self.total_cleaned += profile.cleaned_size
            if profile.db_locked and bname not in locked_names:
                locked_names.append(bname)
            logger.info(f"Очищено [{profile.browser_name}/{profile.profile_name}]: "
                        f"{profile.cleaned_size / 1024**2:.1f} МБ"
                        + (" [история заблокирована]" if profile.db_locked else ""))

        if progress_cb:
            progress_cb(1.0, "Очистка завершена")
        return self.total_cleaned, locked_names
