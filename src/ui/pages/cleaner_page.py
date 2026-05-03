"""
WinClare — Страница «Очистка мусора»
"""
import threading
import customtkinter as ctk
from modules.cleaner.junk_cleaner import JunkCleaner


def _fmt(n: int) -> str:
    if n < 1024:
        return f"{n} Б"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} КБ"
    elif n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} МБ"
    return f"{n / 1024 ** 3:.2f} ГБ"


class CleanerPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._cleaner = JunkCleaner()
        self._scanned = False
        self._lock = threading.Lock()      # ← FIX: защита от race condition
        self._is_running = False           # ← FIX: флаг активной операции
        self._checkboxes: dict[str, ctk.BooleanVar] = {}
        self._size_labels: dict[str, ctk.CTkLabel] = {}
        self._build()

    # ─────────────────────── Построение UI ───────────────────────

    def _build(self):
        # ── Заголовок ──────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 4))

        ctk.CTkLabel(header, text="🧹  Очистка мусора",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")

        self.btn_scan = ctk.CTkButton(
            btn_frame, text="🔍  Анализ",
            width=130, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#0f3460", hover_color="#16213e",
            command=self._start_scan,
        )
        self.btn_scan.pack(side="left", padx=(0, 8))

        self.btn_clean = ctk.CTkButton(
            btn_frame, text="🧹  Очистить",
            width=140, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#e94560", hover_color="#c73652",
            state="disabled",
            command=self._start_clean,
        )
        self.btn_clean.pack(side="left")

        # ── Итоговая строка ─────────────────────────────────────────
        self.summary_label = ctk.CTkLabel(
            self, text="Нажмите «Анализ» — найдём весь мусор на вашем компьютере",
            font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0")
        self.summary_label.pack(anchor="w", padx=30, pady=(4, 0))

        # ── Прогресс-бар ────────────────────────────────────────────
        prog_frame = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        prog_frame.pack(fill="x", padx=30, pady=(12, 16))

        self.prog_label = ctk.CTkLabel(
            prog_frame, text="Ожидание...",
            font=ctk.CTkFont("Segoe UI", 11), text_color="#718096")
        self.prog_label.pack(anchor="w", padx=16, pady=(12, 4))

        self.progress = ctk.CTkProgressBar(
            prog_frame, height=8, corner_radius=4,
            progress_color="#4a9eff", fg_color="#2d3748")
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 12))

        # ── Список категорий ────────────────────────────────────────
        ctk.CTkLabel(self, text="Категории очистки",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", padx=30, pady=(0, 8))

        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color="#16213e", corner_radius=14)
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=(0, 12))
        self.list_frame.columnconfigure(0, weight=1)

        for i, target in enumerate(self._cleaner.get_targets()):
            self._add_target_row(i, target)

        # ── Нижняя панель ───────────────────────────────────────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=30, pady=(0, 20))

        ctk.CTkButton(bottom, text="Выбрать всё", width=120, height=30,
                      corner_radius=8, fg_color="#2d3748", hover_color="#4a5568",
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=lambda: self._select_all(True)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bottom, text="Снять всё", width=120, height=30,
                      corner_radius=8, fg_color="#2d3748", hover_color="#4a5568",
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=lambda: self._select_all(False)).pack(side="left")

        self.result_label = ctk.CTkLabel(
            bottom, text="",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            text_color="#48bb78")
        self.result_label.pack(side="right")

    def _add_target_row(self, row_idx: int, target):
        row = ctk.CTkFrame(self.list_frame, fg_color="#1a1a2e", corner_radius=10)
        row.grid(row=row_idx, column=0, padx=4, pady=4, sticky="ew")
        row.columnconfigure(1, weight=1)

        var = ctk.BooleanVar(value=target.enabled)
        self._checkboxes[target.key] = var

        ctk.CTkCheckBox(
            row, text="", variable=var, width=24,
            checkbox_width=20, checkbox_height=20,
            fg_color="#e94560", hover_color="#c73652",
            command=lambda k=target.key, v=var: self._on_toggle(k, v.get()),
        ).grid(row=0, column=0, rowspan=2, padx=(14, 6), pady=12)

        ctk.CTkLabel(row, text=target.name,
                     font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                     text_color="#ffffff", anchor="w").grid(
            row=0, column=1, sticky="sw", pady=(12, 0))
        ctk.CTkLabel(row, text=target.description,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#718096", anchor="w").grid(
            row=1, column=1, sticky="nw", pady=(0, 12))

        size_lbl = ctk.CTkLabel(row, text="—",
                                 font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                                 text_color="#a0aec0", width=110, anchor="e")
        size_lbl.grid(row=0, column=2, rowspan=2, padx=16)
        self._size_labels[target.key] = size_lbl

    # ─────────────────────── Действия ────────────────────────────

    def _on_toggle(self, key: str, enabled: bool):
        self._cleaner.set_enabled(key, enabled)

    def _select_all(self, value: bool):
        for key, var in self._checkboxes.items():
            var.set(value)
            self._cleaner.set_enabled(key, value)

    def _set_buttons(self, busy: bool = False):
        """Блокировать/разблокировать кнопки."""
        scan_state  = "disabled" if busy else "normal"
        clean_state = "disabled" if (busy or not self._scanned) else "normal"
        self.btn_scan.configure(state=scan_state)
        self.btn_clean.configure(state=clean_state)

    # ── Сканирование ─────────────────────────────────────────────

    def _start_scan(self):
        # ← FIX: проверяем флаг до запуска потока
        with self._lock:
            if self._is_running:
                return
            self._is_running = True

        self._scanned = False
        self.result_label.configure(text="")
        self._set_buttons(busy=True)
        self.progress.set(0)
        self.progress.configure(progress_color="#4a9eff")
        for lbl in self._size_labels.values():
            lbl.configure(text="…", text_color="#a0aec0")
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        def cb(pct: float, msg: str):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        self._cleaner.scan(progress_cb=cb)

        for target in self._cleaner.get_targets():
            lbl = self._size_labels.get(target.key)
            if lbl:
                if target.found_size > 0:
                    self.after(0, lambda l=lbl, t=_fmt(target.found_size):
                               l.configure(text=t, text_color="#e94560"))
                else:
                    self.after(0, lambda l=lbl:
                               l.configure(text="Чисто ✅", text_color="#48bb78"))

        total = self._cleaner.total_found
        self.after(0, lambda: self.summary_label.configure(
            text=f"Найдено мусора: {_fmt(total)}   •   Нажмите «Очистить»"))
        self.after(0, lambda: self.prog_label.configure(
            text=f"✅ Анализ завершён — найдено {_fmt(total)}"))

        self._scanned = True
        with self._lock:
            self._is_running = False
        self.after(0, lambda: self._set_buttons(busy=False))

    # ── Очистка ──────────────────────────────────────────────────

    def _start_clean(self):
        with self._lock:
            if self._is_running:
                return
            self._is_running = True

        self._set_buttons(busy=True)
        self.progress.set(0)
        self.progress.configure(progress_color="#e94560")
        self.result_label.configure(text="")
        threading.Thread(target=self._do_clean, daemon=True).start()

    def _do_clean(self):
        def cb(pct: float, msg: str):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        self._cleaner.clean(progress_cb=cb)

        for target in self._cleaner.get_targets():
            lbl = self._size_labels.get(target.key)
            if lbl and target.enabled:
                cleaned  = target.cleaned_size
                skipped  = target.skipped_count
                if cleaned > 0 and skipped == 0:
                    txt = f"✅ {_fmt(cleaned)}"
                    col = "#48bb78"
                elif cleaned > 0 and skipped > 0:
                    # ← FIX: показываем пропущенные файлы
                    txt = f"✅ {_fmt(cleaned)}  ⚠ {skipped} зaбл."
                    col = "#ed8936"
                elif skipped > 0:
                    txt = f"⚠ {skipped} файл(ов) заблокировано"
                    col = "#ed8936"
                else:
                    txt = "✅ Чисто"
                    col = "#48bb78"
                self.after(0, lambda l=lbl, t=txt, c=col:
                           l.configure(text=t, text_color=c))

        total   = self._cleaner.total_cleaned
        skipped = sum(t.skipped_count for t in self._cleaner.get_targets())

        summary = f"Освобождено {_fmt(total)}"
        if skipped > 0:
            summary += f"  •  ⚠ {skipped} файл(ов) пропущено (используются)"

        self.after(0, lambda: self.prog_label.configure(
            text=f"🎉 Очистка завершена! {summary}"))
        self.after(0, lambda: self.summary_label.configure(text=summary))
        self.after(0, lambda: self.result_label.configure(
            text=f"💾 Освобождено {_fmt(total)}"))

        self._scanned = False
        with self._lock:
            self._is_running = False
        self.after(0, lambda: self._set_buttons(busy=False))
