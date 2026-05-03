"""
WinClare — Страница «Анализатор диска»
"""
import os
import threading
import tkinter.filedialog as fd
import customtkinter as ctk
from modules.disk.disk_analyzer import DiskAnalyzer, get_drives, DriveInfo, _fmt


def _disk_color(pct: float) -> str:
    if pct >= 90:
        return "#e94560"
    if pct >= 70:
        return "#ed8936"
    return "#48bb78"


class DiskPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._analyzer = DiskAnalyzer()
        self._lock = threading.Lock()
        self._is_running = False
        self._drives: list[DriveInfo] = []
        self._build()
        threading.Thread(target=self._load_drives, daemon=True).start()

    # ── Построение интерфейса ────────────────────────────────────────────────

    def _build(self):
        # Заголовок
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 4))
        ctk.CTkLabel(header, text="💾  Анализатор диска",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")

        btn_f = ctk.CTkFrame(header, fg_color="transparent")
        btn_f.pack(side="right")
        self.btn_analyze = ctk.CTkButton(
            btn_f, text="🔍  Анализ", width=130, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#0f3460", hover_color="#16213e",
            command=self._start_analyze)
        self.btn_analyze.pack(side="left", padx=(0, 8))
        self.btn_stop = ctk.CTkButton(
            btn_f, text="⏹  Стоп", width=100, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#2d3748", hover_color="#4a5568",
            state="disabled", command=self._stop_analyze)
        self.btn_stop.pack(side="left")

        self.summary = ctk.CTkLabel(
            self, text="Выберите диск или папку и нажмите «Анализ»",
            font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0")
        self.summary.pack(anchor="w", padx=30, pady=(4, 0))

        # Диски-карточки
        self.drives_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.drives_frame.pack(fill="x", padx=30, pady=(10, 0))

        # Выбор пути
        path_row = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        path_row.pack(fill="x", padx=30, pady=(10, 0))
        path_row.columnconfigure(1, weight=1)

        ctk.CTkLabel(path_row, text="📂  Путь:",
                     font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0",
                     width=70, anchor="w").grid(row=0, column=0, padx=(16, 4), pady=10)
        self.path_var = ctk.StringVar(value="C:\\")
        ctk.CTkEntry(path_row, textvariable=self.path_var,
                     font=ctk.CTkFont("Segoe UI", 12),
                     height=32, fg_color="#0f3460", border_color="#2d3748",
                     ).grid(row=0, column=1, padx=4, pady=10, sticky="ew")
        ctk.CTkButton(path_row, text="Обзор", width=80, height=30,
                      corner_radius=8, fg_color="#2d3748", hover_color="#4a5568",
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=self._browse).grid(row=0, column=2, padx=(4, 16), pady=10)

        # Прогресс
        prog_f = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        prog_f.pack(fill="x", padx=30, pady=(10, 0))
        self.prog_label = ctk.CTkLabel(prog_f, text="Ожидание...",
                                        font=ctk.CTkFont("Segoe UI", 11),
                                        text_color="#718096")
        self.prog_label.pack(anchor="w", padx=16, pady=(10, 4))
        self.progress = ctk.CTkProgressBar(prog_f, height=7, corner_radius=4,
                                            progress_color="#4a9eff",
                                            fg_color="#2d3748")
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 10))

        # Вкладки: Папки / Файлы
        tabs = ctk.CTkFrame(self, fg_color="transparent")
        tabs.pack(fill="x", padx=30, pady=(10, 0))
        self._tab_mode = ctk.StringVar(value="folders")
        for label, mode in [("📁  Папки", "folders"), ("📄  Файлы", "files")]:
            ctk.CTkButton(tabs, text=label, width=140, height=34,
                          corner_radius=8,
                          fg_color="#0f3460" if mode == "folders" else "#2d3748",
                          hover_color="#16213e",
                          font=ctk.CTkFont("Segoe UI", 12),
                          command=lambda m=mode: self._switch_tab(m)
                          ).pack(side="left", padx=(0, 8))

        self._tab_btns: dict[str, ctk.CTkButton] = {}
        # Перестраиваем кнопки правильно
        for w in tabs.winfo_children():
            w.destroy()
        for label, mode in [("📁  Папки", "folders"), ("📄  Файлы", "files")]:
            btn = ctk.CTkButton(tabs, text=label, width=140, height=34,
                                corner_radius=8,
                                fg_color="#0f3460" if mode == "folders" else "#2d3748",
                                hover_color="#16213e",
                                font=ctk.CTkFont("Segoe UI", 12),
                                command=lambda m=mode: self._switch_tab(m))
            btn.pack(side="left", padx=(0, 8))
            self._tab_btns[mode] = btn

        # Шапка таблицы
        self.thead = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=0)
        self.thead.pack(fill="x", padx=30)
        self.thead.columnconfigure(1, weight=1)
        self._build_thead("folders")

        # Список
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color="#16213e", corner_radius=14)
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=(4, 20))
        self.list_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(self.list_frame,
                     text="Результаты появятся здесь",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color="#718096").grid(row=0, column=0, pady=60)

    def _build_thead(self, mode: str):
        for w in self.thead.winfo_children():
            w.destroy()
        if mode == "folders":
            cols = [("Папка", 0, "w"), ("Размер", 120, "center"),
                    ("Файлов", 80, "center"), ("Доля", 90, "center")]
        else:
            cols = [("Файл", 0, "w"), ("Размер", 120, "center"),
                    ("Тип", 80, "center"), ("Путь", 280, "w")]
        for i, (txt, w, anch) in enumerate(cols):
            ctk.CTkLabel(self.thead, text=txt,
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color="#718096",
                         width=w if w else 0, anchor=anch,
                         ).grid(row=0, column=i,
                                padx=(8 if i == 0 else 4, 4), pady=6,
                                sticky="ew" if i == 0 else "")
        self.thead.columnconfigure(0, weight=1)

    # ── Диски-карточки ────────────────────────────────────────────────────────

    def _load_drives(self):
        drives = get_drives()
        self.after(0, lambda: self._render_drive_cards(drives))

    def _render_drive_cards(self, drives: list[DriveInfo]):
        self._drives = drives
        for w in self.drives_frame.winfo_children():
            w.destroy()
        for i, d in enumerate(drives):
            self.drives_frame.columnconfigure(i, weight=1)
            self._drive_card(d, i)

    def _drive_card(self, d: DriveInfo, col: int):
        color = _disk_color(d.percent)
        f = ctk.CTkFrame(self.drives_frame, fg_color="#16213e", corner_radius=12,
                         cursor="hand2")
        f.grid(row=0, column=col, padx=(0 if col == 0 else 8, 0), sticky="ew")
        f.bind("<Button-1>", lambda e, p=d.letter: self._pick_drive(p))

        label = d.label or d.letter.rstrip("\\")
        ctk.CTkLabel(f, text=f"{d.letter.rstrip(chr(92))}  {label}",
                     font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                     text_color="#ffffff"
                     ).pack(anchor="w", padx=12, pady=(10, 4))

        bar = ctk.CTkProgressBar(f, height=8, corner_radius=4,
                                  progress_color=color, fg_color="#2d3748")
        bar.set(d.percent / 100)
        bar.pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(f,
                     text=f"{_fmt(d.used)} / {_fmt(d.total)}  ({d.percent:.0f}%)",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color="#a0aec0"
                     ).pack(anchor="w", padx=12, pady=(0, 10))

    def _pick_drive(self, path: str):
        self.path_var.set(path)

    def _browse(self):
        folder = fd.askdirectory(title="Выберите папку для анализа")
        if folder:
            self.path_var.set(folder)

    # ── Вкладки ───────────────────────────────────────────────────────────────

    def _switch_tab(self, mode: str):
        self._tab_mode.set(mode)
        for m, btn in self._tab_btns.items():
            btn.configure(fg_color="#0f3460" if m == mode else "#2d3748")
        self._build_thead(mode)
        # Если уже есть результат — перерисовать
        if self._analyzer.result:
            if mode == "folders":
                self._render_folders(self._analyzer.result.top_folders,
                                     self._analyzer.result.total_size)
            else:
                self._render_files(self._analyzer.result.top_files)

    # ── Анализ ────────────────────────────────────────────────────────────────

    def _start_analyze(self):
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
        self.btn_analyze.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress.set(0)
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._analyzer.stop()
        self._analyzer = DiskAnalyzer()

        path = self.path_var.get().strip() or "C:\\"
        threading.Thread(target=self._do_analyze, args=(path,), daemon=True).start()

    def _stop_analyze(self):
        self._analyzer.stop()
        self.btn_stop.configure(state="disabled")

    def _do_analyze(self, path: str):
        def cb(pct, msg):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        try:
            result = self._analyzer.analyze(path, progress_cb=cb)
        except Exception as e:
            result = None
            self.after(0, lambda: self.prog_label.configure(text=f"❌ Ошибка: {e}"))

        self.after(0, lambda: self._on_done(result))

    def _on_done(self, result):
        with self._lock:
            self._is_running = False
        self.btn_analyze.configure(state="normal")
        self.btn_stop.configure(state="disabled")

        if result is None:
            return

        self.summary.configure(
            text=f"Проанализировано: {result.total_files:,} файлов  •  "
                 f"Всего: {_fmt(result.total_size)}  •  "
                 f"Путь: {result.root_path}")

        mode = self._tab_mode.get()
        self._build_thead(mode)
        if mode == "folders":
            self._render_folders(result.top_folders, result.total_size)
        else:
            self._render_files(result.top_files)

    # ── Рендер ────────────────────────────────────────────────────────────────

    def _render_folders(self, folders, total_size: int):
        for w in self.list_frame.winfo_children():
            w.destroy()
        if not folders:
            ctk.CTkLabel(self.list_frame, text="Нет данных",
                         font=ctk.CTkFont("Segoe UI", 13),
                         text_color="#718096").grid(row=0, column=0, pady=40)
            return

        max_size = folders[0].size if folders else 1
        for i, f in enumerate(folders):
            bg = "#1a1a2e" if i % 2 == 0 else "#16213e"
            pct_total = f.size / total_size * 100 if total_size > 0 else 0
            pct_max   = f.size / max_size if max_size > 0 else 0
            color = _disk_color(pct_total)

            row = ctk.CTkFrame(self.list_frame, fg_color=bg, corner_radius=8)
            row.grid(row=i, column=0, padx=4, pady=2, sticky="ew")
            row.columnconfigure(0, weight=1)

            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.grid(row=0, column=0, columnspan=4, sticky="ew", padx=8, pady=(6, 2))
            inner.columnconfigure(0, weight=1)

            # Название папки
            ctk.CTkLabel(inner, text=f.name,
                         font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                         text_color="#ffffff", anchor="w"
                         ).grid(row=0, column=0, sticky="ew")
            ctk.CTkLabel(inner, text=_fmt(f.size),
                         font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                         text_color=color, width=110, anchor="e"
                         ).grid(row=0, column=1, padx=(8, 0))
            ctk.CTkLabel(inner, text=f"{f.file_count:,} файл.",
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color="#a0aec0", width=80, anchor="center"
                         ).grid(row=0, column=2, padx=4)
            ctk.CTkLabel(inner, text=f"{pct_total:.1f}%",
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color="#718096", width=60, anchor="center"
                         ).grid(row=0, column=3, padx=(4, 0))

            # Прогресс-бар доли
            bar = ctk.CTkProgressBar(row, height=4, corner_radius=2,
                                     progress_color=color, fg_color="#2d3748")
            bar.set(pct_max)
            bar.grid(row=1, column=0, padx=8, pady=(0, 6), sticky="ew")

            # Путь (мелко)
            short_path = f.path
            if len(short_path) > 70:
                short_path = "..." + short_path[-67:]
            ctk.CTkLabel(row, text=short_path,
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color="#4a5568", anchor="w"
                         ).grid(row=2, column=0, padx=8, pady=(0, 6), sticky="ew")

    def _render_files(self, files):
        for w in self.list_frame.winfo_children():
            w.destroy()
        if not files:
            ctk.CTkLabel(self.list_frame, text="Нет данных",
                         font=ctk.CTkFont("Segoe UI", 13),
                         text_color="#718096").grid(row=0, column=0, pady=40)
            return

        for i, f in enumerate(files):
            bg = "#1a1a2e" if i % 2 == 0 else "#16213e"
            row = ctk.CTkFrame(self.list_frame, fg_color=bg,
                               corner_radius=8, height=44)
            row.grid(row=i, column=0, padx=4, pady=2, sticky="ew")
            row.columnconfigure(0, weight=1)
            row.grid_propagate(False)

            ext = os.path.splitext(f.name)[1].upper().lstrip(".") or "—"
            size_color = "#e94560" if f.size > 500*1024*1024 else \
                         "#ed8936" if f.size > 100*1024*1024 else "#a0aec0"

            ctk.CTkLabel(row, text=f.name,
                         font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                         text_color="#ffffff", anchor="w"
                         ).grid(row=0, column=0, padx=(12, 4), sticky="ew")
            ctk.CTkLabel(row, text=_fmt(f.size),
                         font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                         text_color=size_color, width=120, anchor="center"
                         ).grid(row=0, column=1, padx=4)
            ctk.CTkLabel(row, text=ext,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color="#4a9eff", width=80, anchor="center"
                         ).grid(row=0, column=2, padx=4)

            folder = os.path.dirname(f.path)
            if len(folder) > 40:
                folder = "..." + folder[-37:]
            ctk.CTkLabel(row, text=folder,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color="#718096", width=280, anchor="w"
                         ).grid(row=0, column=3, padx=(4, 12))
