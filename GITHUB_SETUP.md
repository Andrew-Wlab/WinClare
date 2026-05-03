# 📋 Инструкция по публикации WinClare на GitHub

## Шаг 1 — Создать аккаунт GitHub

Если ещё нет — зайди на https://github.com и зарегистрируйся.

---

## Шаг 2 — Создать репозиторий

1. Нажми кнопку **«New»** (зелёная, вверху слева)
2. Заполни:
   - **Repository name:** `WinClare`
   - **Description:** `Free Windows Optimizer — аналог CCleaner Pro`
   - **Visibility:** `Public` ✅ (чтобы все могли скачать)
   - **НЕ ставь** галочки на README/gitignore — они уже готовы
3. Нажми **«Create repository»**

---

## Шаг 3 — Загрузить файлы

Открой командную строку в папке `F:\Claude\Projects\WinClare\` и выполни:

```bash
git init
git add .
git commit -m "🎉 Initial release — WinClare v1.0.0"
git branch -M main
git remote add origin https://github.com/ТВО_ИМЯ/WinClare.git
git push -u origin main
```

---

## Шаг 4 — Собрать .exe

Запусти `build.bat` из папки проекта.
Готовый файл появится в `dist\WinClare.exe`.

> Сначала установи PyInstaller: `pip install pyinstaller`

---

## Шаг 5 — Создать релиз (страница скачивания)

1. В GitHub открой свой репозиторий
2. Справа найди **«Releases»** → **«Create a new release»**
3. Заполни:
   - **Tag:** `v1.0.0`
   - **Title:** `WinClare v1.0.0 — Первый релиз 🎉`
   - **Description:** скопируй из CHANGELOG.md раздел v1.0.0
4. В раздел **«Attach binaries»** перетащи файл `dist\WinClare.exe`
5. Нажми **«Publish release»**

Готово! Пользователи увидят кнопку «Download» с твоим `.exe`.

---

## 💰 Платная Pro версия (v2.0)

**Вариант 1 — Gumroad (проще всего):**
1. Зарегистрируйся на https://gumroad.com
2. Создай продукт, установи цену (например, $9.99)
3. Загрузи `WinClare_Pro.exe`
4. Покупатель платит → получает ссылку на скачивание автоматически

**Вариант 2 — GitHub Sponsors:**
- Пользователи платят ежемесячно за поддержку
- Спонсоры получают доступ к приватному репозиторию с Pro версией

**Вариант 3 — Лицензионные ключи:**
- Добавляем в программу проверку ключа при первом запуске
- Платный пользователь вводит ключ → открывается полный функционал

---

## 🔒 Защита кода

Чтобы исходники не были видны — **НЕ загружай** папку `src/` в публичный репозиторий.
Публично выкладывай только:
- `README.md`
- `LICENSE.txt`
- `CHANGELOG.md`
- `dist/WinClare.exe` (через Releases)

Исходный код храни в **приватном** репозитории отдельно.
