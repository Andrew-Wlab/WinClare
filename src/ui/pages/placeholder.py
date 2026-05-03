"""
WinClare — Заглушка для страниц в разработке
"""
import customtkinter as ctk


class PlaceholderPage(ctk.CTkFrame):
    def __init__(self, master, icon: str, title: str, description: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=20,
                               width=480, height=300)
        content.place(relx=0.5, rely=0.5, anchor="center")
        content.pack_propagate(False)

        ctk.CTkLabel(content, text=icon,
                     font=ctk.CTkFont("Segoe UI", 56)).pack(pady=(40, 8))
        ctk.CTkLabel(content, text=title,
                     font=ctk.CTkFont("Segoe UI", 20, weight="bold"),
                     text_color="#ffffff").pack()
        ctk.CTkLabel(content, text=description,
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color="#718096", wraplength=380).pack(pady=(6, 20))
        ctk.CTkLabel(content, text="🔧  Модуль в разработке",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color="#4a9eff").pack()
