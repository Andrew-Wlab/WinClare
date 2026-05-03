# WinClare — Память проекта

> Последнее обновление: 2 мая 2026

---

## О проекте

**WinClare** — бесплатный оптимизатор и очиститель Windows.
Аналог CCleaner Pro / IObit Advanced SystemCare — без рекламы, без ограничений, open-source.
Позиционирование: _"Бесплатный CCleaner Pro — без рекламы, с открытым кодом"_

---

## Рабочий путь

```
F:\Claude\Projects\WinClare\     ← ВСЕ файлы здесь
```

Папка C:\Users\Andrey\Documents\Claude\Projects\WinClare — старая, не используется (мало места на C:).

---

## Запуск программы

```bat
cd F:\Claude\Projects\WinClare
python main.py
```

Зависимости (установлены один раз через install.bat):
- customtkinter >= 5.2.0
- psutil >= 5.9.0
- pywin32 >= 306
- send2trash >= 1.8.0

Python версия: **3.14.4**

---

## Стек технологий

| Компонент | Выбор |
|---|---|
| Язык | Python 3.14.4 |
| GUI | CustomTkinter (тёмная тема) |
| Системные API | psutil, winreg, ctypes, sqlite3 |
| Windows API | pywin32, shell32 |
| Сборка .exe | PyInstaller (планируется) |
| Логи | logging → `C:\Users\Andrey\.winclare\logs\YYYY-MM-DD.log` |
| Настройки | JSON → `C:\Users\Andrey\.winclare\settings.json` |

---

## Статус разработки — ВСЕ МОДУЛИ ГОТОВЫ ✅

| # | Модуль | Файлы | Статус |
|---|---|---|---|
| 1 | 🧹 Очистка мусора | `modules/cleaner/junk_cleaner.py` + `ui/pages/cleaner_page.py` | ✅ Готово |
| 2 | 🌐 Очистка браузеров | `modules/cleaner/browser_cleaner.py` + `ui/pages/browser_page.py` | ✅ Готово |
| 3 | 🗂️ Очистка реестра | `modules/registry/registry_cleaner.py` + `ui/pages/registry_page.py` | ✅ Готово |
| 4 | 📋 Поиск дубликатов | `modules/duplicates/duplicate_finder.py` + `ui/pages/duplicates_page.py` | ✅ Готово |
| 5 | 🚀 Менеджер автозагрузки | `modules/startup/startup_manager.py` + `ui/pages/startup_page.py` | ✅ Готово |
| 6 | 🗑️ Деинсталлятор | `modules/uninstaller/uninstaller.py` + `ui/pages/uninstaller_page.py` | ✅ Готово |
| 7 | 📊 Монитор системы | `modules/system/system_monitor.py` + `ui/pages/monitor_page.py` | ✅ Готово |
| 8 | 💾 Анализ диска | `modules/disk/disk_analyzer.py` + `ui/pages/disk_page.py` | ✅ Готово |

---

## Полная структура файлов

```
F:\Claude\Projects\WinClare\
│
├── main.py
├── requirements.txt
├── install.bat
├── CLAUDE.md
│
└── src/
    ├── ui/
    │   ├── main_window.py          ← роутер: все 8 модулей подключены
    │   ├── sidebar.py              ← навигация (10 пунктов)
    │   │
    │   └── pages/
    │       ├── dashboard.py        ← главная (CPU/RAM/диск/мусор)
    │       ├── cleaner_page.py     ← очистка мусора
    │       ├── browser_page.py     ← очистка браузеров
    │       ├── registry_page.py    ← очистка реестра
    │       ├── duplicates_page.py  ← поиск дубликатов
    │       ├── startup_page.py     ← автозагрузка
    │       ├── uninstaller_page.py ← деинсталлятор
    │       ├── monitor_page.py     ← монитор системы (live, каждые 1с)
    │       ├── disk_page.py        ← анализатор диска
    │       └── placeholder.py      ← заглушка для настроек
    │
    ├── modules/
    │   ├── cleaner/
    │   │   ├── junk_cleaner.py
    │   │   └── browser_cleaner.py
    │   ├── registry/
    │   │   └── registry_cleaner.py
    │   ├── duplicates/
    │   │   └── duplicate_finder.py
    │   ├── startup/
    │   │   └── startup_manager.py
    │   ├── uninstaller/
    │   │   └── uninstaller.py
    │   ├── system/
    │   │   └── system_monitor.py
    │   └── disk/
    │       └── disk_analyzer.py
    │
    └── utils/
        ├── logger.py
        └── settings.py
```

---

## Архитектурные решения

- **Lazy loading страниц** — страница создаётся в `main_window.py` только при первом переходе и кэшируется
- **Фоновые потоки** — все тяжёлые операции в `threading.Thread(daemon=True)`, UI обновляется через `self.after(0, lambda: ...)`
- **threading.Lock() + _is_running** — защита от двойного запуска на каждой странице
- **Монитор системы** обновляется через `self.after(1000, ...)` — не блокирует UI
- **Реестр** — бэкап через `reg export` перед любыми исправлениями
- **Дубликаты** — алгоритм: группировка по размеру → MD5-хэш кандидатов → группы
- **Браузеры** — история очищается через SQLite `DELETE + VACUUM`, файл не удаляется
- **Автозагрузка** — enable/disable через `StartupApproved` ключ (byte[0]: 0x02=вкл, 0x03=выкл)

---

## Известные исправленные баги

| Баг | Файл | Решение |
|---|---|---|
| 10× повторных сканирований | `cleaner_page.py` | `threading.Lock()` + флаг `_is_running` |
| Нет инфо о заблокированных файлах | `junk_cleaner.py` | Поле `skipped_count` в `CleanTarget` |
| UI не показывал пропущенные | `cleaner_page.py` | Надпись `⚠ N забл.` в результате |

---

## Дорожная карта

### Фаза 1 — MVP ✅
- [x] Главное окно + навигация + Dashboard
- [x] Очистка мусора (10 категорий)
- [x] Очистка браузеров (8 браузеров)

### Фаза 2 — Core Features ✅
- [x] Очистка реестра + резервная копия
- [x] Поиск дубликатов (MD5, выбор диска, авто-выбор)
- [x] Менеджер автозагрузки (реестр + папки + Task Scheduler)
- [x] Деинсталлятор программ (HKLM 64/32 + HKCU, поиск, сортировка)
- [x] Монитор системы (CPU/RAM/диск/сеть/процессы, live 1с)
- [x] Анализатор диска (топ папки + файлы, карточки дисков)

### Фаза 3 — Advanced (следующий этап)
- [ ] Страница «Настройки» (тема, язык, расписание очистки)
- [ ] Планировщик автоматической очистки
- [ ] Экспорт отчётов (PDF / TXT)
- [ ] Тихий режим удаления в деинсталляторе

### Фаза 4 — Release
- [ ] Тестирование на Windows 10 / 11
- [ ] PyInstaller → .exe (portable + installer)
- [ ] GitHub репозиторий + README
