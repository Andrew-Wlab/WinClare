"""
WinClare — Страница «Очистка реестра»
"""
import threading
import customtkinter as ctk
from modules.registry.registry_cleaner import RegistryCleaner, RegistryIssue, IssueType

TYPE_ICON = {
    IssueType.INVALID_STARTUP:   "🚀",
    IssueType.MISSING_EXE:       "❌",
    IssueType.OBSOLETE_SOFTWARE: "🗑️",
    IssueType.SHARED_DLL:        "📦",
    IssueType.EMPTY_KEY:         "📭",
    IssueType.INVALID_PATH:      "🔗",
    IssueType.INVALID_SHORTCUT:  "🔗",
}


class RegistryPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._cleaner = RegistryCleaner()
        self._issues: list[RegistryIssue] = []
        self._lock = threading.Lock()
        self._is_running = False
        self._scanned = False
        self._chk_vars: list[ctk.BooleanVar] = []
        self._build()

    def _build(self):
        # Заголовок
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 4))
        ctk.CTkLabel(header, text="🗂️  Очистка реестра",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")

        btn_f = ctk.CTkFrame(header, fg_color="transparent")
        btn_f.pack(side="right")
        self.btn_scan = ctk.CTkButton(btn_f, text="🔍  Анализ",
                                       width=130, height=40, corner_radius=10,
                                       font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                                       fg_color="#0f3460", hover_color="#16213e",
                                       command=self._start_scan)
        self.btn_scan.pack(side="left", padx=(0, 8))
        self.btn_fix = ctk.CTkButton(btn_f, text="🔧  Исправить",
                                      width=140, height=40, corner_radius=10,
                                      font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                                      fg_color="#e94560", hover_color="#c73652",
                                      state="disabled", command=self._start_fix)
        self.btn_fix.pack(side="left")

        self.summary = ctk.CTkLabel(self, text="Нажмите «Анализ» для сканирования реестра",
                                     font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0")
        self.summary.pack(anchor="w", padx=30, pady=(4, 0))

        # Предупреждение
        warn = ctk.CTkFrame(self, fg_color="#2d1b0e", corner_radius=10)
        warn.pack(fill="x", padx=30, pady=(10, 0))
        ctk.CTkLabel(warn,
                     text="⚠️  Перед исправлением автоматически создаётся резервная копия реестра в папке .winclare/registry_backups",
                     font=ctk.CTkFont("Segoe UI", 11), text_color="#ed8936").pack(
            padx=16, pady=8, anchor="w")

        # Прогресс
        prog_f = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        prog_f.pack(fill="x", padx=30, pady=(10, 12))
        self.prog_label = ctk.CTkLabel(prog_f, text="Ожидание...",
                                        font=ctk.CTkFont("Segoe UI", 11), text_color="#718096")
        self.prog_label.pack(anchor="w", padx=16, pady=(10, 4))
        self.progress = ctk.CTkProgressBar(prog_f, height=7, corner_radius=4,
                                            progress_color="#4a9eff", fg_color="#2d3748")
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 10))

        # Карточки по типам
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=30, pady=(0, 12))

        # Список проблем
        ctk.CTkLabel(self, text="Найденные проблемы",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", padx=30, pady=(0, 6))

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="#16213e", corner_radius=14)
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=(0, 12))
        self.list_frame.columnconfigure(2, weight=1)

        # Нижняя панель
        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.pack(fill="x", padx=30, pady=(0, 20))
        ctk.CTkButton(bot, text="Выбрать всё", width=120, height=30, corner_radius=8,
                      fg_color="#2d3748", hover_color="#4a5568",
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=lambda: self._select_all(True)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bot, text="Снять всё", width=120, height=30, corner_radius=8,
                      fg_color="#2d3748", hover_color="#4a5568",
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=lambda: self._select_all(False)).pack(side="left")
        self.result_label = ctk.CTkLabel(bot, text="",
                                          font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                                          text_color="#48bb78")
        self.result_label.pack(side="right")

    # ── Сканирование ─────────────────────────────────────────────

    def _start_scan(self):
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
        self._scanned = False
        self.btn_scan.configure(state="disabled")
        self.btn_fix.configure(state="disabled")
        self.result_label.configure(text="")
        self.progress.set(0)
        self.progress.configure(progress_color="#4a9eff")
        for w in self.list_frame.winfo_children():
            w.destroy()
        for w in self.stats_frame.winfo_children():
            w.destroy()
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        def cb(pct, msg):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        issues = self._cleaner.scan(progress_cb=cb)
        self._issues = issues
        self.after(0, lambda: self._on_scan_done(issues))

    def _on_scan_done(self, issues):
        stats = self._cleaner.get_stats()
        self._render_stats(stats)
        self._render_issues(issues)
        n = stats["total"]
        self.summary.configure(
            text=f"Найдено проблем: {n}  •  Создайте бэкап и нажмите «Исправить»" if n
            else "✅ Реестр в порядке — проблем не обнаружено")
        self.prog_label.configure(text=f"✅ Анализ завершён — {n} проблем")
        self._scanned = n > 0
        with self._lock:
            self._is_running = False
        self.btn_scan.configure(state="normal")
        if n > 0:
            self.btn_fix.configure(state="normal")

    def _render_stats(self, stats: dict):
        for w in self.stats_frame.winfo_children():
            w.destroy()
        by_type = stats.get("by_type", {})
        for i, (type_name, count) in enumerate(by_type.items()):
            f = ctk.CTkFrame(self.stats_frame, fg_color="#16213e", corner_radius=10)
            f.grid(row=0, column=i, padx=(0 if i == 0 else 6, 0), sticky="ew")
            self.stats_frame.columnconfigure(i, weight=1)
            ctk.CTkLabel(f, text=str(count),
                         font=ctk.CTkFont("Segoe UI", 18, weight="bold"),
                         text_color="#e94560").pack(pady=(10, 2))
            ctk.CTkLabel(f, text=type_name,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color="#a0aec0", wraplength=120).pack(pady=(0, 10))

    def _render_issues(self, issues):
        self._chk_vars = []
        for w in self.list_frame.winfo_children():
            w.destroy()
        if not issues:
            ctk.CTkLabel(self.list_frame, text="✅  Проблем не найдено",
                         font=ctk.CTkFont("Segoe UI", 13),
                         text_color="#48bb78").grid(row=0, column=0, pady=40)
            return
        for i, iss in enumerate(issues):
            self._add_issue_row(i, iss)

    def _add_issue_row(self, idx, iss: RegistryIssue):
        bg = "#1a1a2e" if idx % 2 == 0 else "#16213e"
        row = ctk.CTkFrame(self.list_frame, fg_color=bg, corner_radius=8)
        row.grid(row=idx, column=0, padx=4, pady=2, sticky="ew")
        row.columnconfigure(2, weight=1)

        var = ctk.BooleanVar(value=iss.selected)
        self._chk_vars.append(var)
        ctk.CTkCheckBox(row, text="", variable=var, width=24,
                         checkbox_width=18, checkbox_height=18,
                         fg_color="#e94560", hover_color="#c73652",
                         command=lambda i=iss, v=var: setattr(i, "selected", v.get()),
                         ).grid(row=0, column=0, padx=(10, 4), pady=10)

        icon = TYPE_ICON.get(iss.issue_type, "⚠️")
        ctk.CTkLabel(row, text=icon, font=ctk.CTkFont("Segoe UI", 16),
                     width=30).grid(row=0, column=1, padx=4)

        ctk.CTkLabel(row, text=iss.description,
                     font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                     text_color="#ffffff" if not iss.fixed else "#48bb78",
                     anchor="w").grid(row=0, column=2, padx=8, sticky="ew")

        short_key = "..." + iss.key_path[-45:] if len(iss.key_path) > 45 else iss.key_path
        ctk.CTkLabel(row, text=f"{iss.hive_name}\\{short_key}",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color="#718096", anchor="w").grid(
            row=1, column=2, padx=8, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(row, text=iss.issue_type.value,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color="#4a9eff", width=180, anchor="e").grid(
            row=0, column=3, rowspan=2, padx=(4, 14))

    # ── Исправление ──────────────────────────────────────────────

    def _start_fix(self):
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
        self.btn_scan.configure(state="disabled")
        self.btn_fix.configure(state="disabled")
        self.progress.set(0)
        self.progress.configure(progress_color="#e94560")
        threading.Thread(target=self._do_fix, daemon=True).start()

    def _do_fix(self):
        backup = self._cleaner.create_backup()
        if backup:
            self.after(0, lambda: self.prog_label.configure(
                text=f"✅ Бэкап создан: {backup}"))

        def cb(pct, msg):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        count = self._cleaner.fix(progress_cb=cb)
        self.after(0, lambda: self._on_fix_done(count))

    def _on_fix_done(self, count):
        self.summary.configure(text=f"✅ Исправлено {count} проблем в реестре")
        self.result_label.configure(text=f"🔧 Исправлено: {count}")
        self.prog_label.configure(text=f"🎉 Исправлено {count} проблем")
        # Перекрашиваем исправленные строки
        self._render_issues(self._issues)
        with self._lock:
            self._is_running = False
        self.btn_scan.configure(state="normal")

    def _select_all(self, val: bool):
        for iss, var in zip(self._issues, self._chk_vars):
            var.set(val)
            iss.selected = val
