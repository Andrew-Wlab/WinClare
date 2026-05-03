"""
WinClare — Менеджер автозагрузки Windows
Источники:
  - Реестр HKLM/HKCU Run, RunOnce, WOW6432Node
  - Папки Startup (пользователь + все пользователи)
  - Планировщик задач Windows (Task Scheduler)
"""
import os
import winreg
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable
from utils.logger import logger


# ─── Типы и константы ────────────────────────────────────────────────────────

class StartupSource(Enum):
    REGISTRY_HKCU      = "Реестр (текущий пользователь)"
    REGISTRY_HKLM      = "Реестр (все пользователи)"
    REGISTRY_HKCU_ONCE = "Реестр RunOnce (пользователь)"
    REGISTRY_HKLM_ONCE = "Реестр RunOnce (система)"
    FOLDER_USER        = "Папка автозагрузки (пользователь)"
    FOLDER_ALL         = "Папка автозагрузки (все пользователи)"
    TASK_SCHEDULER     = "Планировщик задач"


class ImpactLevel(Enum):
    HIGH   = "Высокий"
    MEDIUM = "Средний"
    LOW    = "Низкий"
    UNKNOWN = "Неизвестен"


# Ключи реестра для сканирования
REGISTRY_SOURCES = [
    (winreg.HKEY_CURRENT_USER,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
     StartupSource.REGISTRY_HKCU, False),

    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
     StartupSource.REGISTRY_HKLM, False),

    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
     StartupSource.REGISTRY_HKLM, False),

    (winreg.HKEY_CURRENT_USER,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
     StartupSource.REGISTRY_HKCU_ONCE, False),

    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
     StartupSource.REGISTRY_HKLM_ONCE, False),
]

# Папки автозагрузки
STARTUP_FOLDERS = [
    (os.path.join(os.environ.get("APPDATA", ""),
                  r"Microsoft\Windows\Start Menu\Programs\Startup"),
     StartupSource.FOLDER_USER),
    (r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup",
     StartupSource.FOLDER_ALL),
]

# Ключ реестра для отключения записей (не удаляет, только отключает)
DISABLED_KEY_HKCU = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
DISABLED_KEY_HKLM = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"

# Процессы с высокой нагрузкой на старт
HIGH_IMPACT_KEYWORDS = [
    "update", "updater", "agent", "service", "daemon",
    "antivirus", "security", "defender", "norton", "kaspersky",
    "avast", "eset", "malware",
]
LOW_IMPACT_KEYWORDS = [
    "notify", "tray", "quicklaunch", "helper", "sidebar",
    "widget", "gadget", "launcher",
]


# ─── Запись автозагрузки ─────────────────────────────────────────────────────

@dataclass
class StartupEntry:
    name: str                          # имя записи
    command: str                       # полная команда запуска
    source: StartupSource              # откуда взята запись
    enabled: bool = True               # включена/отключена
    exe_path: str = ""                 # путь к .exe (извлечён из command)
    publisher: str = ""                # издатель (из метаданных файла)
    description: str = ""             # описание (из метаданных файла)
    impact: ImpactLevel = ImpactLevel.UNKNOWN
    # Внутренние поля для операций
    reg_hive: Optional[int] = field(default=None, repr=False)
    reg_key: str = field(default="", repr=False)
    folder_path: str = field(default="", repr=False)  # для записей из папки
    task_path: str = field(default="", repr=False)    # для задач планировщика


# ─── Вспомогательные функции ─────────────────────────────────────────────────

def _extract_exe(command: str) -> str:
    """Извлекает путь к exe из строки команды."""
    cmd = command.strip().strip('"')
    # Берём первый токен до пробела (если не в кавычках)
    if command.startswith('"'):
        end = command.find('"', 1)
        if end != -1:
            return command[1:end]
    return cmd.split(" ")[0]


def _get_file_info(exe_path: str) -> tuple[str, str]:
    """Возвращает (publisher, description) из метаданных файла."""
    if not exe_path or not os.path.isfile(exe_path):
        return "", ""
    try:
        import win32api
        info = win32api.GetFileVersionInfo(exe_path, "\\StringFileInfo\\040904B0\\")
        publisher   = info.get("CompanyName",   "").strip()
        description = info.get("FileDescription", "").strip()
        return publisher, description
    except Exception:
        pass
    try:
        # Запасной вариант — PowerShell
        result = subprocess.run(
            ["powershell", "-Command",
             f"(Get-Item '{exe_path}').VersionInfo | "
             "Select-Object -Property CompanyName, FileDescription | "
             "ConvertTo-Json"],
            capture_output=True, text=True, timeout=3
        )
        import json
        data = json.loads(result.stdout)
        return (data.get("CompanyName") or "").strip(), \
               (data.get("FileDescription") or "").strip()
    except Exception:
        return "", ""


def _assess_impact(entry: StartupEntry) -> ImpactLevel:
    """Оценивает нагрузку записи на время загрузки."""
    combined = (entry.name + " " + entry.command + " " + entry.description).lower()
    if any(k in combined for k in HIGH_IMPACT_KEYWORDS):
        return ImpactLevel.HIGH
    if any(k in combined for k in LOW_IMPACT_KEYWORDS):
        return ImpactLevel.LOW
    if entry.exe_path and os.path.isfile(entry.exe_path):
        size = os.path.getsize(entry.exe_path)
        if size > 50 * 1024 * 1024:   # > 50 МБ
            return ImpactLevel.HIGH
        if size < 2 * 1024 * 1024:    # < 2 МБ
            return ImpactLevel.LOW
        return ImpactLevel.MEDIUM
    return ImpactLevel.UNKNOWN


def _is_entry_disabled(name: str, hive: int) -> bool:
    """Проверяет, отключена ли запись через StartupApproved."""
    key_path = (DISABLED_KEY_HKCU if hive == winreg.HKEY_CURRENT_USER
                else DISABLED_KEY_HKLM)
    try:
        key = winreg.OpenKey(hive, key_path)
        data, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        # Первый байт: 02 = включено, 03 = отключено
        if isinstance(data, bytes) and len(data) > 0:
            return data[0] == 3
    except Exception:
        pass
    return False


# ─── Главный класс ────────────────────────────────────────────────────────────

class StartupManager:
    """
    Чтение, включение, отключение и удаление записей автозагрузки Windows.

    Использование:
        mgr = StartupManager()
        entries = mgr.load(progress_cb=...)
        mgr.disable(entry)
        mgr.enable(entry)
        mgr.delete(entry)
    """

    def __init__(self):
        self.entries: list[StartupEntry] = []

    def load(self,
             progress_cb: Optional[Callable[[float, str], None]] = None
             ) -> list[StartupEntry]:
        """Загружает все записи автозагрузки."""
        self.entries = []
        steps = [
            ("Реестр текущего пользователя...", self._load_registry),
            ("Папки автозагрузки...",           self._load_folders),
            ("Планировщик задач...",            self._load_task_scheduler),
        ]
        for i, (msg, fn) in enumerate(steps):
            if progress_cb:
                progress_cb(i / len(steps), msg)
            try:
                fn()
            except Exception as e:
                logger.warning(f"Ошибка загрузки автозагрузки [{msg}]: {e}")

        # Обогащаем данными о файлах
        if progress_cb:
            progress_cb(0.9, "Получение информации о файлах...")
        for entry in self.entries:
            entry.exe_path  = _extract_exe(entry.command)
            pub, desc       = _get_file_info(entry.exe_path)
            entry.publisher = pub
            entry.description = desc
            entry.impact    = _assess_impact(entry)

        if progress_cb:
            progress_cb(1.0, f"Загружено записей: {len(self.entries)}")
        logger.info(f"Автозагрузка: загружено {len(self.entries)} записей")
        return self.entries

    # ── Загрузка из реестра ──────────────────────────────────────

    def _load_registry(self):
        for hive, key_path, source, _ in REGISTRY_SOURCES:
            try:
                key = winreg.OpenKey(hive, key_path,
                                     access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.warning(f"Реестр [{key_path}]: {e}")
                continue

            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    enabled = not _is_entry_disabled(name, hive)
                    entry = StartupEntry(
                        name=name,
                        command=value,
                        source=source,
                        enabled=enabled,
                        reg_hive=hive,
                        reg_key=key_path,
                    )
                    self.entries.append(entry)
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)

    # ── Загрузка из папок Startup ────────────────────────────────

    def _load_folders(self):
        for folder, source in STARTUP_FOLDERS:
            if not os.path.isdir(folder):
                continue
            for fname in os.listdir(folder):
                fpath = os.path.join(folder, fname)
                if not os.path.isfile(fpath):
                    continue
                name = os.path.splitext(fname)[0]
                # .lnk — ярлык, разворачиваем через Shell
                if fname.lower().endswith(".lnk"):
                    command = self._resolve_lnk(fpath)
                else:
                    command = fpath
                entry = StartupEntry(
                    name=name,
                    command=command or fpath,
                    source=source,
                    enabled=True,
                    folder_path=fpath,
                )
                self.entries.append(entry)

    def _resolve_lnk(self, lnk_path: str) -> str:
        """Разворачивает .lnk ярлык в путь к целевому файлу."""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            return shortcut.Targetpath
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"(New-Object -ComObject WScript.Shell)"
                 f".CreateShortcut('{lnk_path}').TargetPath"],
                capture_output=True, text=True, timeout=3
            )
            return result.stdout.strip()
        except Exception:
            return lnk_path

    # ── Загрузка из планировщика задач ──────────────────────────

    def _load_task_scheduler(self):
        try:
            result = subprocess.run(
                ["schtasks", "/query", "/fo", "CSV", "/v"],
                capture_output=True, text=True, timeout=10,
                encoding="cp866", errors="ignore"
            )
            lines = result.stdout.splitlines()
            if not lines:
                return

            header = [h.strip('"') for h in lines[0].split('","')]
            try:
                idx_name    = header.index("ИМЯ ЗАДАЧИ") if "ИМЯ ЗАДАЧИ" in header else header.index("TaskName")
                idx_status  = next((i for i, h in enumerate(header)
                                    if "СОСТОЯНИЕ" in h or "Status" in h), -1)
                idx_cmd     = next((i for i, h in enumerate(header)
                                    if "ВЫПОЛНИТЬ" in h or "Task To Run" in h), -1)
                idx_trigger = next((i for i, h in enumerate(header)
                                    if "ТРИГГЕР" in h or "Trigger" in h), -1)
            except ValueError:
                return

            seen = set()
            for line in lines[1:]:
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) <= max(idx_name, idx_cmd if idx_cmd >= 0 else 0):
                    continue
                name = parts[idx_name] if idx_name < len(parts) else ""
                if not name or name in seen:
                    continue

                # Только задачи при входе/старте системы
                trigger = parts[idx_trigger].lower() if (idx_trigger >= 0 and idx_trigger < len(parts)) else ""
                if not any(t in trigger for t in ["logon", "startup", "при входе", "при запуске", "at startup", "at log on"]):
                    continue

                seen.add(name)
                cmd     = parts[idx_cmd] if (idx_cmd >= 0 and idx_cmd < len(parts)) else ""
                status  = parts[idx_status] if (idx_status >= 0 and idx_status < len(parts)) else ""
                enabled = "отключ" not in status.lower() and "disabled" not in status.lower()

                entry = StartupEntry(
                    name=name.split("\\")[-1],
                    command=cmd,
                    source=StartupSource.TASK_SCHEDULER,
                    enabled=enabled,
                    task_path=name,
                )
                self.entries.append(entry)
        except Exception as e:
            logger.warning(f"Планировщик задач: {e}")

    # ── Операции с записями ──────────────────────────────────────

    def enable(self, entry: StartupEntry) -> bool:
        """Включить запись автозагрузки."""
        try:
            if entry.source == StartupSource.TASK_SCHEDULER:
                subprocess.run(
                    ["schtasks", "/change", "/tn", entry.task_path, "/enable"],
                    capture_output=True, timeout=5)
                entry.enabled = True
                return True

            if entry.folder_path:
                # Папки — переименовываем с .disabled обратно
                disabled = entry.folder_path + ".disabled"
                if os.path.isfile(disabled):
                    os.rename(disabled, entry.folder_path)
                entry.enabled = True
                return True

            if entry.reg_hive is not None:
                self._set_startup_approved(entry, enabled=True)
                entry.enabled = True
                return True
        except Exception as e:
            logger.error(f"Не удалось включить [{entry.name}]: {e}")
        return False

    def disable(self, entry: StartupEntry) -> bool:
        """Отключить запись автозагрузки (без удаления)."""
        try:
            if entry.source == StartupSource.TASK_SCHEDULER:
                subprocess.run(
                    ["schtasks", "/change", "/tn", entry.task_path, "/disable"],
                    capture_output=True, timeout=5)
                entry.disabled = True
                entry.enabled = False
                return True

            if entry.folder_path:
                disabled = entry.folder_path + ".disabled"
                os.rename(entry.folder_path, disabled)
                entry.enabled = False
                return True

            if entry.reg_hive is not None:
                self._set_startup_approved(entry, enabled=False)
                entry.enabled = False
                return True
        except Exception as e:
            logger.error(f"Не удалось отключить [{entry.name}]: {e}")
        return False

    def delete(self, entry: StartupEntry) -> bool:
        """Удалить запись автозагрузки навсегда."""
        try:
            if entry.source == StartupSource.TASK_SCHEDULER:
                subprocess.run(
                    ["schtasks", "/delete", "/tn", entry.task_path, "/f"],
                    capture_output=True, timeout=5)
                self._remove_from_list(entry)
                return True

            if entry.folder_path:
                path = entry.folder_path
                if os.path.isfile(path):
                    os.remove(path)
                disabled = path + ".disabled"
                if os.path.isfile(disabled):
                    os.remove(disabled)
                self._remove_from_list(entry)
                return True

            if entry.reg_hive is not None:
                key = winreg.OpenKey(
                    entry.reg_hive, entry.reg_key,
                    access=winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
                winreg.DeleteValue(key, entry.name)
                winreg.CloseKey(key)
                self._remove_from_list(entry)
                return True
        except Exception as e:
            logger.error(f"Не удалось удалить [{entry.name}]: {e}")
        return False

    def _set_startup_approved(self, entry: StartupEntry, enabled: bool):
        """Устанавливает флаг включения в StartupApproved."""
        key_path = (DISABLED_KEY_HKCU
                    if entry.reg_hive == winreg.HKEY_CURRENT_USER
                    else DISABLED_KEY_HKLM)
        try:
            key = winreg.OpenKey(
                entry.reg_hive, key_path,
                access=winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
        except FileNotFoundError:
            key = winreg.CreateKey(entry.reg_hive, key_path)
        # 12 байт: первый байт 02=включено, 03=отключено, остальные нули
        data = bytes([2 if enabled else 3]) + b'\x00' * 11
        winreg.SetValueEx(key, entry.name, 0, winreg.REG_BINARY, data)
        winreg.CloseKey(key)

    def _remove_from_list(self, entry: StartupEntry):
        try:
            self.entries.remove(entry)
        except ValueError:
            pass

    # ── Утилиты ──────────────────────────────────────────────────

    def get_stats(self) -> dict:
        total    = len(self.entries)
        enabled  = sum(1 for e in self.entries if e.enabled)
        disabled = total - enabled
        high     = sum(1 for e in self.entries if e.impact == ImpactLevel.HIGH)
        return {"total": total, "enabled": enabled,
                "disabled": disabled, "high_impact": high}
