"""
WinClare — Страница «Очистка браузеров»
"""
import threading
import customtkinter as ctk
from modules.cleaner.browser_cleaner import BrowserCleaner, get_running_browsers


def _fmt(n: int) -> str:
    if n < 1024:
        return f"{n} Б"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} КБ"
    elif n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} МБ"
    return f"{n / 1024 ** 3:.2f} ГБ"


class BrowserPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._cleaner = BrowserCleaner()
        self._scanned = False
        self._is_running = False
        self._lock = threading.Lock()
        self._browser_vars: dict[str, ctk.BooleanVar] = {}
        self._browser_size_labels: dict[str, ctk.CTkLabel] = {}
        self._cat_vars: dict[str, ctk.BooleanVar] = {}
        self._build()
        # Сразу обнаруживаем браузеры
        threading.Thread(target=self._detect, daemon=True).start()

    # ─────────────────────── Построение UI ───────────────────────

    def _build(self):
        # ── Заголовок ──────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 4))

        ctk.CTkLabel(header, text="🌐  Очистка браузеров",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")

        self.btn_scan = ctk.CTkButton(
            btn_frame, text="🔍  Анализ",
            width=130, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#0f3460", hover_color="#16213e",
            state="disabled",
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

        # ── Строка состояния ────────────────────────────────────────
        self.summary_label = ctk.CTkLabel(
            self, text="⏳  Поиск установленных браузеров...",
            font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0")
        self.summary_label.pack(anchor="w", padx=30, pady=(4, 0))

        # ── Баннер предупреждения об открытых браузерах ──────────────
        self.warn_frame = ctk.CTkFrame(self, fg_color="#2d1b0e",
                                        corner_radius=10)
        # (скрыт по умолчанию, показывается через _check_running_browsers)
        self.warn_label = ctk.CTkLabel(
            self.warn_frame, text="",
            font=ctk.CTkFont("Segoe UI", 11), text_color="#ed8936")
        self.warn_label.pack(padx=16, pady=8, anchor="w")

        # ── Прогресс-бар ────────────────────────────────────────────
        prog_frame = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=12)
        prog_frame.pack(fill="x", padx=30, pady=(12, 16))

        self.prog_label = ctk.CTkLabel(
            prog_frame, text="Обнаружение браузеров...",
            font=ctk.CTkFont("Segoe UI", 11), text_color="#718096")
        self.prog_label.pack(anchor="w", padx=16, pady=(12, 4))

        self.progress = ctk.CTkProgressBar(
            prog_frame, height=8, corner_radius=4,
            progress_color="#4a9eff", fg_color="#2d3748")
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 12))

        # ── Двухколоночный layout: браузеры + категории ─────────────
        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        columns.columnconfigure(0, weight=3)
        columns.columnconfigure(1, weight=2)
        columns.rowconfigure(0, weight=1)

        # ── Левая колонка: список браузеров ─────────────────────────
        left = ctk.CTkFrame(columns, fg_color="transparent")
        left.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        ctk.CTkLabel(left, text="Найденные браузеры",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", pady=(0, 8))

        self.browsers_frame = ctk.CTkScrollableFrame(
            left, fg_color="#16213e", corner_radius=14)
        self.browsers_frame.pack(fill="both", expand=True)
        self.browsers_frame.columnconfigure(0, weight=1)

        self.no_browsers_label = ctk.CTkLabel(
            self.browsers_frame,
            text="⏳  Поиск...",
            font=ctk.CTkFont("Segoe UI", 13),
            text_color="#718096")
        self.no_browsers_label.grid(row=0, column=0, padx=20, pady=40)

        # ── Правая колонка: категории очистки ───────────────────────
        right = ctk.CTkFrame(columns, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(right, text="Что очищать",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", pady=(0, 8))

        cat_frame = ctk.CTkFrame(right, fg_color="#16213e", corner_radius=14)
        cat_frame.pack(fill="both", expand=True)

        for i, cat in enumerate(self._cleaner.get_categories()):
            self._add_category_row(cat_frame, i, cat)

        # ── Итог ────────────────────────────────────────────────────
        self.result_label = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            text_color="#48bb78")
        self.result_label.pack(anchor="e", padx=30, pady=(0, 10))

    def _add_category_row(self, parent, idx: int, cat):
        row = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=10)
        row.pack(fill="x", padx=8, pady=4)

        var = ctk.BooleanVar(value=cat.enabled)
        self._cat_vars[cat.key] = var

        ctk.CTkCheckBox(
            row, text=cat.name, variable=var,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            text_color="#ffffff",
            fg_color="#4a9eff", hover_color="#2d7dd2",
            command=lambda k=cat.key, v=var:
                self._cleaner.set_category_enabled(k, v.get()),
        ).pack(anchor="w", padx=14, pady=(12, 2))

        ctk.CTkLabel(row, text=cat.description,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#718096", anchor="w").pack(
            anchor="w", padx=14, pady=(0, 12))

    def _add_browser_row(self, idx: int, binfo: dict):
        """Добавить строку браузера в список (вызывается после detect)."""
        row = ctk.CTkFrame(self.browsers_frame, fg_color="#1a1a2e", corner_radius=10)
        row.grid(row=idx, column=0, padx=4, pady=4, sticky="ew")
        row.columnconfigure(1, weight=1)

        var = ctk.BooleanVar(value=True)
        self._browser_vars[binfo["key"]] = var

        # Иконка + чекбокс
        ctk.CTkCheckBox(
            row, text="", variable=var, width=24,
            checkbox_width=20, checkbox_height=20,
            fg_color="#4a9eff", hover_color="#2d7dd2",
            command=lambda k=binfo["key"], v=var:
                self._cleaner.set_browser_enabled(k, v.get()),
        ).grid(row=0, column=0, rowspan=2, padx=(10, 2), pady=12)

        ctk.CTkLabel(row, text=binfo["icon"],
                     font=ctk.CTkFont("Segoe UI", 22)).grid(
            row=0, column=1, rowspan=2, padx=(4, 8), pady=12, sticky="w")

        # Имя + кол-во профилей
        n_profiles = len(binfo["profiles"])
        ctk.CTkLabel(row, text=binfo["name"],
                     font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                     text_color="#ffffff", anchor="w").grid(
            row=0, column=2, sticky="sw", pady=(12, 0))
        ctk.CTkLabel(row,
                     text=f"{n_profiles} профил{'ь' if n_profiles==1 else 'я' if n_profiles<5 else 'ей'}",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#718096", anchor="w").grid(
            row=1, column=2, sticky="nw", pady=(0, 12))

        # Размер (справа)
        size_lbl = ctk.CTkLabel(row, text="—",
                                 font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                                 text_color="#a0aec0", width=100, anchor="e")
        size_lbl.grid(row=0, column=3, rowspan=2, padx=14)
        self._browser_size_labels[binfo["key"]] = size_lbl

    # ─────────────────────── Обнаружение браузеров ───────────────

    def _detect(self):
        browsers = self._cleaner.detect_browsers()
        self.after(0, lambda: self._on_detected(browsers))

    def _on_detected(self, browsers: list):
        self.no_browsers_label.destroy()

        if not browsers:
            ctk.CTkLabel(self.browsers_frame,
                         text="❌  Браузеры не найдены",
                         font=ctk.CTkFont("Segoe UI", 13),
                         text_color="#e94560").grid(row=0, column=0, padx=20, pady=40)
            self.summary_label.configure(text="Установленные браузеры не обнаружены")
            return

        for i, binfo in enumerate(browsers):
            self._add_browser_row(i, binfo)

        n = len(browsers)
        self.summary_label.configure(
            text=f"Найдено браузеров: {n}  •  Нажмите «Анализ» для подсчёта кэша")
        self.prog_label.configure(text="Готов к анализу")
        self.btn_scan.configure(state="normal")
        self._check_running_browsers()

    def _check_running_browsers(self):
        """Проверяет, какие браузеры запущены, и показывает/скрывает баннер."""
        running = get_running_browsers()
        # Пересекаем с обнаруженными браузерами
        running_names = [
            b["name"] for b in self._cleaner.detected_browsers
            if b["key"] in running
        ]
        if running_names:
            names_str = ", ".join(running_names)
            self.warn_label.configure(
                text=f"⚠️  Открыты браузеры: {names_str}\n"
                     f"   История и куки не очистятся, пока они запущены. "
                     f"Закройте их перед очисткой для полного результата.")
            self.warn_frame.pack(fill="x", padx=30, pady=(6, 0),
                                  before=self._get_prog_frame())
        else:
            self.warn_frame.pack_forget()

    def _get_prog_frame(self):
        """Возвращает фрейм прогресс-бара для позиционирования баннера."""
        for child in self.winfo_children():
            if isinstance(child, ctk.CTkFrame) and hasattr(self, 'progress'):
                # Ищем фрейм, который содержит self.progress
                try:
                    if self.progress.winfo_parent() == str(child):
                        return child
                except Exception:
                    pass
        return self.progress  # fallback

    # ─────────────────────── Сканирование ────────────────────────

    def _start_scan(self):
        with self._lock:
            if self._is_running:
                return
            self._is_running = True

        self._scanned = False
        self.result_label.configure(text="")
        self.btn_scan.configure(state="disabled")
        self.btn_clean.configure(state="disabled")
        for lbl in self._browser_size_labels.values():
            lbl.configure(text="…", text_color="#a0aec0")
        self.progress.set(0)
        self.progress.configure(progress_color="#4a9eff")
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        def cb(pct, msg):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        self._cleaner.scan(progress_cb=cb)

        # Обновляем размеры по браузерам
        for binfo in self._cleaner.detected_browsers:
            key = binfo["key"]
            total = sum(p.found_size for p in binfo["profiles"])
            lbl = self._browser_size_labels.get(key)
            if lbl:
                if total > 0:
                    self.after(0, lambda l=lbl, t=_fmt(total):
                               l.configure(text=t, text_color="#e94560"))
                else:
                    self.after(0, lambda l=lbl:
                               l.configure(text="Чисто ✅", text_color="#48bb78"))

        total = self._cleaner.total_found
        self.after(0, lambda: self.summary_label.configure(
            text=f"Найдено в браузерах: {_fmt(total)}  •  Нажмите «Очистить»"))
        self.after(0, lambda: self.prog_label.configure(
            text=f"✅ Анализ завершён — {_fmt(total)}"))
        self._scanned = True
        with self._lock:
            self._is_running = False
        self.after(0, lambda: self.btn_scan.configure(state="normal"))
        self.after(0, lambda: self.btn_clean.configure(state="normal"))

    # ─────────────────────── Очистка ─────────────────────────────

    def _start_clean(self):
        with self._lock:
            if self._is_running:
                return
            self._is_running = True

        # Обновляем баннер перед стартом
        self._check_running_browsers()

        self.btn_scan.configure(state="disabled")
        self.btn_clean.configure(state="disabled")
        self.progress.set(0)
        self.progress.configure(progress_color="#e94560")
        self.result_label.configure(text="")
        threading.Thread(target=self._do_clean, daemon=True).start()

    def _do_clean(self):
        def cb(pct, msg):
            self.after(0, lambda: self.progress.set(pct))
            self.after(0, lambda: self.prog_label.configure(text=msg))

        total_bytes, locked_names = self._cleaner.clean(progress_cb=cb)

        for binfo in self._cleaner.detected_browsers:
            key = binfo["key"]
            profiles = binfo["profiles"]
            cleaned  = sum(p.cleaned_size for p in profiles)
            has_lock = any(getattr(p, "db_locked", False) for p in profiles)
            lbl = self._browser_size_labels.get(key)
            if lbl:
                if has_lock:
                    self.after(0, lambda l=lbl, t=_fmt(cleaned):
                               l.configure(
                                   text=f"⚠ {t} (история не очищена)",
                                   text_color="#ed8936"))
                elif cleaned > 0:
                    self.after(0, lambda l=lbl, t=_fmt(cleaned):
                               l.configure(text=f"✅ {t}", text_color="#48bb78"))
                else:
                    self.after(0, lambda l=lbl:
                               l.configure(text="✅ Чисто", text_color="#48bb78"))

        # Финальные сообщения
        if locked_names:
            names_str = ", ".join(locked_names)
            prog_text = (f"✅ Освобождено {_fmt(total_bytes)}  "
                         f"⚠ История не очищена (закройте: {names_str})")
            summary_text = (f"Кэш очищен: {_fmt(total_bytes)}  •  "
                            f"История заблокирована — закройте {names_str}")
        else:
            prog_text = f"🎉 Готово! Освобождено: {_fmt(total_bytes)}"
            summary_text = f"Очистка завершена. Освобождено: {_fmt(total_bytes)}"

        self.after(0, lambda: self.prog_label.configure(text=prog_text))
        self.after(0, lambda: self.summary_label.configure(text=summary_text))
        self.after(0, lambda: self.result_label.configure(
            text=f"💾 Освобождено {_fmt(total_bytes)}"))

        self._scanned = False
        with self._lock:
            self._is_running = False
        self.after(0, lambda: self.btn_scan.configure(state="normal"))
        self.after(0, lambda: self.btn_clean.configure(state="disabled"))
        # Обновляем баннер после очистки
        self.after(500, self._check_running_browsers)
