"""
WinClare — Free Windows Optimizer
Точка входа в приложение

Запуск:
    python main.py

Требования:
    pip install customtkinter psutil
"""
import sys
import os

# Добавляем src в путь поиска модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import customtkinter as ctk
from ui.main_window import MainWindow
from utils.logger import logger


def main():
    logger.info("WinClare запускается...")

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = MainWindow()
    app.mainloop()

    logger.info("WinClare завершил работу.")


if __name__ == "__main__":
    main()
