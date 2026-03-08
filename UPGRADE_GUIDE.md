# 🚀 Инструкция по обновлению до Dashboard 2.0

## Требования к среде

- **Python:** 3.7.3+ (Debian 10 buster)
- **ОС:** Debian 10 или совместимая
- **Системные библиотеки:** см. PYTHON_3.7_REQUIREMENTS.md

---

## Шаг 1: Установка системных зависимостей (Debian 10)

```bash
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev
```

---

## Шаг 2: Установка новых зависимостей

### Вариант A: Виртуальное окружение (рекомендуется)

```bash
cd d:\Users\zergius\Yandex.Disk\zergius85\jira_report

# Создание виртуального окружения
python3 -m venv venv

# Активация
source venv/bin/activate  # Linux
# или
venv\Scripts\activate     # Windows

# Обновление pip
pip install --upgrade pip==23.3.1

# Установка зависимостей
pip install -r requirements.txt
```

### Вариант B: Глобальная установка (не рекомендуется)

```bash
sudo pip3 install -r requirements.txt
```

### Если возникают ошибки при установке WeasyPrint

WeasyPrint требует дополнительные библиотеки. Для Windows:

**Вариант 1: Через pip (простой)**
```bash
pip install weasyprint
```

**Вариант 2: Если не работает — использовать pre-built wheel**
```bash
pip install https://github.com/Kozea/WeasyPrint/releases/download/v59.0/WeasyPrint-59.0-py3-none-any.whl
```

**Вариант 3: Установить GTK3 (если требуется)**
1. Скачайте GTK3: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-for-Windows/releases
2. Установите GTK3
3. Перезапустите терминал
4. `pip install weasyprint`

---

## Шаг 2: Обновление конфигурации

```bash
# Скопируйте новый .env.example
copy configs\.env.example .env
```

Откройте `.env` и добавьте:

```ini
# =============================================
# TELEGRAM (для уведомлений)
# =============================================
TELEGRAM_BOT_TOKEN=

# =============================================
# EMAIL (SMTP для отправки отчётов)
# =============================================
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
EMAIL_FROM=Jira Report <noreply@jira-report.local>

# =============================================
# БАЗА ДАННЫХ (для истории отчётов)
# =============================================
DATABASE_URL=sqlite:///jira_report.db
```

---

## Шаг 3: Инициализация базы данных

```bash
python scripts\init_db.py
```

Ожидаемый вывод:
```
🔧 Инициализация базы данных Jira Report System...
✅ База данных успешно инициализирована!
📁 Файл базы данных: jira_report.db (в корне проекта)

Созданные таблицы:
  • report_history — История отчётов
  • report_comments — Комментарии к отчётам
  • scheduled_reports — Расписание отчётов
  • telegram_subscriptions — Telegram подписки
```

---

## Шаг 4: Проверка установки

### Проверка зависимостей

```bash
python -c "import sqlalchemy; print(f'SQLAlchemy: {sqlalchemy.__version__}')"
python -c "import apscheduler; print(f'APScheduler: {apscheduler.__version__}')"
python -c "import telegram; print(f'python-telegram-bot: {telegram.__version__}')"
```

### Проверка импортов в коде

```bash
python -c "from core.models import init_db; print('✅ core.models OK')"
python -c "from core.report_service import save_report; print('✅ core.report_service OK')"
python -c "from core.pdf_export import generate_pdf_report; print('✅ core.pdf_export OK')"
python -c "from core.scheduler import init_scheduler; print('✅ core.scheduler OK')"
```

---

## Шаг 5: Запуск приложения

```bash
python app.py
```

Ожидаемый вывод:
```
🚀 Запуск веб-интерфейса...
📍 Откройте в браузере: http://localhost:5001
📦 Доступные блоки: summary, assignees, detail, issues, internal, risk_zone
🔧 Режим: dev, Хост: 0.0.0.0, Порт: 5001
✅ Telegram routes зарегистрированы
✅ Планировщик задач инициализирован
✅ База данных инициализирована
 * Running on http://0.0.0.0:5001
```

---

## Шаг 6: Проверка новых функций

### 1. Проверка API истории отчётов

Откройте в браузере:
```
http://localhost:5001/api/reports/history
```

Ожидаемый ответ:
```json
{
  "success": true,
  "reports": [],
  "count": 0
}
```

### 2. Проверка API метрик

```
http://localhost:5001/api/metrics/velocity
http://localhost:5001/api/metrics/workload
http://localhost:5001/api/metrics/kpi
```

### 3. Проверка статуса планировщика

```
http://localhost:5001/api/scheduler/status
```

---

## Шаг 7: Настройка Telegram (опционально)

### 1. Создание бота

1. Откройте @BotFather в Telegram
2. Отправьте `/newbot`
3. Введите имя бота (например, `Jira Report Bot`)
4. Введите username бота (например, `jira_report_bot`)
5. Скопируйте токен (выглядит как `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Добавление токена

Откройте `.env` и добавьте:
```ini
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 3. Перезапуск приложения

```bash
# Остановите приложение (Ctrl+C)
python app.py
```

### 4. Тестирование бота

1. Найдите бота в Telegram по username
2. Отправьте `/start`
3. Бот должен ответить приветственным сообщением

---

## Шаг 8: Настройка Email (опционально)

### Для Gmail:

1. Включите двухфакторную аутентификацию
2. Создайте App Password: https://myaccount.google.com/apppasswords
3. Добавьте в `.env`:

```ini
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=16-digit-app-password
EMAIL_FROM=Jira Report <your-email@gmail.com>
```

### Для Яндекс.Почты:

```ini
SMTP_SERVER=smtp.yandex.ru
SMTP_PORT=465
SMTP_USER=your-email@yandex.ru
SMTP_PASS=app-password
```

---

## 🔧 Troubleshooting

### Ошибка: ModuleNotFoundError: No module named 'sqlalchemy'

**Решение:**
```bash
pip install sqlalchemy
```

### Ошибка: No module named 'telegram'

**Решение:**
```bash
pip install python-telegram-bot
```

### Ошибка: WeasyPrint не работает

**Решение для Windows:**
```bash
# Попробуйте установить старую версию
pip install weasyprint==52.5

# Или используйте conda
conda install -c conda-forge weasyprint
```

### Ошибка: Database is locked

**Решение:**
SQLite не поддерживает конкурентную запись. Для production используйте PostgreSQL:

```ini
DATABASE_URL=postgresql://user:password@localhost/jira_report
```

### Ошибка: Планировщик не запускается

Проверьте логи приложения. Убедитесь, что APScheduler установлен:
```bash
pip install apscheduler
```

---

## 📊 Проверка работы

### 1. Сгенерируйте отчёт через веб-интерфейс

1. Откройте http://localhost:5001
2. Выберите параметры
3. Нажмите "📋 Сгенерировать"

### 2. Проверьте историю отчётов

```bash
curl http://localhost:5001/api/reports/history
```

### 3. Создайте расписание

```bash
curl -X POST -H "Content-Type: application/json" ^
  -d "{\"name\":\"Тест\",\"schedule_type\":\"weekly\",\"schedule_hour\":9}" ^
  http://localhost:5001/api/scheduled-reports
```

---

## ✅ Чеклист успешного обновления

- [ ] Установлены все зависимости (`pip install -r requirements.txt`)
- [ ] Скопирован и настроен `.env`
- [ ] Инициализирована БД (`python scripts\init_db.py`)
- [ ] Приложение запускается без ошибок
- [ ] API `/api/reports/history` возвращает данные
- [ ] API `/api/metrics/kpi` работает
- [ ] Планировщик инициализирован
- [ ] Telegram бот отвечает на `/start` (если настроен)

---

## 📞 Поддержка

Если возникли проблемы:

1. Проверьте логи приложения
2. Убедитесь, что все зависимости установлены
3. Проверьте `.env` на корректность
4. Убедитесь, что порты 5000/5001 не заняты

---

**🎉 Удачи с Dashboard 2.0!**
