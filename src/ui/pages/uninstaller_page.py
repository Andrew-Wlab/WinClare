"""
WinClare — Страница «Деинсталлятор программ»
"""
import threading
import customtkinter as ctk
from modules.uninstaller.uninstaller import Uninstaller, InstalledApp


class UninstallerPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._uninstaller = Uninstaller()
        self._apps: list[InstalledApp] = []
        self._filtered: list[InstalledApp] = []
        self._lock = threading.Lock()
        self._is_loading = False
        self._build()
        threading.Thread(target=self._do_load, daemon=True).start()

    def _build(self):
        # Заголовок
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 4))
        ctk.CTkLabel(header, text="🗑️  Деинсталлятор программ",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")
        self.btn_reload = ctk.CTkButton(
            header, text="🔄  Обновить", width=130, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#0f3460", hover_color="#16213e",
            command=self._reload)
        self.btn_reload.pack(side="right")

        self.summary = ctk.CTkLabel(
            self, text="⏳  Загрузка списка программ...",
            font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0")
        self.summary.pack(anchor="w", padx=30, pady=(4, 0))

        # Прогресс
        prog_f = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        prog_f.pack(fill="x", padx=30, pady=(10, 10))
        self.prog_label = ctk.CTkLabel(prog_f, text="Загрузка...",
                                        font=ctk.CTkFont("Segoe UI", 11), text_color="#718096")
        self.prog_label.pack(anchor="w", padx=16, pady=(10, 4))
        self.progress = ctk.CTkProgressBar(prog_f, height=6, corner_radius=4,
                                            progress_color="#4a9eff", fg_color="#2d3748")
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 10))

        # Карточки
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", padx=30, pady=(0, 10))
        cards.columnconfigure((0, 1, 2), weight=1, uniform="c")
        self._card_total  = self._stat(cards, 0, "Программ установлено", "—", "#4a9eff")
        self._card_size   = self._stat(cards, 1, "Общий размер",          "—", "#ed8936")
        self._card_filter = self._stat(cards, 2, "Показано",              "—", "#48bb78")

        # Поиск + сортировка
        ctrl = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        ctrl.pack(fill="x", padx=30, pady=(0, 8))
        ctrl.columnconfigure(1, weight=1)

        ctk.CTkLabel(ctrl, text="🔍", font=ctk.CTkFont("Segoe UI", 16),
                     text_color="#a0aec0").grid(row=0, column=0, padx=(16, 4), pady=10)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        ctk.CTkEntry(ctrl, textvariable=self.search_var,
                     placeholder_text="Поиск по названию или издателю...",
                     font=ctk.CTkFont("Segoe UI", 12),
                     height=32, fg_color="#0f3460", border_color="#2d3748"
                     ).grid(row=0, column=1, padx=4, pady=10, sticky="ew")

        self.sort_var = ctk.StringVar(value="По размеру ↓")
        ctk.CTkOptionMenu(ctrl,
                          values=["По размеру ↓", "По размеру ↑",
                                  "По названию А-Я", "По дате (новые)"],
                          variable=self.sort_var,
                          font=ctk.CTkFont("Segoe UI", 12),
                          fg_color="#0f3460", button_color="#0f3460",
                          button_hover_color="#16213e", dropdown_fg_color="#1a1a2e",
                          width=180, height=32,
                          command=lambda _: self._apply_filter()
                          ).grid(row=0, column=2, padx=(4, 16), pady=10)

        # Шапка таблицы
        thead = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=0)
        thead.pack(fill="x", padx=30)
        thead.columnconfigure(0, weight=1)
        for col, (text, w) in enumerate([
            ("Название программы", 0), ("Версия", 100),
            ("Издатель", 160), ("Дата", 90), ("Размер", 90), ("", 120),
        ]):
            ctk.CTkLabel(thead, text=text,
                         font=ctk.CTkFont("Segoe UI", 11), text_color="#718096",
                         width=w if w else 0,
                         anchor="w" if col == 0 else "center",
                         ).grid(row=0, column=col, padx=(8 if col == 0 else 4, 4),
                                pady=6, sticky="ew" if col == 0 else "")

        # Список
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="#16213e", corner_radius=14)
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=(4, 20))
        self.list_frame.columnconfigure(0, weight=1)

        self._placeholder = ctk.CTkLabel(
            self.list_frame, text="⏳  Загрузка...",
            font=ctk.CTkFont("Segoe UI", 13), text_color="#718096")
        self._placeholder.grid(row=0, column=0, pady=60)

    def _stat(self, parent, col, title, val, color):
        f = ctk.CTkFrame(parent, fg_color="#16213e", corner_radius=12)
        f.grid(row=0, column=col, padx=(0 if col == 0 else 8, 0), sticky="ew")
        lbl = ctk.CTkLabel(f, text=val,
                            font=ctk.CTkFont("Segoe UI", 20, weight="bold"),
                            text_color=color)
        lbl.pack(pady=(12, 2))
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#a0aec0").pack(pady=(0, 12))
        return lbl

    # ── Загрузка ─────────────────────────────────────────────────

    def _reload(self):
        with self._lock:
            if self._is_loading:
                return
            self._is_loading = True
        self.btn_reload.configure(state="disabled")
        self.progress.set(0)
        for w in self.list_frame.winfo_children():
            w.destroy()
        threading.Thread(target=self._do_load, daemon=True).start()

    def _do_load(self):
        def cb(pct, msg):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        apps = self._uninstaller.load(progress_cb=cb)
        self.after(0, lambda: self._on_loaded(apps))

    def _on_loaded(self, apps):
        self._apps = apps
        total_size = self._uninstaller.get_total_size()
        n = len(apps)

        def _fmtsz(b):
            for u in ("КБ","МБ","ГБ","ТБ"):
                if b < 1024: return f"{b:.1f} {u}"
                b /= 1024
            return f"{b:.1f} ТБ"

        self._card_total.configure(text=str(n))
        self._card_size.configure(text=_fmtsz(total_size) if total_size else "—")
        self.summary.configure(text=f"Установлено программ: {n}  •  Найдите и удалите ненужные")
        self.prog_label.configure(text=f"✅ Загружено {n} программ")
        self._apply_filter()
        with self._lock:
            self._is_loading = False
        self.btn_reload.configure(state="normal")

    # ── Фильтр + рендер ──────────────────────────────────────────

    def _apply_filter(self):
        q = self.search_var.get().lower()
        apps = self._apps if not q else self._uninstaller.search(q)

        sort = self.sort_var.get()
        if sort == "По размеру ↑":
            apps = sorted(apps, key=lambda a: a.size_bytes)
        elif sort == "По названию А-Я":
            apps = sorted(apps, key=lambda a: a.name.lower())
        elif sort == "По дате (новые)":
            apps = sorted(apps, key=lambda a: a.install_date, reverse=True)
        else:
            apps = sorted(apps, key=lambda a: a.size_bytes, reverse=True)

        self._filtered = apps
        self._card_filter.configure(text=str(len(apps)))
        self._render_list(apps)

    def _render_list(self, apps):
        for w in self.list_frame.winfo_children():
            w.destroy()
        if not apps:
            ctk.CTkLabel(self.list_frame, text="Ничего не найдено",
                         font=ctk.CTkFont("Segoe UI", 13),
                         text_color="#718096").grid(row=0, column=0, pady=40)
            return
        for i, app in enumerate(apps[:500]):
            self._add_row(i, app)

    def _add_row(self, idx: int, app: InstalledApp):
        bg = "#1a1a2e" if idx % 2 == 0 else "#16213e"
        row = ctk.CTkFrame(self.list_frame, fg_color=bg, corner_radius=8, height=48)
        row.grid(row=idx, column=0, padx=4, pady=2, sticky="ew")
        row.columnconfigure(0, weight=1)
        row.grid_propagate(False)

        # Название
        ctk.CTkLabel(row, text=app.name,
                     font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                     text_color="#ffffff", anchor="w"
                     ).grid(row=0, column=0, padx=(12, 4), sticky="ew")

        # Версия
        ctk.CTkLabel(row, text=app.version or "—",
                     font=ctk.CTkFont("Segoe UI", 11), text_color="#718096",
                     width=100, anchor="center"
                     ).grid(row=0, column=1, padx=4)

        # Издатель
        pub = app.publisher[:22] + "…" if len(app.publisher) > 22 else app.publisher or "—"
        ctk.CTkLabel(row, text=pub, font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#a0aec0", width=160, anchor="center"
                     ).grid(row=0, column=2, padx=4)

        # Дата
        ctk.CTkLabel(row, text=app.date_str,
                     font=ctk.CTkFont("Segoe UI", 11), text_color="#718096",
                     width=90, anchor="center"
                     ).grid(row=0, column=3, padx=4)

        # Размер
        size_color = "#ed8936" if app.size_bytes > 500 * 1024 * 1024 else "#a0aec0"
        ctk.CTkLabel(row, text=app.size_str,
                     font=ctk.CTkFont("Segoe UI", 11), text_color=size_color,
                     width=90, anchor="center"
                     ).grid(row=0, column=4, padx=4)

        # Кнопка удаления
        ctk.CTkButton(row, text="Удалить", width=100, height=28,
                      corner_radius=8, fg_color="#2d3748", hover_color="#e94560",
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=lambda a=app, r=row: self._confirm_uninstall(a, r)
                      ).grid(row=0, column=5, padx=(4, 10))

    def _confirm_uninstall(self, app: InstalledApp, row_frame):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Удаление программы")
        dlg.geometry("440x200")
        dlg.resizable(False, False)
        dlg.grab_set()

        ctk.CTkLabel(dlg,
                     text=f"Удалить программу?\n\n«{app.name}»\n{app.publisher}",
                     font=ctk.CTkFont("Segoe UI", 13), text_color="#ffffff",
                     wraplength=400).pack(pady=(20, 16))

        btn_f = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_f.pack()

        def do_uninstall():
            dlg.destroy()
            ok = self._uninstaller.uninstall(app)
            if ok:
                row_frame.destroy()
                self._apps = [a for a in self._apps if a is not app]
                n = len(self._apps)
                self._card_total.configure(text=str(n))
                self._card_filter.configure(text=str(
                    len([a for a in self._filtered if a is not app])))
                self.summary.configure(
                    text=f"Удаление запущено: {app.name}  •  Дождитесь завершения")

        ctk.CTkButton(btn_f, text="Удалить", width=120, height=36,
                      fg_color="#e94560", hover_color="#c73652",
                      command=do_uninstall).pack(side="left", padx=8)
        ctk.CTkButton(btn_f, text="Отмена", width=120, height=36,
                      fg_color="#2d3748", hover_color="#4a5568",
                      command=dlg.destroy).pack(side="left", padx=8)
