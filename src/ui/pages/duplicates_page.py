"""
WinClare — Страница «Поиск дубликатов»
"""
import os
import time
import threading
import tkinter.filedialog as fd
import customtkinter as ctk
from typing import Optional
from modules.duplicates.duplicate_finder import DuplicateFinder, DuplicateGroup, _fmt


class DuplicatesPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._finder = DuplicateFinder()
        self._groups: list[DuplicateGroup] = []
        self._scan_paths: list[str] = ["C:\\"]
        self._extensions: Optional[list[str]] = None
        self._lock = threading.Lock()
        self._is_running = False
        self._scanned = False
        self._auto_mode: Optional[str] = None   # "newest" | "oldest"
        self._build()

    def _build(self):
        # ── Заголовок ────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 4))
        ctk.CTkLabel(header, text="📋  Поиск дубликатов",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")

        btn_f = ctk.CTkFrame(header, fg_color="transparent")
        btn_f.pack(side="right")
        self.btn_scan = ctk.CTkButton(
            btn_f, text="🔍  Найти дубликаты",
            width=160, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#0f3460", hover_color="#16213e",
            command=self._start_scan)
        self.btn_scan.pack(side="left", padx=(0, 8))
        self.btn_delete = ctk.CTkButton(
            btn_f, text="🗑️  Удалить выбранные",
            width=170, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#e94560", hover_color="#c73652",
            state="disabled", command=self._start_delete)
        self.btn_delete.pack(side="left")

        self.summary = ctk.CTkLabel(
            self, text="Выберите диск/папку и нажмите «Найти дубликаты»",
            font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0")
        self.summary.pack(anchor="w", padx=30, pady=(4, 0))

        # ── Настройки сканирования ────────────────────────────────────────────
        opts = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        opts.pack(fill="x", padx=30, pady=(10, 10))

        path_row = ctk.CTkFrame(opts, fg_color="transparent")
        path_row.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(path_row, text="Папка для поиска:",
                     font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0",
                     width=140, anchor="w").pack(side="left")
        self.path_var = ctk.StringVar(value="C:\\")
        self.path_entry = ctk.CTkEntry(
            path_row, textvariable=self.path_var,
            font=ctk.CTkFont("Segoe UI", 12),
            height=32, fg_color="#0f3460", border_color="#2d3748")
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(path_row, text="📂  Обзор", width=100, height=32,
                      corner_radius=8, fg_color="#2d3748", hover_color="#4a5568",
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=self._browse_folder).pack(side="left")

        drives_row = ctk.CTkFrame(opts, fg_color="transparent")
        drives_row.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(drives_row, text="Быстрый выбор:",
                     font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0",
                     width=140, anchor="w").pack(side="left")
        for drive in self._get_drives():
            ctk.CTkButton(drives_row, text=drive, width=60, height=26,
                          corner_radius=6, fg_color="#0f3460", hover_color="#16213e",
                          font=ctk.CTkFont("Segoe UI", 11),
                          command=lambda d=drive: self.path_var.set(d)
                          ).pack(side="left", padx=(0, 6))

        filter_row = ctk.CTkFrame(opts, fg_color="transparent")
        filter_row.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(filter_row, text="Тип файлов:",
                     font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0",
                     width=140, anchor="w").pack(side="left")
        self.filter_var = ctk.StringVar(value="Все файлы")
        ctk.CTkOptionMenu(filter_row,
                          values=["Все файлы", "Фото (jpg, png, jpeg, bmp, gif)",
                                  "Видео (mp4, avi, mkv, mov)", "Документы (pdf, docx, xlsx)",
                                  "Музыка (mp3, flac, wav, ogg)", "Архивы (zip, rar, 7z)"],
                          variable=self.filter_var,
                          font=ctk.CTkFont("Segoe UI", 12),
                          fg_color="#0f3460", button_color="#0f3460",
                          button_hover_color="#16213e", dropdown_fg_color="#1a1a2e",
                          width=300, height=30).pack(side="left")

        # ── Прогресс ─────────────────────────────────────────────────────────
        prog_f = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        prog_f.pack(fill="x", padx=30, pady=(0, 10))
        self.prog_label = ctk.CTkLabel(
            prog_f, text="Ожидание...",
            font=ctk.CTkFont("Segoe UI", 11), text_color="#718096")
        self.prog_label.pack(anchor="w", padx=16, pady=(10, 4))
        self.progress = ctk.CTkProgressBar(
            prog_f, height=7, corner_radius=4,
            progress_color="#4a9eff", fg_color="#2d3748")
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 10))

        # ── Авто-выбор ───────────────────────────────────────────────────────
        auto_row = ctk.CTkFrame(self, fg_color="transparent")
        auto_row.pack(fill="x", padx=30, pady=(0, 8))

        ctk.CTkLabel(auto_row, text="Авто-выбор дубликатов:",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color="#a0aec0").pack(side="left")

        self._btn_newest = ctk.CTkButton(
            auto_row, text="✔  Оставить новейший",
            width=185, height=30, corner_radius=8,
            fg_color="#2d3748", hover_color="#4a5568",
            font=ctk.CTkFont("Segoe UI", 11),
            command=lambda: self._auto_select("newest"))
        self._btn_newest.pack(side="left", padx=(10, 6))

        self._btn_oldest = ctk.CTkButton(
            auto_row, text="✔  Оставить старейший",
            width=185, height=30, corner_radius=8,
            fg_color="#2d3748", hover_color="#4a5568",
            font=ctk.CTkFont("Segoe UI", 11),
            command=lambda: self._auto_select("oldest"))
        self._btn_oldest.pack(side="left")

        self.result_label = ctk.CTkLabel(
            auto_row, text="",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            text_color="#48bb78")
        self.result_label.pack(side="right")

        # ── Список групп ─────────────────────────────────────────────────────
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color="#16213e", corner_radius=14)
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        self.list_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(self.list_frame,
                     text="Результаты поиска появятся здесь",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color="#718096").grid(row=0, column=0, pady=60)

    # ── Вспомогательные ──────────────────────────────────────────────────────

    def _get_drives(self) -> list[str]:
        import string
        return [f"{d}:\\" for d in string.ascii_uppercase
                if os.path.exists(f"{d}:\\")]

    def _browse_folder(self):
        folder = fd.askdirectory(title="Выберите папку для поиска дубликатов")
        if folder:
            self.path_var.set(folder)

    def _get_extensions(self) -> Optional[list[str]]:
        val = self.filter_var.get()
        import re
        m = re.findall(r'\b(\w+)\b(?=,|\))', val)
        return m if m and "Все" not in val else None

    # ── Сканирование ─────────────────────────────────────────────────────────

    def _start_scan(self):
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
        self._scanned = False
        self._auto_mode = None
        self._reset_auto_buttons()
        self.btn_scan.configure(state="disabled", text="⏳  Поиск...")
        self.btn_delete.configure(state="disabled",
                                  text="🗑️  Удалить выбранные")
        self.result_label.configure(text="")
        self.progress.set(0)
        self.progress.configure(progress_color="#4a9eff")
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._scan_paths = [self.path_var.get()]
        self._extensions = self._get_extensions()
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        def cb(pct, msg):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        groups = self._finder.find(
            scan_paths=self._scan_paths,
            extensions=self._extensions,
            progress_cb=cb,
        )
        self.after(0, lambda: self._on_scan_done(groups))

    def _on_scan_done(self, groups):
        self._groups = groups
        self._render_groups(groups)
        n = len(groups)
        wasted = self._finder.total_wasted
        self.summary.configure(
            text=(f"Найдено {n} групп дубликатов  •  "
                  f"Потрачено впустую: {_fmt(wasted)}")
            if n else "✅ Дубликатов не найдено")
        self.prog_label.configure(
            text=f"✅ Готово — {n} групп, {_fmt(wasted)} можно освободить")
        self._scanned = n > 0
        with self._lock:
            self._is_running = False
        self.btn_scan.configure(state="normal", text="🔍  Найти дубликаты")
        if n > 0:
            self.btn_delete.configure(state="normal")

    # ── Рендер групп ─────────────────────────────────────────────────────────

    def _render_groups(self, groups):
        for w in self.list_frame.winfo_children():
            w.destroy()
        if not groups:
            ctk.CTkLabel(self.list_frame, text="✅  Дубликатов не найдено",
                         font=ctk.CTkFont("Segoe UI", 13),
                         text_color="#48bb78").grid(row=0, column=0, pady=60)
            return
        row_cursor = 0
        for group in groups[:200]:
            active = [f for f in group.files if not f.deleted]
            if len(active) < 2:
                continue
            row_cursor = self._add_group_row(row_cursor, group)

    def _add_group_row(self, start_row: int, group: DuplicateGroup) -> int:
        """Рисует заголовок группы и строки файлов. Возвращает следующий свободный row."""
        # Заголовок (синяя полоса)
        header_f = ctk.CTkFrame(self.list_frame, fg_color="#0f3460",
                                corner_radius=8)
        header_f.grid(row=start_row, column=0, padx=4,
                      pady=(8, 2), sticky="ew")
        ctk.CTkLabel(header_f,
                     text=(f"📁  {len(group.files)} копии  •  "
                           f"{_fmt(group.size)} каждый  •  "
                           f"Потрачено: {_fmt(group.wasted)}"),
                     font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                     text_color="#4a9eff").pack(side="left", padx=12, pady=8)

        next_row = start_row + 1
        for dup_file in group.files:
            self._add_file_row(next_row, dup_file)
            next_row += 1

        return next_row

    def _add_file_row(self, row_idx: int, dup_file):
        """
        Строка одного файла в группе дубликатов.
        Использует pack внутри (надёжнее grid в CTkScrollableFrame).
        """
        bg = "#1a1a2e"
        is_deleted = dup_file.deleted

        row = ctk.CTkFrame(self.list_frame, fg_color=bg, corner_radius=6)
        row.grid(row=row_idx, column=0, padx=(20, 4), pady=1, sticky="ew")

        # Дата — правая сторона (пакуем первой, чтобы side="right" работал)
        mtime_str = time.strftime("%d.%m.%Y", time.localtime(dup_file.mtime))
        ctk.CTkLabel(row, text=mtime_str,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color="#4a5568" if is_deleted else "#a0aec0",
                     width=90, anchor="center").pack(side="right", padx=(0, 10), pady=6)

        if is_deleted:
            ctk.CTkLabel(row, text="✓ удалён",
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color="#48bb78").pack(side="right", pady=6)

        # Левая часть: чекбокс + имя/путь
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        var = ctk.BooleanVar(value=dup_file.selected)

        def on_toggle(f=dup_file, v=var):
            f.selected = v.get()
            self._update_delete_btn()

        ctk.CTkCheckBox(left, text="", variable=var,
                        width=20, checkbox_width=16, checkbox_height=16,
                        fg_color="#e94560", hover_color="#c73652",
                        state="disabled" if is_deleted else "normal",
                        command=on_toggle).pack(side="left", padx=(4, 10))

        # Имя + папка в вертикальном блоке
        txt = ctk.CTkFrame(left, fg_color="transparent")
        txt.pack(side="left", fill="both", expand=True)

        name = os.path.basename(dup_file.path)
        folder = os.path.dirname(dup_file.path)
        if len(folder) > 60:
            folder = "..." + folder[-57:]

        ctk.CTkLabel(txt, text=name,
                     font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                     text_color="#718096" if is_deleted else "#ffffff",
                     anchor="w").pack(anchor="w", fill="x")
        ctk.CTkLabel(txt, text=folder,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color="#4a5568" if is_deleted else "#718096",
                     anchor="w").pack(anchor="w", fill="x")

        # Сохраняем BooleanVar на объекте для авто-выбора
        dup_file._var = var

    # ── Кнопка «Удалить» ─────────────────────────────────────────────────────

    def _update_delete_btn(self):
        selected = sum(1 for g in self._groups for f in g.files
                       if f.selected and not f.deleted)
        if selected > 0:
            self.btn_delete.configure(
                text=f"🗑️  Удалить {selected} файл(ов)", state="normal")
        else:
            self.btn_delete.configure(
                text="🗑️  Удалить выбранные", state="disabled")

    # ── Авто-выбор ───────────────────────────────────────────────────────────

    def _reset_auto_buttons(self):
        self._btn_newest.configure(fg_color="#2d3748",
                                   text="✔  Оставить новейший")
        self._btn_oldest.configure(fg_color="#2d3748",
                                   text="✔  Оставить старейший")

    def _auto_select(self, mode: str):
        if not self._groups:
            return
        self._auto_mode = mode
        self._finder.auto_select_all(keep=mode)

        # Подсвечиваем активную кнопку синим — другую серым
        if mode == "newest":
            self._btn_newest.configure(fg_color="#0f3460",
                                       text="✅  Оставить новейший")
            self._btn_oldest.configure(fg_color="#2d3748",
                                       text="✔  Оставить старейший")
        else:
            self._btn_oldest.configure(fg_color="#0f3460",
                                       text="✅  Оставить старейший")
            self._btn_newest.configure(fg_color="#2d3748",
                                       text="✔  Оставить новейший")

        # Синхронизируем чекбоксы в UI
        for group in self._groups:
            for f in group.files:
                if hasattr(f, "_var"):
                    f._var.set(f.selected)

        self._update_delete_btn()

        selected = sum(1 for g in self._groups for f in g.files
                       if f.selected and not f.deleted)
        self.result_label.configure(
            text=f"Выбрано к удалению: {selected} файлов")

    # ── Удаление ─────────────────────────────────────────────────────────────

    def _start_delete(self):
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
        self.btn_delete.configure(state="disabled")
        self.btn_scan.configure(state="disabled")
        self.progress.set(0)
        self.progress.configure(progress_color="#e94560")
        threading.Thread(target=self._do_delete, daemon=True).start()

    def _do_delete(self):
        def cb(pct, msg):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        count, freed = self._finder.delete_selected(progress_cb=cb)
        self.after(0, lambda: self._on_delete_done(count, freed))

    def _on_delete_done(self, count, freed):
        self.summary.configure(
            text=f"✅ Удалено {count} файлов  •  Освобождено {_fmt(freed)}")
        self.result_label.configure(text=f"💾 Освобождено {_fmt(freed)}")
        self.prog_label.configure(
            text=f"🎉 Удалено {count} дубликатов, освобождено {_fmt(freed)}")
        self._render_groups(self._groups)
        self._reset_auto_buttons()
        with self._lock:
            self._is_running = False
        self.btn_scan.configure(state="normal")
