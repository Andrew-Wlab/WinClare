"""
WinClare — Страница «Менеджер автозагрузки»
"""
import threading
import customtkinter as ctk
from modules.startup.startup_manager import (
    StartupManager, StartupEntry, ImpactLevel, StartupSource
)

# Цвета уровней нагрузки
IMPACT_COLOR = {
    ImpactLevel.HIGH:    "#e94560",
    ImpactLevel.MEDIUM:  "#ed8936",
    ImpactLevel.LOW:     "#48bb78",
    ImpactLevel.UNKNOWN: "#718096",
}
IMPACT_ICON = {
    ImpactLevel.HIGH:    "🔴",
    ImpactLevel.MEDIUM:  "🟡",
    ImpactLevel.LOW:     "🟢",
    ImpactLevel.UNKNOWN: "⚪",
}


class StartupPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._manager  = StartupManager()
        self._entries: list[StartupEntry] = []
        self._rows: list[dict] = []           # dict с виджетами каждой строки
        self._filter_source = "Все"
        self._search_text   = ""
        self._lock          = threading.Lock()
        self._is_loading    = False
        self._build()
        # Загружаем сразу при открытии страницы
        self._start_load()

    # ═══════════════════════════ Построение UI ═══════════════════════════════

    def _build(self):
        # ── Заголовок ────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 4))

        ctk.CTkLabel(header, text="🚀  Менеджер автозагрузки",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")

        self.btn_reload = ctk.CTkButton(
            header, text="🔄  Обновить",
            width=130, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#0f3460", hover_color="#16213e",
            command=self._start_load,
        )
        self.btn_reload.pack(side="right")

        # ── Статус-строка ─────────────────────────────────────────────────────
        self.summary_label = ctk.CTkLabel(
            self, text="⏳  Загрузка записей автозагрузки...",
            font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0")
        self.summary_label.pack(anchor="w", padx=30, pady=(4, 0))

        # ── Прогресс-бар ─────────────────────────────────────────────────────
        prog_frame = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        prog_frame.pack(fill="x", padx=30, pady=(10, 14))

        self.prog_label = ctk.CTkLabel(
            prog_frame, text="Инициализация...",
            font=ctk.CTkFont("Segoe UI", 11), text_color="#718096")
        self.prog_label.pack(anchor="w", padx=16, pady=(10, 4))

        self.progress = ctk.CTkProgressBar(
            prog_frame, height=6, corner_radius=4,
            progress_color="#4a9eff", fg_color="#2d3748")
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 10))

        # ── Карточки статистики ───────────────────────────────────────────────
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=30, pady=(0, 14))
        stats_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="s")

        self._stat_total    = self._make_stat(stats_frame, 0, "Всего записей",   "—",  "#4a9eff")
        self._stat_enabled  = self._make_stat(stats_frame, 1, "Включено",        "—",  "#48bb78")
        self._stat_disabled = self._make_stat(stats_frame, 2, "Отключено",       "—",  "#718096")
        self._stat_high     = self._make_stat(stats_frame, 3, "Высокая нагрузка","—",  "#e94560")

        # ── Панель фильтров ───────────────────────────────────────────────────
        filter_frame = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        filter_frame.pack(fill="x", padx=30, pady=(0, 10))
        filter_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(filter_frame, text="Источник:",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color="#a0aec0").grid(row=0, column=0, padx=(16, 8), pady=10)

        self.source_filter = ctk.CTkOptionMenu(
            filter_frame,
            values=["Все", "Реестр (пользователь)", "Реестр (система)",
                    "Папка автозагрузки", "Планировщик задач"],
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color="#0f3460", button_color="#0f3460",
            button_hover_color="#16213e", dropdown_fg_color="#1a1a2e",
            width=220, height=32,
            command=self._on_filter_change,
        )
        self.source_filter.grid(row=0, column=1, padx=0, pady=10, sticky="w")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search())
        ctk.CTkEntry(
            filter_frame,
            placeholder_text="🔍  Поиск по названию...",
            textvariable=self.search_var,
            font=ctk.CTkFont("Segoe UI", 12),
            height=32, width=220,
            fg_color="#0f3460", border_color="#2d3748",
        ).grid(row=0, column=2, padx=(12, 16), pady=10, sticky="e")

        # ── Шапка таблицы ────────────────────────────────────────────────────
        thead = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=0)
        thead.pack(fill="x", padx=30)
        thead.columnconfigure(2, weight=1)

        for col, (text, w) in enumerate([
            ("", 36), ("Нагрузка", 90), ("Название программы", 0),
            ("Источник", 170), ("Издатель", 150),
            ("Статус", 90), ("Действия", 130),
        ]):
            ctk.CTkLabel(thead, text=text,
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color="#718096",
                         width=w if w else 0,
                         anchor="w" if col == 2 else "center",
                         ).grid(row=0, column=col,
                                padx=(8 if col == 0 else 4, 4),
                                pady=6,
                                sticky="ew" if col == 2 else "")

        # ── Список записей (прокручиваемый) ──────────────────────────────────
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color="#16213e", corner_radius=14)
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=(4, 20))
        self.list_frame.columnconfigure(2, weight=1)

        self._loading_label = ctk.CTkLabel(
            self.list_frame, text="⏳  Загрузка...",
            font=ctk.CTkFont("Segoe UI", 14), text_color="#718096")
        self._loading_label.grid(row=0, column=0, columnspan=7, pady=60)

    def _make_stat(self, parent, col, title, val, color):
        f = ctk.CTkFrame(parent, fg_color="#16213e", corner_radius=12)
        f.grid(row=0, column=col,
               padx=(0 if col == 0 else 6, 0), sticky="ew")
        lbl_val = ctk.CTkLabel(f, text=val,
                                font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                                text_color=color)
        lbl_val.pack(pady=(12, 2))
        ctk.CTkLabel(f, text=title,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#a0aec0").pack(pady=(0, 12))
        return lbl_val

    # ═══════════════════════════ Загрузка ════════════════════════════════════

    def _start_load(self):
        with self._lock:
            if self._is_loading:
                return
            self._is_loading = True

        self.btn_reload.configure(state="disabled")
        self.progress.set(0)
        self._clear_rows()
        self._loading_label = ctk.CTkLabel(
            self.list_frame, text="⏳  Загрузка записей...",
            font=ctk.CTkFont("Segoe UI", 14), text_color="#718096")
        self._loading_label.grid(row=0, column=0, columnspan=7, pady=60)
        threading.Thread(target=self._do_load, daemon=True).start()

    def _do_load(self):
        def cb(pct, msg):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        entries = self._manager.load(progress_cb=cb)
        self.after(0, lambda: self._on_loaded(entries))

    def _on_loaded(self, entries: list[StartupEntry]):
        self._entries = entries
        self._update_stats()
        self._render_rows(entries)
        stats = self._manager.get_stats()
        self.summary_label.configure(
            text=f"Загружено {stats['total']} записей  •  "
                 f"Включено: {stats['enabled']}  •  "
                 f"Отключено: {stats['disabled']}  •  "
                 f"Высокая нагрузка: {stats['high_impact']}")
        self.prog_label.configure(
            text=f"✅ Готово — {stats['total']} записей автозагрузки")
        with self._lock:
            self._is_loading = False
        self.btn_reload.configure(state="normal")

    # ═══════════════════════════ Рендер строк ════════════════════════════════

    def _clear_rows(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._rows = []

    def _render_rows(self, entries: list[StartupEntry]):
        self._clear_rows()
        visible = self._apply_filter(entries)
        if not visible:
            ctk.CTkLabel(self.list_frame,
                         text="Ничего не найдено",
                         font=ctk.CTkFont("Segoe UI", 13),
                         text_color="#718096").grid(
                row=0, column=0, columnspan=7, pady=40)
            return

        for i, entry in enumerate(visible):
            self._add_row(i, entry)

    def _add_row(self, row_idx: int, entry: StartupEntry):
        bg = "#1a1a2e" if row_idx % 2 == 0 else "#16213e"
        row = ctk.CTkFrame(self.list_frame, fg_color=bg, corner_radius=8, height=48)
        row.grid(row=row_idx, column=0, columnspan=7,
                 padx=4, pady=2, sticky="ew")
        row.columnconfigure(2, weight=1)
        row.grid_propagate(False)

        # Вкл/выкл переключатель
        sw_var = ctk.BooleanVar(value=entry.enabled)
        sw = ctk.CTkSwitch(
            row, text="", variable=sw_var, width=46, height=22,
            progress_color="#48bb78", button_color="#ffffff",
            command=lambda e=entry, v=sw_var: self._toggle(e, v),
        )
        sw.grid(row=0, column=0, padx=(10, 4), pady=0)

        # Нагрузка
        ctk.CTkLabel(row,
                     text=IMPACT_ICON[entry.impact],
                     font=ctk.CTkFont("Segoe UI", 14),
                     width=90, anchor="center",
                     ).grid(row=0, column=1, padx=4)

        # Название
        name_color = "#ffffff" if entry.enabled else "#4a5568"
        name_lbl = ctk.CTkLabel(row,
                                  text=entry.name,
                                  font=ctk.CTkFont("Segoe UI", 12,
                                                   weight="bold" if entry.enabled else "normal"),
                                  text_color=name_color,
                                  anchor="w")
        name_lbl.grid(row=0, column=2, padx=8, sticky="ew")
        # Подсказка с полной командой
        name_lbl.bind("<Enter>", lambda e, cmd=entry.command:
                      self.summary_label.configure(text=f"Команда: {cmd}"))
        name_lbl.bind("<Leave>", lambda e: self._restore_summary())

        # Источник
        ctk.CTkLabel(row,
                     text=entry.source.value,
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color="#718096", width=170, anchor="center",
                     wraplength=165,
                     ).grid(row=0, column=3, padx=4)

        # Издатель
        pub = entry.publisher or "—"
        if len(pub) > 20:
            pub = pub[:18] + "…"
        ctk.CTkLabel(row, text=pub,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#a0aec0", width=150, anchor="center",
                     ).grid(row=0, column=4, padx=4)

        # Статус
        status_text  = "Включено"  if entry.enabled else "Отключено"
        status_color = "#48bb78"   if entry.enabled else "#718096"
        status_lbl = ctk.CTkLabel(row, text=status_text,
                                   font=ctk.CTkFont("Segoe UI", 11),
                                   text_color=status_color, width=90)
        status_lbl.grid(row=0, column=5, padx=4)

        # Кнопка удаления
        ctk.CTkButton(
            row, text="🗑", width=36, height=28,
            corner_radius=6, fg_color="#2d3748", hover_color="#e94560",
            font=ctk.CTkFont("Segoe UI", 13),
            command=lambda e=entry, r=row, sl=status_lbl, sw_=sw, v=sw_var:
                self._delete(e, r, sl, sw_, v),
        ).grid(row=0, column=6, padx=(4, 10))

        self._rows.append({
            "entry": entry, "row": row,
            "status_lbl": status_lbl, "sw": sw, "sw_var": sw_var,
        })

    # ═══════════════════════════ Действия ════════════════════════════════════

    def _toggle(self, entry: StartupEntry, var: ctk.BooleanVar):
        want_enabled = var.get()
        ok = (self._manager.enable(entry) if want_enabled
              else self._manager.disable(entry))
        if not ok:
            # Откатываем переключатель
            var.set(not want_enabled)
            return
        # Обновляем лейбл статуса в строке
        for row_d in self._rows:
            if row_d["entry"] is entry:
                color = "#48bb78" if entry.enabled else "#718096"
                text  = "Включено" if entry.enabled else "Отключено"
                row_d["status_lbl"].configure(text=text, text_color=color)
                break
        self._update_stats()

    def _delete(self, entry: StartupEntry, row_frame, status_lbl, sw, sw_var):
        """Удаляет запись с подтверждением (всплывающее окно)."""
        # Диалог подтверждения
        dlg = ctk.CTkToplevel(self)
        dlg.title("Подтверждение удаления")
        dlg.geometry("420x180")
        dlg.resizable(False, False)
        dlg.grab_set()

        ctk.CTkLabel(dlg,
                     text=f"Удалить запись автозагрузки?\n\n«{entry.name}»",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color="#ffffff", wraplength=380).pack(pady=(24, 16))

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack()

        def confirm():
            dlg.destroy()
            ok = self._manager.delete(entry)
            if ok:
                row_frame.destroy()
                self._rows = [r for r in self._rows if r["entry"] is not entry]
                self._update_stats()

        ctk.CTkButton(btn_row, text="Удалить", width=110, height=34,
                      fg_color="#e94560", hover_color="#c73652",
                      command=confirm).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Отмена", width=110, height=34,
                      fg_color="#2d3748", hover_color="#4a5568",
                      command=dlg.destroy).pack(side="left", padx=8)

    # ═══════════════════════════ Фильтры ═════════════════════════════════════

    SOURCE_MAP = {
        "Все":                    None,
        "Реестр (пользователь)":  [StartupSource.REGISTRY_HKCU,
                                    StartupSource.REGISTRY_HKCU_ONCE],
        "Реестр (система)":       [StartupSource.REGISTRY_HKLM,
                                    StartupSource.REGISTRY_HKLM_ONCE],
        "Папка автозагрузки":     [StartupSource.FOLDER_USER,
                                    StartupSource.FOLDER_ALL],
        "Планировщик задач":      [StartupSource.TASK_SCHEDULER],
    }

    def _apply_filter(self, entries: list[StartupEntry]) -> list[StartupEntry]:
        result = entries
        # Фильтр по источнику
        allowed = self.SOURCE_MAP.get(self._filter_source)
        if allowed:
            result = [e for e in result if e.source in allowed]
        # Поиск по тексту
        q = self._search_text.lower()
        if q:
            result = [e for e in result
                      if q in e.name.lower()
                      or q in e.command.lower()
                      or q in e.publisher.lower()]
        return result

    def _on_filter_change(self, value: str):
        self._filter_source = value
        self._render_rows(self._entries)

    def _on_search(self):
        self._search_text = self.search_var.get()
        self._render_rows(self._entries)

    # ═══════════════════════════ Утилиты ═════════════════════════════════════

    def _update_stats(self):
        stats = self._manager.get_stats()
        self._stat_total.configure(text=str(stats["total"]))
        self._stat_enabled.configure(text=str(stats["enabled"]))
        self._stat_disabled.configure(text=str(stats["disabled"]))
        self._stat_high.configure(text=str(stats["high_impact"]))

    def _restore_summary(self):
        stats = self._manager.get_stats()
        self.summary_label.configure(
            text=f"Загружено {stats['total']} записей  •  "
                 f"Включено: {stats['enabled']}  •  "
                 f"Отключено: {stats['disabled']}  •  "
                 f"Высокая нагрузка: {stats['high_impact']}")
