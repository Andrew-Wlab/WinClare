"""
WinClare — Боковая навигационная панель
"""
import customtkinter as ctk
from typing import Callable

NAV_ITEMS = [
    ("dashboard",   "🏠", "Главная"),
    ("cleaner",     "🧹", "Очистка"),
    ("browser",     "🌐", "Браузеры"),
    ("registry",    "🗂️", "Реестр"),
    ("duplicates",  "📋", "Дубликаты"),
    ("startup",     "🚀", "Автозагрузка"),
    ("uninstaller", "🗑️", "Программы"),
    ("monitor",     "📊", "Монитор"),
    ("disk",        "💾", "Диск"),
    ("settings",    "⚙️", "Настройки"),
]

COLORS = {
    "sidebar_bg":      "#1a1a2e",
    "btn_hover":       "#16213e",
    "btn_active":      "#0f3460",
    "btn_active_line": "#e94560",
    "text_normal":     "#a0aec0",
    "text_active":     "#ffffff",
    "logo_blue":       "#4a9eff",
    "logo_accent":     "#e94560",
    "version":         "#4a5568",
}


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_navigate: Callable[[str], None], **kwargs):
        super().__init__(master, width=220, corner_radius=0,
                         fg_color=COLORS["sidebar_bg"], **kwargs)
        self.on_navigate = on_navigate
        self.active_key = "dashboard"
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._build()

    def _build(self):
        self.grid_rowconfigure(len(NAV_ITEMS) + 2, weight=1)

        # Логотип
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=(24, 8), sticky="ew")
        ctk.CTkLabel(logo_frame, text="Win",
                     font=ctk.CTkFont("Segoe UI", 26, weight="bold"),
                     text_color=COLORS["logo_blue"]).pack(side="left")
        ctk.CTkLabel(logo_frame, text="Clare",
                     font=ctk.CTkFont("Segoe UI", 26, weight="bold"),
                     text_color=COLORS["logo_accent"]).pack(side="left")

        ctk.CTkLabel(self, text="Free Windows Optimizer",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COLORS["version"],
                     ).grid(row=1, column=0, padx=20, pady=(0, 4), sticky="w")

        sep = ctk.CTkFrame(self, height=1, fg_color="#2d3748")
        sep.grid(row=1, column=0, padx=16, pady=(30, 8), sticky="ew")

        for idx, (key, icon, label) in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                self,
                text=f"  {icon}  {label}",
                anchor="w",
                height=42,
                corner_radius=10,
                border_width=0,
                font=ctk.CTkFont("Segoe UI", 13),
                fg_color="transparent",
                hover_color=COLORS["btn_hover"],
                text_color=COLORS["text_normal"],
                command=lambda k=key: self._on_click(k),
            )
            btn.grid(row=idx + 2, column=0, padx=10, pady=2, sticky="ew")
            self._buttons[key] = btn

        # Копирайт внизу панели
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=len(NAV_ITEMS) + 3, column=0,
                    padx=16, pady=(0, 14), sticky="sew")

        ctk.CTkLabel(footer, text="v0.1.0  •  2026",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=COLORS["version"],
                     anchor="w").pack(anchor="w")

        ctk.CTkLabel(footer, text="© 2026 Andrey Dmitriev",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=COLORS["version"],
                     anchor="w").pack(anchor="w")

        self._set_active("dashboard")

    def _on_click(self, key: str):
        self._set_active(key)
        self.on_navigate(key)

    def _set_active(self, key: str):
        if self.active_key in self._buttons:
            self._buttons[self.active_key].configure(
                fg_color="transparent",
                text_color=COLORS["text_normal"],
                font=ctk.CTkFont("Segoe UI", 13),
            )
        self.active_key = key
        if key in self._buttons:
            self._buttons[key].configure(
                fg_color=COLORS["btn_active"],
                text_color=COLORS["text_active"],
                font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            )
