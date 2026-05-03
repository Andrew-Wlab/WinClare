"""
WinClare — Главное окно приложения
"""
import customtkinter as ctk
from ui.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.cleaner_page import CleanerPage
from ui.pages.browser_page import BrowserPage
from ui.pages.startup_page import StartupPage
from ui.pages.registry_page import RegistryPage
from ui.pages.duplicates_page import DuplicatesPage
from ui.pages.uninstaller_page import UninstallerPage
from ui.pages.monitor_page import MonitorPage
from ui.pages.disk_page import DiskPage
from ui.pages.settings_page import SettingsPage
from ui.pages.placeholder import PlaceholderPage


PAGES_CONFIG = {}


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WinClare — Free Windows Optimizer  |  © 2026 Andrey Dmitriev")
        self.geometry("1100x700")
        self.minsize(900, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._build_layout()
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._show_page("dashboard")

    def _build_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar = Sidebar(self, on_navigate=self._show_page)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.content_area = ctk.CTkFrame(self, corner_radius=0, fg_color="#0d1117")
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

    def _get_or_create_page(self, key: str) -> ctk.CTkFrame:
        if key in self._pages:
            return self._pages[key]

        if key == "dashboard":
            page = DashboardPage(self.content_area)
        elif key == "cleaner":
            page = CleanerPage(self.content_area)
        elif key == "browser":
            page = BrowserPage(self.content_area)
        elif key == "startup":
            page = StartupPage(self.content_area)
        elif key == "registry":
            page = RegistryPage(self.content_area)
        elif key == "duplicates":
            page = DuplicatesPage(self.content_area)
        elif key == "uninstaller":
            page = UninstallerPage(self.content_area)
        elif key == "monitor":
            page = MonitorPage(self.content_area)
        elif key == "disk":
            page = DiskPage(self.content_area)
        elif key == "settings":
            page = SettingsPage(self.content_area)
        else:
            cfg = PAGES_CONFIG.get(key)
            if cfg:
                icon, title, desc = cfg
                page = PlaceholderPage(self.content_area, icon, title, desc)
            else:
                page = PlaceholderPage(self.content_area, "❓", key, "Страница не найдена.")

        page.grid(row=0, column=0, sticky="nsew")
        self._pages[key] = page
        return page

    def _show_page(self, key: str):
        for p in self._pages.values():
            p.grid_remove()
        page = self._get_or_create_page(key)
        page.grid(row=0, column=0, sticky="nsew")
        self.sidebar._set_active(key)
