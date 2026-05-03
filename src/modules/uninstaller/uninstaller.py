"""
WinClare — Деинсталлятор программ
Читает список установленных программ из реестра и запускает их удаление.
"""
import os
import winreg
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional
from utils.logger import logger


UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
     winreg.KEY_WOW64_64KEY),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
     winreg.KEY_WOW64_32KEY),
    (winreg.HKEY_CURRENT_USER,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
     0),
]


@dataclass
class InstalledApp:
    name: str
    version: str
    publisher: str
    install_date: str
    install_location: str
    size_bytes: int
    uninstall_string: str
    quiet_uninstall: str
    key_path: str
    hive: int
    system_component: bool = False   # системные компоненты Windows

    @property
    def size_str(self) -> str:
        n = self.size_bytes
        if n <= 0:
            return "—"
        for unit in ("КБ", "МБ", "ГБ"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} ГБ"

    @property
    def date_str(self) -> str:
        d = self.install_date
        if len(d) == 8 and d.isdigit():
            return f"{d[6:8]}.{d[4:6]}.{d[:4]}"
        return d or "—"


def _read_str(key, name: str, default: str = "") -> str:
    try:
        val, _ = winreg.QueryValueEx(key, name)
        return str(val).strip()
    except Exception:
        return default


def _read_int(key, name: str, default: int = 0) -> int:
    try:
        val, _ = winreg.QueryValueEx(key, name)
        return int(val)
    except Exception:
        return default


class Uninstaller:
    def __init__(self):
        self.apps: list[InstalledApp] = []

    def load(self,
             include_system: bool = False,
             progress_cb: Optional[Callable[[float, str], None]] = None
             ) -> list[InstalledApp]:
        self.apps = []
        seen_names: set[str] = set()

        all_keys = []
        for hive, key_path, flags in UNINSTALL_KEYS:
            try:
                access = winreg.KEY_READ | flags
                root = winreg.OpenKey(hive, key_path, access=access)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(root, i)
                        all_keys.append((hive, key_path + "\\" + subkey_name, flags))
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(root)
            except Exception:
                pass

        total = len(all_keys) or 1
        for idx, (hive, full_path, flags) in enumerate(all_keys):
            if progress_cb and idx % 20 == 0:
                pct = idx / total
                progress_cb(pct, f"Чтение записей... {idx}/{total}")
            try:
                access = winreg.KEY_READ | flags
                key = winreg.OpenKey(hive, full_path, access=access)

                name = _read_str(key, "DisplayName")
                if not name:
                    winreg.CloseKey(key)
                    continue

                # Дедупликация
                key_lower = name.lower()
                if key_lower in seen_names:
                    winreg.CloseKey(key)
                    continue
                seen_names.add(key_lower)

                is_system = bool(_read_int(key, "SystemComponent"))
                if is_system and not include_system:
                    winreg.CloseKey(key)
                    continue

                uninstall_str = _read_str(key, "UninstallString")
                if not uninstall_str:
                    winreg.CloseKey(key)
                    continue

                # Размер: EstimatedSize в КБ → байты
                size_kb = _read_int(key, "EstimatedSize")

                app = InstalledApp(
                    name=name,
                    version=_read_str(key, "DisplayVersion"),
                    publisher=_read_str(key, "Publisher"),
                    install_date=_read_str(key, "InstallDate"),
                    install_location=_read_str(key, "InstallLocation"),
                    size_bytes=size_kb * 1024,
                    uninstall_string=uninstall_str,
                    quiet_uninstall=_read_str(key, "QuietUninstallString"),
                    key_path=full_path,
                    hive=hive,
                    system_component=is_system,
                )
                self.apps.append(app)
                winreg.CloseKey(key)
            except Exception:
                pass

        # Сортируем: сначала крупные
        self.apps.sort(key=lambda a: a.size_bytes, reverse=True)

        if progress_cb:
            progress_cb(1.0, f"Загружено {len(self.apps)} программ")
        logger.info(f"Деинсталлятор: {len(self.apps)} программ")
        return self.apps

    def uninstall(self, app: InstalledApp, silent: bool = False) -> bool:
        """
        Запускает деинсталлятор программы.
        silent=True — пробует тихое удаление (QuietUninstallString).
        """
        cmd = (app.quiet_uninstall if silent and app.quiet_uninstall
               else app.uninstall_string)
        if not cmd:
            return False

        logger.info(f"Деинсталляция [{app.name}]: {cmd}")
        try:
            # MsiExec — добавляем /quiet если нужно
            if "msiexec" in cmd.lower() and silent:
                if "/quiet" not in cmd.lower() and "/q" not in cmd.lower():
                    cmd = cmd + " /quiet"

            subprocess.Popen(cmd, shell=True)
            return True
        except Exception as e:
            logger.error(f"Ошибка деинсталляции [{app.name}]: {e}")
            return False

    def search(self, query: str) -> list[InstalledApp]:
        q = query.lower()
        return [a for a in self.apps
                if q in a.name.lower() or q in a.publisher.lower()]

    def get_total_size(self) -> int:
        return sum(a.size_bytes for a in self.apps)
