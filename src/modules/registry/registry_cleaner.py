"""
WinClare — Модуль очистки реестра Windows
Сканирует устаревшие, битые и пустые ключи. Всегда делает бэкап перед удалением.
"""
import os
import winreg
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional
from utils.logger import logger


class IssueType(Enum):
    INVALID_PATH      = "Недействительный путь к файлу"
    MISSING_EXE       = "Отсутствует исполняемый файл"
    OBSOLETE_SOFTWARE = "Устаревшие записи удалённых программ"
    INVALID_SHORTCUT  = "Битый ярлык"
    SHARED_DLL        = "Несуществующая DLL"
    EMPTY_KEY         = "Пустой ключ реестра"
    INVALID_STARTUP   = "Недействительная запись автозагрузки"


@dataclass
class RegistryIssue:
    issue_type: IssueType
    hive_name: str          # "HKCU" / "HKLM"
    key_path: str
    value_name: str
    value_data: str
    description: str
    selected: bool = True
    fixed: bool = False


HIVES = {
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
}

# Ключи со ссылками на файлы — проверяем что файлы существуют
FILE_REF_KEYS = [
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\SharedDLLs"),
    ("HKCU", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store"),
]

# Ключи программ — ищем удалённые
UNINSTALL_KEYS = [
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]

STARTUP_KEYS = [
    ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
]


def _extract_exe_path(value: str) -> str:
    v = value.strip()
    if v.startswith('"'):
        end = v.find('"', 1)
        return v[1:end] if end != -1 else v[1:]
    return v.split()[0] if v else ""


def _path_exists(path: str) -> bool:
    if not path:
        return True
    path = os.path.expandvars(path.strip('"').strip())
    return os.path.exists(path)


class RegistryCleaner:
    def __init__(self):
        self.issues: list[RegistryIssue] = []
        self.backup_path: str = ""

    def scan(self, progress_cb: Optional[Callable[[float, str], None]] = None
             ) -> list[RegistryIssue]:
        self.issues = []
        steps = [
            (0.15, "Проверка записей автозагрузки...",     self._scan_startup),
            (0.35, "Проверка ссылок на файлы...",          self._scan_file_refs),
            (0.60, "Проверка записей установленных программ...", self._scan_uninstall),
            (0.80, "Поиск пустых ключей...",               self._scan_empty_keys),
            (1.00, "Сканирование завершено",               lambda: None),
        ]
        for pct, msg, fn in steps:
            if progress_cb:
                progress_cb(pct - 0.14, msg)
            try:
                fn()
            except Exception as e:
                logger.warning(f"Реестр scan [{msg}]: {e}")
            if progress_cb:
                progress_cb(pct, msg)

        logger.info(f"Реестр: найдено {len(self.issues)} проблем")
        return self.issues

    def _scan_startup(self):
        for hive_name, key_path in STARTUP_KEYS:
            hive = HIVES[hive_name]
            try:
                key = winreg.OpenKey(hive, key_path, access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            except Exception:
                continue
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    exe = _extract_exe_path(str(value))
                    if exe and not _path_exists(exe):
                        self.issues.append(RegistryIssue(
                            issue_type=IssueType.INVALID_STARTUP,
                            hive_name=hive_name,
                            key_path=key_path,
                            value_name=name,
                            value_data=str(value),
                            description=f"Файл не найден: {exe}",
                        ))
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)

    def _scan_file_refs(self):
        for hive_name, key_path in FILE_REF_KEYS:
            hive = HIVES[hive_name]
            try:
                key = winreg.OpenKey(hive, key_path, access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            except Exception:
                continue
            i = 0
            while True:
                try:
                    name, value, vtype = winreg.EnumValue(key, i)
                    val_str = str(value)
                    if vtype in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                        path = _extract_exe_path(val_str)
                        if path and not _path_exists(path):
                            issue_type = (IssueType.SHARED_DLL
                                          if "SharedDLLs" in key_path
                                          else IssueType.MISSING_EXE)
                            self.issues.append(RegistryIssue(
                                issue_type=issue_type,
                                hive_name=hive_name,
                                key_path=key_path,
                                value_name=name,
                                value_data=val_str,
                                description=f"Файл не существует: {path}",
                            ))
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)

    def _scan_uninstall(self):
        for hive_name, key_path in UNINSTALL_KEYS:
            hive = HIVES[hive_name]
            try:
                key = winreg.OpenKey(hive, key_path, access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            except Exception:
                continue
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_path = key_path + "\\" + subkey_name
                    try:
                        subkey = winreg.OpenKey(hive, subkey_path,
                                                access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                        # Проверяем InstallLocation и UninstallString
                        for val_name in ("InstallLocation", "UninstallString"):
                            try:
                                val, _ = winreg.QueryValueEx(subkey, val_name)
                                path = _extract_exe_path(str(val))
                                if path and len(path) > 3 and not _path_exists(path):
                                    try:
                                        display = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    except Exception:
                                        display = subkey_name
                                    self.issues.append(RegistryIssue(
                                        issue_type=IssueType.OBSOLETE_SOFTWARE,
                                        hive_name=hive_name,
                                        key_path=subkey_path,
                                        value_name=val_name,
                                        value_data=str(val),
                                        description=f"Программа удалена: {display}",
                                    ))
                                    break
                            except Exception:
                                pass
                        winreg.CloseKey(subkey)
                    except Exception:
                        pass
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)

    def _scan_empty_keys(self):
        check_roots = [
            ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FileExts"),
            ("HKCU", r"SOFTWARE\Classes"),
        ]
        for hive_name, key_path in check_roots:
            hive = HIVES[hive_name]
            try:
                key = winreg.OpenKey(hive, key_path, access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            except Exception:
                continue
            i = 0
            count = 0
            while count < 30:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_path = key_path + "\\" + subkey_name
                    try:
                        subkey = winreg.OpenKey(hive, subkey_path,
                                                access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                        info = winreg.QueryInfoKey(subkey)
                        if info[0] == 0 and info[1] == 0:
                            self.issues.append(RegistryIssue(
                                issue_type=IssueType.EMPTY_KEY,
                                hive_name=hive_name,
                                key_path=subkey_path,
                                value_name="",
                                value_data="",
                                description="Пустой ключ реестра",
                            ))
                            count += 1
                        winreg.CloseKey(subkey)
                    except Exception:
                        pass
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)

    # ── Бэкап и исправление ──────────────────────────────────────

    def create_backup(self) -> str:
        """Экспортирует затронутые ключи в .reg файл. Возвращает путь к файлу."""
        backup_dir = os.path.join(os.path.expanduser("~"), ".winclare", "registry_backups")
        os.makedirs(backup_dir, exist_ok=True)
        from datetime import datetime
        fname = datetime.now().strftime("backup_%Y%m%d_%H%M%S.reg")
        path = os.path.join(backup_dir, fname)

        # Собираем уникальные корневые ключи
        keys_to_backup: set[str] = set()
        for issue in self.issues:
            if issue.selected:
                keys_to_backup.add(f"{issue.hive_name}\\{issue.key_path.split(chr(92))[0]}\\{issue.key_path.split(chr(92))[1]}")

        if not keys_to_backup:
            return ""

        with open(path, "w", encoding="utf-16") as f:
            f.write("Windows Registry Editor Version 5.00\n\n")

        for full_key in list(keys_to_backup)[:10]:
            try:
                subprocess.run(
                    ["reg", "export", full_key, path, "/y"],
                    capture_output=True, timeout=10
                )
            except Exception as e:
                logger.warning(f"Бэкап реестра [{full_key}]: {e}")

        self.backup_path = path
        logger.info(f"Бэкап реестра: {path}")
        return path

    def fix(self, progress_cb: Optional[Callable[[float, str], None]] = None) -> int:
        """Исправляет выбранные проблемы. Возвращает количество исправленных."""
        selected = [iss for iss in self.issues if iss.selected and not iss.fixed]
        fixed_count = 0
        total = len(selected) or 1

        for i, issue in enumerate(selected):
            if progress_cb:
                progress_cb(i / total, f"Исправление: {issue.description[:50]}...")
            try:
                hive = HIVES[issue.hive_name]
                if issue.issue_type == IssueType.EMPTY_KEY:
                    # Удаляем пустой ключ
                    parent_path = "\\".join(issue.key_path.split("\\")[:-1])
                    child_name  = issue.key_path.split("\\")[-1]
                    try:
                        parent = winreg.OpenKey(hive, parent_path,
                                                access=winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)
                        winreg.DeleteKey(parent, child_name)
                        winreg.CloseKey(parent)
                        issue.fixed = True
                        fixed_count += 1
                    except Exception as e:
                        logger.warning(f"Удаление ключа [{issue.key_path}]: {e}")
                else:
                    # Удаляем значение
                    if issue.value_name:
                        try:
                            key = winreg.OpenKey(hive, issue.key_path,
                                                 access=winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)
                            winreg.DeleteValue(key, issue.value_name)
                            winreg.CloseKey(key)
                            issue.fixed = True
                            fixed_count += 1
                        except Exception as e:
                            logger.warning(f"Удаление значения [{issue.value_name}]: {e}")
            except Exception as e:
                logger.error(f"Ошибка исправления [{issue.key_path}]: {e}")

        if progress_cb:
            progress_cb(1.0, f"Исправлено: {fixed_count} проблем")
        logger.info(f"Реестр fix: исправлено {fixed_count} из {len(selected)}")
        return fixed_count

    def get_stats(self) -> dict:
        total    = len(self.issues)
        selected = sum(1 for i in self.issues if i.selected)
        by_type: dict[str, int] = {}
        for iss in self.issues:
            k = iss.issue_type.value
            by_type[k] = by_type.get(k, 0) + 1
        return {"total": total, "selected": selected, "by_type": by_type}
