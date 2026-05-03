"""
WinClare — Модуль очистки мусора
Сканирует и удаляет временные файлы, кэш, старые обновления Windows.
"""
import os
import shutil
import tempfile
import ctypes
import stat
from dataclasses import dataclass, field
from typing import Callable, Optional
from utils.logger import logger


@dataclass
class CleanTarget:
    """Описание одной категории мусора."""
    key: str
    name: str
    description: str
    paths: list[str]
    enabled: bool = True
    found_size: int = 0       # байт, найдено
    found_count: int = 0      # кол-во файлов
    cleaned_size: int = 0     # байт, удалено
    skipped_count: int = 0    # файлов пропущено (заблокированы)
    error: Optional[str] = None


def _get_targets() -> list[CleanTarget]:
    user = os.path.expanduser("~")
    windir = os.environ.get("WINDIR", r"C:\Windows")
    local_app = os.path.join(user, "AppData", "Local")

    return [
        CleanTarget(
            key="user_temp",
            name="Временные файлы пользователя",
            description="Папка %TEMP% — временные файлы запущенных программ",
            paths=[tempfile.gettempdir()],
        ),
        CleanTarget(
            key="win_temp",
            name="Системная папка Temp",
            description=r"C:\Windows\Temp — системные временные файлы",
            paths=[os.path.join(windir, "Temp")],
        ),
        CleanTarget(
            key="prefetch",
            name="Файлы Prefetch",
            description="Кэш предзагрузки программ (ускоряет повторный запуск, но накапливается)",
            paths=[os.path.join(windir, "Prefetch")],
        ),
        CleanTarget(
            key="win_updates",
            name="Старые обновления Windows",
            description=r"C:\Windows\SoftwareDistribution\Download — загруженные, но уже применённые обновления",
            paths=[os.path.join(windir, "SoftwareDistribution", "Download")],
        ),
        CleanTarget(
            key="thumbnails",
            name="Кэш миниатюр",
            description="Файлы thumbcache_*.db — превью изображений и видео",
            paths=[os.path.join(local_app, "Microsoft", "Windows", "Explorer")],
        ),
        CleanTarget(
            key="error_reports",
            name="Отчёты об ошибках Windows",
            description="Дампы и логи сбоёв Windows Error Reporting",
            paths=[
                os.path.join(local_app, "Microsoft", "Windows", "WER"),
                os.path.join(user, "AppData", "Local", "CrashDumps"),
                os.path.join(windir, "Minidump"),
            ],
        ),
        CleanTarget(
            key="log_files",
            name="Журналы и лог-файлы",
            description="Файлы *.log, *.tmp, *.dmp в системных папках",
            paths=[
                os.path.join(windir, "Logs"),
                os.path.join(windir, "debug"),
            ],
        ),
        CleanTarget(
            key="recycle_bin",
            name="Корзина",
            description="Удалённые файлы во всех корзинах всех дисков",
            paths=["__RECYCLE_BIN__"],   # специальный маркер
        ),
        CleanTarget(
            key="recent",
            name="Список недавних файлов",
            description="История недавно открытых файлов в меню Пуск",
            paths=[os.path.join(user, "AppData", "Roaming",
                                "Microsoft", "Windows", "Recent")],
        ),
        CleanTarget(
            key="delivery_opt",
            name="Оптимизация доставки обновлений",
            description="Кэш Windows Update Delivery Optimization (P2P-кэш обновлений)",
            paths=[os.path.join(windir, "SoftwareDistribution", "DeliveryOptimization")],
        ),
    ]


def _folder_size(path: str) -> tuple[int, int]:
    """Возвращает (суммарный_размер_байт, количество_файлов)."""
    total_size = 0
    total_count = 0
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    total_size += os.path.getsize(fp)
                    total_count += 1
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total_size, total_count


def _recycle_bin_size() -> tuple[int, int]:
    """Размер корзины на всех дисках."""
    total_size = 0
    total_count = 0
    import string
    for letter in string.ascii_uppercase:
        rb = f"{letter}:\\$RECYCLE.BIN"
        if os.path.exists(rb):
            s, c = _folder_size(rb)
            total_size += s
            total_count += c
    return total_size, total_count


def _remove_path_contents(path: str) -> tuple[int, int, int]:
    """
    Удаляет содержимое папки (не саму папку).
    Возвращает (освобождено_байт, удалено_файлов, пропущено_файлов).
    """
    freed = 0
    deleted = 0
    skipped = 0
    if not os.path.exists(path):
        return 0, 0, 0
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                size = os.path.getsize(item_path)
                os.chmod(item_path, stat.S_IWRITE)
                os.remove(item_path)
                freed += size
                deleted += 1
            elif os.path.isdir(item_path):
                size, count = _folder_size(item_path)
                shutil.rmtree(item_path, ignore_errors=True)
                if not os.path.exists(item_path):
                    freed += size
                    deleted += count
                else:
                    skipped += 1
        except (PermissionError, OSError):
            skipped += 1
    return freed, deleted, skipped


def _empty_recycle_bin() -> tuple[int, int]:
    """Очищает корзину через Windows Shell API."""
    freed = 0
    deleted = 0
    try:
        freed, deleted = _recycle_bin_size()
        # SHEmptyRecycleBin: флаг 7 = без диалога, без звука, без прогресса
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000007)
    except Exception as e:
        logger.warning(f"Не удалось очистить корзину: {e}")
        freed, deleted = 0, 0
    return freed, deleted


# ─────────────────────────────────────────────────────────────────────────────
# Публичный API
# ─────────────────────────────────────────────────────────────────────────────

class JunkCleaner:
    """
    Основной класс очистки мусора.

    Использование:
        cleaner = JunkCleaner()
        cleaner.scan(progress_cb=lambda pct, msg: ...)
        cleaner.clean(progress_cb=lambda pct, msg: ...)
    """

    def __init__(self):
        self.targets: list[CleanTarget] = _get_targets()
        self.total_found: int = 0
        self.total_cleaned: int = 0

    def get_targets(self) -> list[CleanTarget]:
        return self.targets

    def set_enabled(self, key: str, enabled: bool):
        for t in self.targets:
            if t.key == key:
                t.enabled = enabled

    def scan(self, progress_cb: Optional[Callable[[float, str], None]] = None) -> int:
        """
        Сканирует все включённые категории.
        Возвращает суммарный размер найденного мусора в байтах.
        """
        self.total_found = 0
        enabled = [t for t in self.targets if t.enabled]
        total = len(enabled)

        for i, target in enumerate(enabled):
            target.found_size = 0
            target.found_count = 0
            target.error = None

            if progress_cb:
                progress_cb(i / total, f"Сканирую: {target.name}...")

            try:
                if target.paths == ["__RECYCLE_BIN__"]:
                    target.found_size, target.found_count = _recycle_bin_size()
                else:
                    for path in target.paths:
                        if os.path.exists(path):
                            s, c = _folder_size(path)
                            target.found_size += s
                            target.found_count += c
            except Exception as e:
                target.error = str(e)
                logger.warning(f"Ошибка сканирования [{target.key}]: {e}")

            self.total_found += target.found_size
            logger.info(f"Сканирование [{target.key}]: "
                        f"{target.found_size / 1024**2:.1f} МБ, "
                        f"{target.found_count} файлов")

        if progress_cb:
            progress_cb(1.0, "Сканирование завершено")

        return self.total_found

    def clean(self, progress_cb: Optional[Callable[[float, str], None]] = None) -> int:
        """
        Удаляет мусор во всех включённых категориях.
        Возвращает суммарный размер освобождённого места в байтах.
        """
        self.total_cleaned = 0
        enabled = [t for t in self.targets if t.enabled and t.found_size > 0]
        total = len(enabled) or 1

        for i, target in enumerate(enabled):
            target.cleaned_size = 0
            if progress_cb:
                progress_cb(i / total, f"Очищаю: {target.name}...")

            try:
                if target.paths == ["__RECYCLE_BIN__"]:
                    freed, _ = _empty_recycle_bin()
                    target.cleaned_size = freed
                else:
                    for path in target.paths:
                        freed, _, skipped = _remove_path_contents(path)
                        target.cleaned_size += freed
                        target.skipped_count += skipped
            except Exception as e:
                target.error = str(e)
                logger.warning(f"Ошибка очистки [{target.key}]: {e}")

            self.total_cleaned += target.cleaned_size
            logger.info(f"Очищено [{target.key}]: "
                        f"{target.cleaned_size / 1024**2:.1f} МБ")

        if progress_cb:
            progress_cb(1.0, "Очистка завершена")

        return self.total_cleaned
