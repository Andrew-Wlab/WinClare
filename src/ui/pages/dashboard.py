"""
WinClare — Страница Dashboard (главная)
"""
import customtkinter as ctk
from ui.widgets.stat_card import StatCard
import psutil
import shutil
import threading
import os
import tempfile


def _fmt_bytes(n: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ПБ"


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._build()
        self._refresh_stats()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 20))

        ctk.CTkLabel(header, text="Добро пожаловать в WinClare",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")

        self.scan_btn = ctk.CTkButton(
            header, text="  🔍  Быстрое сканирование",
            width=200, height=40, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            fg_color="#e94560", hover_color="#c73652",
            command=self._quick_scan,
        )
        self.scan_btn.pack(side="right")

        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=30, pady=(0, 20))
        cards_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="card")

        self.card_cpu = StatCard(cards_frame, "🖥️", "Загрузка CPU", "—%", value_color="#4a9eff")
        self.card_cpu.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        self.card_ram = StatCard(cards_frame, "🧠", "Использование RAM", "—%", value_color="#48bb78")
        self.card_ram.grid(row=0, column=1, padx=8, sticky="ew")

        self.card_disk = StatCard(cards_frame, "💾", "Занято на диске C:", "— ГБ", value_color="#ed8936")
        self.card_disk.grid(row=0, column=2, padx=8, sticky="ew")

        self.card_junk = StatCard(cards_frame, "🗑️", "Найдено мусора", "0 МБ", value_color="#e94560")
        self.card_junk.grid(row=0, column=3, padx=(8, 0), sticky="ew")

        self.progress_frame = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=14)
        self.progress_frame.pack(fill="x", padx=30, pady=(0, 20))

        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="Нажмите «Быстрое сканирование» для анализа системы",
            font=ctk.CTkFont("Segoe UI", 12), text_color="#a0aec0")
        self.progress_label.pack(padx=20, pady=(16, 6), anchor="w")

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame, height=8, corner_radius=4,
            progress_color="#e94560", fg_color="#2d3748")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkLabel(self, text="Модули очистки",
                     font=ctk.CTkFont("Segoe UI", 15, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", padx=30, pady=(0, 10))

        self.modules_frame = ctk.CTkScrollableFrame(
            self, fg_color="#16213e", corner_radius=14, height=220)
        self.modules_frame.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        self.modules_frame.columnconfigure(0, weight=1)

        modules_data = [
            ("🧹", "Очистка мусора",     "Temp, Prefetch, старые обновления Windows"),
            ("🌐", "Браузеры",           "Chrome, Firefox, Edge, Opera, Brave"),
            ("🗂️", "Реестр",            "Поиск и исправление ошибок реестра"),
            ("📋", "Дубликаты",          "Поиск одинаковых файлов на диске"),
            ("🚀", "Автозагрузка",       "Управление программами при старте Windows"),
            ("🗑️", "Программы",         "Удаление приложений без остатков"),
            ("📊", "Монитор системы",    "CPU, RAM, температура, процессы"),
            ("💾", "Анализ диска",       "Визуализация занятого пространства"),
        ]

        for i, (icon, name, desc) in enumerate(modules_data):
            row_frame = ctk.CTkFrame(self.modules_frame, fg_color="#1a1a2e", corner_radius=10)
            row_frame.grid(row=i, column=0, padx=4, pady=4, sticky="ew")
            row_frame.columnconfigure(1, weight=1)

            ctk.CTkLabel(row_frame, text=icon,
                         font=ctk.CTkFont("Segoe UI", 20)).grid(
                row=0, column=0, rowspan=2, padx=(14, 10), pady=10)
            ctk.CTkLabel(row_frame, text=name,
                         font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                         text_color="#ffffff").grid(row=0, column=1, sticky="sw", pady=(10, 0))
            ctk.CTkLabel(row_frame, text=desc,
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color="#718096").grid(row=1, column=1, sticky="nw", pady=(0, 10))
            ctk.CTkLabel(row_frame, text="● Готов",
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color="#48bb78").grid(row=0, column=2, rowspan=2, padx=16)

    def _refresh_stats(self):
        try:
            cpu = psutil.cpu_percent(interval=0.3)
            ram = psutil.virtual_memory()
            disk = shutil.disk_usage("C:\\")
            self.card_cpu.set_value(f"{cpu:.0f}%")
            self.card_ram.set_value(f"{ram.percent:.0f}%")
            self.card_disk.set_value(
                f"{disk.used / 1024**3:.0f} / {disk.total / 1024**3:.0f} ГБ")
        except Exception:
            pass
        self.after(5000, self._refresh_stats)

    def _quick_scan(self):
        self.scan_btn.configure(state="disabled", text="  ⏳  Сканирование...")
        self.progress_bar.set(0)
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        import time
        total_junk = 0
        steps = [
            ("Временные файлы пользователя...", tempfile.gettempdir()),
            ("Папка Windows Temp...",           r"C:\Windows\Temp"),
            ("Кэш Prefetch...",                 r"C:\Windows\Prefetch"),
        ]
        for i, (msg, path) in enumerate(steps):
            self.after(0, lambda m=msg: self.progress_label.configure(text=m))
            self.after(0, lambda v=(i + 1) / len(steps): self.progress_bar.set(v))
            try:
                for root, dirs, files in os.walk(path):
                    for f in files:
                        try:
                            total_junk += os.path.getsize(os.path.join(root, f))
                        except Exception:
                            pass
            except Exception:
                pass
            time.sleep(0.3)

        result = _fmt_bytes(total_junk)
        self.after(0, lambda: self.card_junk.set_value(result))
        self.after(0, lambda: self.progress_label.configure(
            text=f"✅ Готово! Найдено мусора: {result}"))
        self.after(0, lambda: self.scan_btn.configure(
            state="normal", text="  🔍  Быстрое сканирование"))
