"""
WinClare — Поиск дубликатов файлов
Алгоритм: группировка по размеру → MD5-хэш → группы дубликатов
"""
import os
import hashlib
from dataclasses import dataclass, field
from typing import Callable, Optional
from utils.logger import logger

MIN_FILE_SIZE = 1024  # пропускаем файлы < 1 КБ


@dataclass
class DuplicateFile:
    path: str
    size: int
    mtime: float       # время изменения (для "оставить самый старый/новый")
    selected: bool = False    # отмечен для удаления
    deleted: bool = False


@dataclass
class DuplicateGroup:
    hash_: str
    size: int
    files: list[DuplicateFile] = field(default_factory=list)

    @property
    def wasted(self) -> int:
        """Место, которое займут дубликаты (все кроме одного)."""
        return self.size * (len(self.files) - 1)

    def auto_select(self, keep: str = "newest"):
        """keep: 'newest' | 'oldest' | 'first'"""
        if len(self.files) < 2:
            return
        if keep == "newest":
            keeper = max(self.files, key=lambda f: f.mtime)
        elif keep == "oldest":
            keeper = min(self.files, key=lambda f: f.mtime)
        else:
            keeper = self.files[0]
        for f in self.files:
            f.selected = (f is not keeper)


def _md5(path: str, chunk: int = 65536) -> Optional[str]:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while True:
                buf = f.read(chunk)
                if not buf:
                    break
                h.update(buf)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def _fmt(n: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ТБ"


class DuplicateFinder:
    def __init__(self):
        self.groups:        list[DuplicateGroup] = []
        self.total_wasted:  int = 0
        self.total_files:   int = 0
        self._stop_flag:    bool = False

    def stop(self):
        self._stop_flag = True

    def find(self,
             scan_paths: list[str],
             extensions: Optional[list[str]] = None,
             min_size: int = MIN_FILE_SIZE,
             progress_cb: Optional[Callable[[float, str], None]] = None
             ) -> list[DuplicateGroup]:
        """
        scan_paths: список папок/дисков для сканирования
        extensions: None = все файлы; ['jpg','png',...] = только эти
        """
        self._stop_flag = False
        self.groups = []

        # 1. Сбор файлов
        if progress_cb:
            progress_cb(0.0, "Сбор файлов...")
        all_files: list[tuple[int, str]] = []   # (size, path)
        for root_path in scan_paths:
            for dirpath, _, filenames in os.walk(root_path):
                if self._stop_flag:
                    return []
                for fname in filenames:
                    try:
                        if extensions:
                            ext = os.path.splitext(fname)[1].lower().lstrip(".")
                            if ext not in extensions:
                                continue
                        fp = os.path.join(dirpath, fname)
                        sz = os.path.getsize(fp)
                        if sz >= min_size:
                            all_files.append((sz, fp))
                    except OSError:
                        pass

        self.total_files = len(all_files)
        if progress_cb:
            progress_cb(0.15, f"Найдено файлов: {self.total_files}. Группировка по размеру...")

        if not all_files:
            return []

        # 2. Группировка по размеру
        size_map: dict[int, list[str]] = {}
        for sz, fp in all_files:
            size_map.setdefault(sz, []).append(fp)

        candidates = [(sz, paths) for sz, paths in size_map.items() if len(paths) > 1]
        total_candidates = sum(len(p) for _, p in candidates)

        if progress_cb:
            progress_cb(0.25, f"Вычисление MD5 для {total_candidates} файлов...")

        # 3. MD5-хэширование
        hash_map: dict[str, list[str]] = {}
        done = 0
        for sz, paths in candidates:
            for fp in paths:
                if self._stop_flag:
                    return []
                h = _md5(fp)
                if h:
                    hash_map.setdefault(h, []).append((fp, sz))
                done += 1
                if progress_cb and done % 50 == 0:
                    pct = 0.25 + 0.65 * (done / max(total_candidates, 1))
                    progress_cb(pct, f"Хэширование: {done}/{total_candidates}...")

        # 4. Формирование групп
        self.groups = []
        self.total_wasted = 0
        for h, items in hash_map.items():
            if len(items) < 2:
                continue
            size = items[0][1]
            group = DuplicateGroup(hash_=h, size=size)
            for fp, _ in items:
                try:
                    mtime = os.path.getmtime(fp)
                except OSError:
                    mtime = 0.0
                group.files.append(DuplicateFile(path=fp, size=size, mtime=mtime))
            self.total_wasted += group.wasted
            self.groups.append(group)

        # Сортируем: сначала самые «жирные» группы
        self.groups.sort(key=lambda g: g.wasted, reverse=True)

        if progress_cb:
            progress_cb(1.0, f"Готово — {len(self.groups)} групп дубликатов, "
                             f"потрачено: {_fmt(self.total_wasted)}")
        logger.info(f"Дубликаты: {len(self.groups)} групп, {_fmt(self.total_wasted)} потрачено")
        return self.groups

    def auto_select_all(self, keep: str = "newest"):
        for g in self.groups:
            g.auto_select(keep)

    def delete_selected(self,
                        progress_cb: Optional[Callable[[float, str], None]] = None
                        ) -> tuple[int, int]:
        """Удаляет отмеченные файлы. Возвращает (удалено_файлов, освобождено_байт)."""
        selected = [f for g in self.groups for f in g.files
                    if f.selected and not f.deleted]
        total = len(selected) or 1
        freed = 0
        deleted_count = 0

        for i, f in enumerate(selected):
            if progress_cb:
                progress_cb(i / total, f"Удаление: {os.path.basename(f.path)}")
            try:
                os.remove(f.path)
                freed += f.size
                deleted_count += 1
                f.deleted = True
                f.selected = False
            except (OSError, PermissionError) as e:
                logger.warning(f"Удаление дубликата [{f.path}]: {e}")

        if progress_cb:
            progress_cb(1.0, f"Удалено {deleted_count} файлов, освобождено {_fmt(freed)}")
        logger.info(f"Дубликаты удалены: {deleted_count} файлов, {_fmt(freed)}")
        return deleted_count, freed
