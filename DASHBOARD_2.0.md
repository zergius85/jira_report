# 🚀 Jira Report Dashboard 2.0 — Новые возможности

Этот документ описывает новые функции, добавленные в систему отчётности Jira.

---

## 📋 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [История отчётов](#история-отчётов)
3. [Экспорт в PDF](#экспорт-в-pdf)
4. [Расписание отчётов](#расписание-отчётов)
5. [Telegram уведомления](#telegram-уведомления)
6. [Метрики и KPI](#метрики-и-kpi)
7. [API для внешних систем](#api-для-внешних-систем)

---

## 🎯 Быстрый старт

### 1. Установка новых зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и настройте:

```ini
# Telegram (опционально)
TELEGRAM_BOT_TOKEN=your-bot-token

# Email (для отправки отчётов)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password

# База данных (опционально, по умолчанию SQLite)
DATABASE_URL=sqlite:///jira_report.db
```

### 3. Инициализация базы данных

```bash
python scripts/init_db.py
```

### 4. Запуск приложения

```bash
python app.py
```

---

## 📚 История отчётов

### Описание

Все сгенерированные отчёты сохраняются в базу данных. Это позволяет:
- Сравнивать периоды (эта неделя vs прошлая)
- Отслеживать динамику метрик
- Возвращаться к историческим данным

### API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/reports/history` | GET | Список отчётов |
| `/api/reports/<id>` | GET | Отчёт по ID |
| `/api/reports/compare` | GET | Сравнение двух отчётов |
| `/api/reports/<id>/comment` | POST | Добавить комментарий |
| `/api/reports/<id>/download/pdf` | GET | Скачать PDF |
| `/api/reports/<id>/download/excel` | GET | Скачать Excel |

### Пример: получение истории

```bash
curl http://localhost:5001/api/reports/history?limit=10
```

### Пример: сравнение отчётов

```bash
curl "http://localhost:5001/api/reports/compare?report1=5&report2=3"
```

---

## 📄 Экспорт в PDF

### Описание

Генерация красивых PDF отчётов для презентаций руководству или отправки клиентам.

### Режимы экспорта

1. **Полный отчёт** — все блоки, включая проблемные задачи и Risk Zone
2. **Клиентский режим** — только сводка и детали по задачам (без внутренней кухни)

### API Endpoint

```bash
# Скачать PDF для отчёта из истории
curl -O http://localhost:5001/api/reports/<id>/download/pdf

# Сгенерировать PDF для клиента по конкретной задаче
curl -X POST -H "Content-Type: application/json" \
  -d '{"task_key": "WEB-123"}' \
  http://localhost:5001/api/client-pdf
```

### Использование в веб-интерфейсе

1. Сгенерируйте отчёт
2. Нажмите кнопку **"💾 Экспорт"**
3. Выберите **"PDF (для клиента)"** или **"PDF (полный)"**

---

## ⏰ Расписание отчётов

### Описание

Автоматическая генерация и отправка отчётов по расписанию.

### Типы расписаний

| Тип | Описание | Пример |
|-----|----------|--------|
| `daily` | Ежедневно | В 9:00 каждый день |
| `weekly` | Еженедельно | В понедельник в 9:00 |
| `monthly` | Ежемесячно | 1-го числа в 9:00 |

### Создание расписания через API

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{
    "name": "Еженедельный отчёт",
    "schedule_type": "weekly",
    "schedule_day": 0,
    "schedule_hour": 9,
    "projects": ["WEB", "MOBILE"],
    "days": 7,
    "email_recipients": ["boss@company.com"],
    "telegram_chats": ["@manager"],
    "send_excel": true,
    "send_pdf": false
  }' \
  http://localhost:5001/api/scheduled-reports
```

### Управление расписанием

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/scheduled-reports` | GET | Список расписаний |
| `/api/scheduled-reports` | POST | Создать расписание |
| `/api/scheduled-reports/<id>/toggle` | POST | Включить/выключить |
| `/api/scheduled-reports/<id>` | DELETE | Удалить расписание |

---

## 📢 Telegram уведомления

### Описание

Мгновенные уведомления о рисковых задачах и готовых отчётах.

### Настройка бота

1. Создайте бота в [@BotFather](https://t.me/BotFather)
2. Получите токен
3. Добавьте в `.env`:

```ini
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

4. Перезапустите приложение

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Подписаться на уведомления |
| `/stop` | Отписаться от уведомлений |
| `/help` | Справка |
| `/status` | Проверить статус подписки |

### Настройка уведомлений

| Тип | Описание | Порог |
|-----|----------|-------|
| Risk Zone Alert | Алёрты о зависших задачах | > 7 дней без движения |
| Scheduled Report | Уведомления о готовых отчётах | По расписанию |

### API для подписки

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{
    "chat_id": "123456789",
    "username": "manager",
    "notify_risk_zone": true,
    "notify_scheduled": true,
    "threshold_days": 7
  }' \
  http://localhost:5001/api/telegram/subscribe
```

---

## 📊 Метрики и KPI

### Sprint Velocity

Показывает среднее количество задач, закрываемых за неделю.

**API:**
```bash
curl http://localhost:5001/api/metrics/velocity
```

**Ответ:**
```json
{
  "success": true,
  "velocity": [
    {"week": "2024-01-01", "tasks": 12},
    {"week": "2024-01-08", "tasks": 15}
  ],
  "avg_velocity": 13.5
}
```

### Burndown Chart

График сгорания задач: оставшиеся дни vs оставшиеся задачи.

**API:**
```bash
curl "http://localhost:5001/api/metrics/burndown?start_date=2024-01-01&end_date=2024-01-31"
```

### Workload (Перегруженность)

Анализ загрузки исполнителей.

**API:**
```bash
curl http://localhost:5001/api/metrics/workload
```

**Ответ:**
```json
{
  "success": true,
  "workload": [
    {"Исполнитель": "Ivan", "Задач": 10, "is_overloaded": true, "workload_ratio": 1.5},
    {"Исполнитель": "Maria", "Задач": 5, "is_overloaded": false, "workload_ratio": 0.75}
  ],
  "avg_tasks": 7.5
}
```

### KPI метрики

| Метрика | Описание |
|---------|----------|
| `avg_cycle_time` | Среднее время выполнения задачи (дни) |
| `median_cycle_time` | Медианное время выполнения |
| `avg_lead_time` | Среднее время от создания до завершения |
| `on_time_delivery` | Процент задач, выполненных в срок |

**API:**
```bash
curl http://localhost:5001/api/metrics/kpi
```

---

## 🔌 API для внешних систем

### Получение информации о задаче

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"task_key": "WEB-123"}' \
  http://localhost:5001/api/task-info
```

### Batch-запрос по нескольким задачам

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"task_keys": ["WEB-123", "WEB-124", "WEB-125"]}' \
  http://localhost:5001/api/task-info-batch
```

### Статус планировщика

```bash
curl http://localhost:5001/api/scheduler/status
```

### Health check

```bash
curl http://localhost:5001/health
```

---

## 📁 Структура новых файлов

```
jira_report/
├── core/
│   ├── models.py           # SQLAlchemy модели
│   ├── report_service.py   # Сервис истории отчётов
│   ├── pdf_export.py       # Экспорт в PDF
│   ├── telegram_bot.py     # Telegram бот
│   └── scheduler.py        # Планировщик APScheduler
├── web/
│   └── telegram_routes.py  # Telegram webhook endpoints
├── scripts/
│   └── init_db.py          # Скрипт инициализации БД
└── reports/                # Папка для сохранённых отчётов
    ├── *.xlsx
    └── *.pdf
```

---

## 🔧 Конфигурация

### Переменные окружения

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | ❌ | Токен Telegram бота |
| `SMTP_SERVER` | ❌ | SMTP сервер для email |
| `SMTP_PORT` | ❌ | SMTP порт (587) |
| `SMTP_USER` | ❌ | SMTP пользователь |
| `SMTP_PASS` | ❌ | SMTP пароль |
| `DATABASE_URL` | ❌ | URL базы данных (SQLite по умолчанию) |

---

## 🚨 Troubleshooting

### Ошибка: WeasyPrint не установлен

```bash
pip install weasyprint
```

### Ошибка: python-telegram-bot не установлен

```bash
pip install python-telegram-bot
```

### Ошибка: База данных не инициализирована

```bash
python scripts/init_db.py
```

### Планировщик не запускается

Проверьте логи приложения:
```
⚠️  Планировщик задач не инициализирован: ...
```

Убедитесь, что APScheduler установлен:
```bash
pip install APScheduler
```

---

## 📈 Roadmap

### P0 (Реализовано ✅)

- [x] История отчётов
- [x] Экспорт в PDF
- [x] Расписание отчётов
- [x] Telegram уведомления
- [x] Сравнение периодов
- [x] KPI метрики

### P1 (В работе 🚧)

- [ ] Мульти-проект дашборд
- [ ] Мобильная адаптация
- [ ] Кастомные фильтры для дашборда

### P2 (Планы 🔮)

- [ ] Интеграция с Confluence
- [ ] Экспорт в PowerPoint
- [ ] Machine Learning для предсказания рисков

---

## 📞 Поддержка

По вопросам и предложениям обращайтесь к разработчику.
