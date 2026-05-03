"""
WinClare — Страница «Настройки»
"""
import os
import sys
import subprocess
import winreg
import customtkinter as ctk
from utils.settings import load_settings, save_settings

APP_NAME    = "WinClare"
STARTUP_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
VERSION     = "v0.1.0"


def _get_exe_path() -> str:
    """Путь к запускаемому файлу (main.py или .exe после сборки)."""
    if getattr(sys, "frozen", False):
        return sys.executable
    main_py = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "main.py")
    return f'pythonw "{os.path.normpath(main_py)}"'


def _set_startup(enabled: bool):
    """Добавляет или удаляет WinClare из автозапуска Windows."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY,
                             0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass


def _open_log_folder():
    log_dir = os.path.join(os.path.expanduser("~"), ".winclare", "logs")
    os.makedirs(log_dir, exist_ok=True)
    subprocess.Popen(f'explorer "{log_dir}"')


def _open_backup_folder():
    bk_dir = os.path.join(os.path.expanduser("~"), ".winclare", "registry_backups")
    os.makedirs(bk_dir, exist_ok=True)
    subprocess.Popen(f'explorer "{bk_dir}"')


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._s = load_settings()
        self._build()

    # ── Построение UI ────────────────────────────────────────────────────────

    def _build(self):
        # Заголовок
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 4))
        ctk.CTkLabel(header, text="⚙️  Настройки",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(header, text=f"WinClare {VERSION}",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color="#4a5568").pack(side="right")

        self.status_lbl = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont("Segoe UI", 12), text_color="#48bb78")
        self.status_lbl.pack(anchor="w", padx=30, pady=(2, 0))

        # Прокручиваемый контейнер
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=30, pady=(10, 20))
        scroll.columnconfigure(0, weight=1)

        row = 0

        # ── Раздел: Запуск ───────────────────────────────────────────────────
        row = self._section(scroll, row, "🚀  Запуск")

        self._var_startup = ctk.BooleanVar(
            value=self._s.get("run_on_startup", False))
        row = self._toggle(scroll, row,
                           "Запускать WinClare вместе с Windows",
                           "Добавляет запись в автозагрузку (HKCU\\Run)",
                           self._var_startup,
                           self._on_startup_toggle)

        self._var_minimized = ctk.BooleanVar(
            value=self._s.get("start_minimized", False))
        row = self._toggle(scroll, row,
                           "Запускать свёрнутым",
                           "Окно не будет показываться при старте",
                           self._var_minimized,
                           lambda: self._save("start_minimized",
                                              self._var_minimized.get()))

        self._var_scan_start = ctk.BooleanVar(
            value=self._s.get("auto_scan_on_start", False))
        row = self._toggle(scroll, row,
                           "Сканировать при открытии",
                           "Автоматически запускает анализ мусора при старте",
                           self._var_scan_start,
                           lambda: self._save("auto_scan_on_start",
                                              self._var_scan_start.get()))

        # ── Раздел: Авто-очистка ─────────────────────────────────────────────
        row = self._section(scroll, row, "🗓️  Авто-очистка по расписанию")

        self._var_auto = ctk.BooleanVar(
            value=self._s.get("auto_clean_enabled", False))
        row = self._toggle(scroll, row,
                           "Включить авто-очистку",
                           "Программа будет автоматически чистить мусор по расписанию",
                           self._var_auto,
                           lambda: self._save("auto_clean_enabled",
                                              self._var_auto.get()))

        # Интервал
        interval_f = ctk.CTkFrame(scroll, fg_color="#16213e", corner_radius=12)
        interval_f.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        row += 1
        ctk.CTkLabel(interval_f, text="Периодичность очистки",
                     font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(interval_f,
                     text="Как часто WinClare будет автоматически удалять мусор",
                     font=ctk.CTkFont("Segoe UI", 11), text_color="#718096").pack(
            anchor="w", padx=16)
        self._var_interval = ctk.StringVar(
            value=self._interval_label(self._s.get("auto_clean_interval", "weekly")))
        ctk.CTkOptionMenu(interval_f,
                          values=["Ежедневно", "Еженедельно", "Ежемесячно"],
                          variable=self._var_interval,
                          font=ctk.CTkFont("Segoe UI", 12),
                          fg_color="#0f3460", button_color="#0f3460",
                          button_hover_color="#16213e",
                          dropdown_fg_color="#1a1a2e",
                          width=200, height=32,
                          command=self._on_interval_change).pack(
            anchor="w", padx=16, pady=(8, 14))

        # ── Раздел: Безопасность ─────────────────────────────────────────────
        row = self._section(scroll, row, "🔒  Безопасность")

        self._var_confirm = ctk.BooleanVar(
            value=self._s.get("confirm_before_delete", True))
        row = self._toggle(scroll, row,
                           "Подтверждение перед удалением",
                           "Показывать диалог «Вы уверены?» перед очисткой",
                           self._var_confirm,
                           lambda: self._save("confirm_before_delete",
                                              self._var_confirm.get()))

        # ── Раздел: Уведомления ──────────────────────────────────────────────
        row = self._section(scroll, row, "🔔  Уведомления")

        self._var_notif = ctk.BooleanVar(
            value=self._s.get("show_notifications", True))
        row = self._toggle(scroll, row,
                           "Системные уведомления",
                           "Показывать уведомление по завершении очистки",
                           self._var_notif,
                           lambda: self._save("show_notifications",
                                              self._var_notif.get()))

        # ── Раздел: Журнал ───────────────────────────────────────────────────
        row = self._section(scroll, row, "📋  Журнал событий")

        log_f = ctk.CTkFrame(scroll, fg_color="#16213e", corner_radius=12)
        log_f.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        row += 1
        top_l = ctk.CTkFrame(log_f, fg_color="transparent")
        top_l.pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(top_l, text="Уровень логирования",
                     font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                     text_color="#ffffff").pack(side="left")
        self._var_log = ctk.StringVar(
            value=self._s.get("log_level", "INFO"))
        ctk.CTkOptionMenu(top_l,
                          values=["DEBUG", "INFO", "WARNING"],
                          variable=self._var_log,
                          font=ctk.CTkFont("Segoe UI", 12),
                          fg_color="#0f3460", button_color="#0f3460",
                          button_hover_color="#16213e",
                          dropdown_fg_color="#1a1a2e",
                          width=130, height=28,
                          command=lambda v: self._save("log_level", v)
                          ).pack(side="right")
        ctk.CTkLabel(log_f,
                     text="INFO — стандартный. DEBUG — подробный (замедляет). "
                          "WARNING — только ошибки.",
                     font=ctk.CTkFont("Segoe UI", 11), text_color="#718096").pack(
            anchor="w", padx=16)

        # Хранить логи N дней
        days_f = ctk.CTkFrame(log_f, fg_color="transparent")
        days_f.pack(fill="x", padx=16, pady=(10, 14))
        ctk.CTkLabel(days_f, text="Хранить логи (дней):",
                     font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0"
                     ).pack(side="left")
        self._var_logdays = ctk.StringVar(
            value=str(self._s.get("log_keep_days", 14)))
        ctk.CTkEntry(days_f, textvariable=self._var_logdays,
                     width=60, height=28,
                     font=ctk.CTkFont("Segoe UI", 12),
                     fg_color="#0f3460", border_color="#2d3748"
                     ).pack(side="left", padx=8)
        ctk.CTkButton(days_f, text="Открыть папку логов",
                      width=160, height=28, corner_radius=8,
                      fg_color="#2d3748", hover_color="#4a5568",
                      font=ctk.CTkFont("Segoe UI", 11),
                      command=_open_log_folder).pack(side="right")

        # ── Раздел: Резервные копии ──────────────────────────────────────────
        row = self._section(scroll, row, "💾  Резервные копии реестра")

        bk_f = ctk.CTkFrame(scroll, fg_color="#16213e", corner_radius=12)
        bk_f.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        row += 1
        ctk.CTkLabel(bk_f,
                     text="Бэкапы реестра создаются автоматически перед каждым исправлением.\n"
                          "Чтобы восстановить — дважды кликните по .reg файлу.",
                     font=ctk.CTkFont("Segoe UI", 11), text_color="#a0aec0"
                     ).pack(anchor="w", padx=16, pady=(14, 8))
        ctk.CTkButton(bk_f, text="📂  Открыть папку бэкапов",
                      width=200, height=32, corner_radius=8,
                      fg_color="#2d3748", hover_color="#4a5568",
                      font=ctk.CTkFont("Segoe UI", 12),
                      command=_open_backup_folder).pack(
            anchor="w", padx=16, pady=(0, 14))

        # ── Раздел: О программе ──────────────────────────────────────────────
        row = self._section(scroll, row, "ℹ️  О программе")

        about_f = ctk.CTkFrame(scroll, fg_color="#16213e", corner_radius=12)
        about_f.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        row += 1

        about_inner = ctk.CTkFrame(about_f, fg_color="transparent")
        about_inner.pack(fill="x", padx=16, pady=16)
        about_inner.columnconfigure(1, weight=1)

        items = [
            ("Версия",       VERSION),
            ("Автор",        "Andrey Dmitriev"),
            ("Copyright",    "© 2026 Andrey Dmitriev. Все права защищены."),
            ("Лицензия",     "Проприетарная — см. LICENSE.txt"),
            ("Python",       f"{sys.version.split()[0]}"),
            ("Данные",       os.path.join(os.path.expanduser("~"), ".winclare")),
        ]
        for i, (label, value) in enumerate(items):
            ctk.CTkLabel(about_inner, text=label + ":",
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color="#718096", anchor="w", width=100
                         ).grid(row=i, column=0, sticky="w", pady=3)
            ctk.CTkLabel(about_inner, text=value,
                         font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                         text_color="#ffffff", anchor="w"
                         ).grid(row=i, column=1, sticky="w", padx=12, pady=3)

        # Кнопка «Сбросить настройки»
        reset_f = ctk.CTkFrame(scroll, fg_color="transparent")
        reset_f.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        row += 1
        ctk.CTkButton(reset_f, text="↩  Сбросить все настройки",
                      width=200, height=36, corner_radius=10,
                      fg_color="#2d3748", hover_color="#4a5568",
                      font=ctk.CTkFont("Segoe UI", 12),
                      command=self._reset_settings).pack(side="left")

    # ── Вспомогательные виджеты ──────────────────────────────────────────────

    def _section(self, parent, row: int, title: str) -> int:
        """Заголовок раздела."""
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=0, sticky="ew", pady=(16, 4))
        ctk.CTkLabel(f, text=title,
                     font=ctk.CTkFont("Segoe UI", 15, weight="bold"),
                     text_color="#4a9eff").pack(side="left")
        sep = ctk.CTkFrame(f, fg_color="#2d3748", height=2)
        sep.pack(side="left", fill="x", expand=True, padx=(12, 0))
        return row + 1

    def _toggle(self, parent, row: int, title: str, desc: str,
                var: ctk.BooleanVar, command) -> int:
        """Строка с переключателем."""
        f = ctk.CTkFrame(parent, fg_color="#16213e", corner_radius=12)
        f.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        f.columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        inner.columnconfigure(0, weight=1)

        txt = ctk.CTkFrame(inner, fg_color="transparent")
        txt.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(txt, text=title,
                     font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                     text_color="#ffffff", anchor="w").pack(anchor="w")
        ctk.CTkLabel(txt, text=desc,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#718096", anchor="w").pack(anchor="w")

        ctk.CTkSwitch(inner, text="", variable=var,
                      onvalue=True, offvalue=False,
                      progress_color="#4a9eff",
                      button_color="#ffffff",
                      width=46, height=24,
                      command=command).grid(row=0, column=1, padx=(16, 0))
        return row + 1

    # ── Логика ───────────────────────────────────────────────────────────────

    def _save(self, key: str, value):
        self._s[key] = value
        save_settings(self._s)
        self._flash("✅  Настройки сохранены")

    def _flash(self, msg: str):
        self.status_lbl.configure(text=msg, text_color="#48bb78")
        self.after(2500, lambda: self.status_lbl.configure(text=""))

    def _on_startup_toggle(self):
        val = self._var_startup.get()
        _set_startup(val)
        self._save("run_on_startup", val)

    def _on_interval_change(self, label: str):
        mapping = {"Ежедневно": "daily",
                   "Еженедельно": "weekly",
                   "Ежемесячно": "monthly"}
        self._save("auto_clean_interval", mapping.get(label, "weekly"))

    @staticmethod
    def _interval_label(key: str) -> str:
        return {"daily": "Ежедневно",
                "weekly": "Еженедельно",
                "monthly": "Ежемесячно"}.get(key, "Еженедельно")

    def _reset_settings(self):
        from utils.settings import DEFAULTS
        self._s = DEFAULTS.copy()
        save_settings(self._s)
        self._flash("↩  Настройки сброшены до заводских")
        # Перестраиваем страницу
        for w in self.winfo_children():
            w.destroy()
        self._build()
