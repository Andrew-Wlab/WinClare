"""
WinClare — Виджет карточки статистики
"""
import customtkinter as ctk


class StatCard(ctk.CTkFrame):
    """Карточка с иконкой, заголовком и значением — для Dashboard."""

    def __init__(self, master, icon: str, title: str, value: str,
                 value_color: str = "#4a9eff", **kwargs):
        super().__init__(master, corner_radius=14, **kwargs)
        self.configure(fg_color="#16213e")

        ctk.CTkLabel(self, text=icon,
                     font=ctk.CTkFont("Segoe UI", 28),
                     ).grid(row=0, column=0, rowspan=2, padx=(18, 10), pady=14)

        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#a0aec0",
                     ).grid(row=0, column=1, sticky="sw", padx=(0, 16), pady=(14, 0))

        self.value_label = ctk.CTkLabel(self, text=value,
                                        font=ctk.CTkFont("Segoe UI", 20, weight="bold"),
                                        text_color=value_color)
        self.value_label.grid(row=1, column=1, sticky="nw", padx=(0, 16), pady=(0, 14))

    def set_value(self, value: str):
        self.value_label.configure(text=value)
