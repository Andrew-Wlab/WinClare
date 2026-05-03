"""
WinClare — Анализатор диска
Рекурсивный обход папок: топ-папки и топ-файлы по размеру.
"""
import os
import string
from dataclasses import dataclass, field
from typing import Callable, Optional
from utils.logger import logger


@dataclass
class FileEntry:
    path: str
    size: int
    name: str = field(init=False)

    def __post_init__(self):
        self.name = os.path.basename(self.path)


@dataclass
class FolderEntry:
    path: str
    size: int          # суммарный размер содержимого
    file_count: int
    name: str = field(init=False)

    def __post_init__(self):
        self.name = os.path.basename(self.path) or self.path


@dataclass
class DriveInfo:
    letter: str        # "C:\\"
    label: str         # метка тома
    total: int
    used: int
    free: int
    percent: float
    fstype: str


@dataclass
class AnalysisResult:
    root_path: str
    total_size: int
    total_files: int
    top_files: list[FileEntry]
    top_folders: list[FolderEntry]


def _fmt(n: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ТБ"


def get_drives() -> list[DriveInfo]:
    """Возвращает список логических дисков Windows."""
    drives = []
    try:
        import psutil
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                label = _get_volume_label(part.mountpoint)
                drives.append(DriveInfo(
                    letter=part.mountpoint,
                    label=label,
                    total=usage.total,
                    used=usage.used,
                    free=usage.free,
                    percent=round(usage.percent, 1),
                    fstype=part.fstype,
                ))
            except (OSError, PermissionError):
                pass
    except Exception as e:
        logger.warning(f"get_drives: {e}")
    return drives


def _get_volume_label(path: str) -> str:
    try:
        import ctypes
        vol_name = ctypes.create_unicode_buffer(261)
        ctypes.windll.kernel32.GetVolumeInformationW(
            path, vol_name, 261, None, None, None, None, 0)
        return vol_name.value or ""
    except Exception:
        return ""


class DiskAnalyzer:
    def __init__(self):
        self._stop_flag = False
        self.result: Optional[AnalysisResult] = None

    def stop(self):
        self._stop_flag = True

    def analyze(self,
                root_path: str,
                top_n: int = 50,
                progress_cb: Optional[Callable[[float, str], None]] = None
                ) -> AnalysisResult:
        """
        Рекурсивно обходит root_path, собирает:
        - топ top_n файлов по размеру
        - топ top_n папок по суммарному размеру
        """
        self._stop_flag = False

        if progress_cb:
            progress_cb(0.0, "Сбор файлов...")

        all_files: list[FileEntry] = []
        folder_sizes: dict[str, int] = {}    # path -> суммарный размер
        folder_counts: dict[str, int] = {}

        total_checked = 0

        # Первый проход: собираем все файлы
        for dirpath, dirnames, filenames in os.walk(root_path):
            if self._stop_flag:
                break

            # Пропускаем системные папки Windows верхнего уровня
            rel = os.path.relpath(dirpath, root_path).lower()
            if rel in ("windows", "system volume information", "$recycle.bin",
                       "program files", "program files (x86)") and \
               os.path.abspath(dirpath) != os.path.abspath(root_path):
                pass   # не пропускаем — просканируем

            for fname in filenames:
                if self._stop_flag:
                    break
                try:
                    fp = os.path.join(dirpath, fname)
                    sz = os.path.getsize(fp)
                    all_files.append(FileEntry(path=fp, size=sz))
                    # Приписываем размер всем родительским папкам
                    parts = dirpath
                    while True:
                        folder_sizes[parts] = folder_sizes.get(parts, 0) + sz
                        folder_counts[parts] = folder_counts.get(parts, 0) + 1
                        parent = os.path.dirname(parts)
                        if parent == parts:
                            break
                        # Останавливаемся выше root_path
                        if not parts.lower().startswith(root_path.lower()):
                            break
                        parts = parent
                except (OSError, PermissionError):
                    pass

                total_checked += 1
                if progress_cb and total_checked % 500 == 0:
                    progress_cb(
                        min(0.9, total_checked / max(1, total_checked + 1000)),
                        f"Просканировано файлов: {total_checked:,}..."
                    )

        if progress_cb:
            progress_cb(0.9, "Формирование результатов...")

        total_size = sum(f.size for f in all_files)

        # Топ файлов
        all_files.sort(key=lambda f: f.size, reverse=True)
        top_files = all_files[:top_n]

        # Топ папок — только прямые подпапки root_path (первый уровень)
        top_folders_raw: list[FolderEntry] = []
        for path, size in folder_sizes.items():
            # Включаем только папки на уровне ниже root_path
            rel = os.path.relpath(path, root_path)
            # rel == "." — сам root; rel без os.sep — прямой дочерний
            if rel == ".":
                continue
            depth = rel.count(os.sep)
            if depth > 0:   # только 1-й уровень
                continue
            top_folders_raw.append(FolderEntry(
                path=path,
                size=size,
                file_count=folder_counts.get(path, 0),
            ))

        top_folders_raw.sort(key=lambda f: f.size, reverse=True)
        top_folders = top_folders_raw[:top_n]

        if progress_cb:
            progress_cb(1.0, f"Готово — {total_checked:,} файлов, {_fmt(total_size)}")

        self.result = AnalysisResult(
            root_path=root_path,
            total_size=total_size,
            total_files=total_checked,
            top_files=top_files,
            top_folders=top_folders,
        )
        logger.info(f"Анализ диска [{root_path}]: {total_checked} файлов, {_fmt(total_size)}")
        return self.result
