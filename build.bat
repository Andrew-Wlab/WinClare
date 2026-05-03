@echo off
:: ============================================================
:: WinClare — Сборка .exe через PyInstaller
:: Запускать из корня проекта: F:\Claude\Projects\WinClare\
:: ============================================================

echo.
echo  ===================================
echo   WinClare Build Script v1.0
echo   (c) 2026 Andrey Dmitriev
echo  ===================================
echo.

:: Проверяем PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [!] PyInstaller не найден. Устанавливаем...
    pip install pyinstaller
)

:: Очистка предыдущей сборки
if exist dist\WinClare rmdir /s /q dist\WinClare
if exist build rmdir /s /q build

echo [*] Сборка WinClare.exe...
echo.

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "WinClare" ^
    --icon "assets\icon.ico" ^
    --add-data "src;src" ^
    --paths "src" ^
    --hidden-import customtkinter ^
    --hidden-import psutil ^
    --hidden-import win32api ^
    --hidden-import win32con ^
    --hidden-import wmi ^
    --collect-data customtkinter ^
    --version-file version_info.txt ^
    main.py

echo.
if exist dist\WinClare.exe (
    echo  ===================================
    echo   [OK] Сборка успешна!
    echo   Файл: dist\WinClare.exe
    echo  ===================================
    explorer dist
) else (
    echo  [ОШИБКА] Сборка не удалась. Проверьте лог выше.
)

pause
