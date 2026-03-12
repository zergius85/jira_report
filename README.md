# 📊 Jira Report System

Система автоматизированной отчётности для Jira Server / Data Center.

## 📋 Описание

Автоматизация сбора, обработки и выгрузки данных из Jira для формирования отчётов по закрытым задачам с валидацией корректности заполнения.

### Возможности

- ✅ **Ежемесячная отчётность** по проектам
- ✅ **Контроль качества** заполнения задач
- ✅ **Анализ загрузки** исполнителей
- ✅ **Выявление проблемных** задач
- ✅ **Web-интерфейс** с удобным UI
- ✅ **Выгрузка в Excel** (5 листов: Сводка, Исполнители, Детали, Проблемы, Непонятное, Risk Zone)

### 🆕 Dashboard 2.0 — Новые возможности

- 📈 **История отчётов** — хранение в БД, сравнение периодов
- 📄 **Экспорт в PDF** — для презентаций и клиентов
- ⏰ **Расписание отчётов** — автоматическая генерация по cron
- 📢 **Telegram уведомления** — алёрты о рисковых задачах
- 📊 **Метрики и KPI** — Velocity, Burndown, Cycle Time, Workload
- 🔌 **REST API** — интеграция с внешними системами

📖 **Подробная документация:** [DASHBOARD_2.0.md](DASHBOARD_2.0.md)

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка конфигурации

```bash
cp configs/.env.example .env
```

Отредактируйте `.env` и укажите:

```ini
JIRA_SERVER=https://your-jira-server.com
JIRA_USER=your.email@company.com
JIRA_PASS=your_password_or_token
```

### 3. Инициализация базы данных (для Dashboard 2.0)

```bash
python scripts/init_db.py
```

### 4. Запуск веб-приложения

**Dev-режим (порт 5001, debug):**
```bash
python app.py
```
Откройте в браузере: http://localhost:5001

**Prod-режим (порт 5000):**

Добавьте в `.env`:
```ini
FLASK_ENV=production
```

Запустите:
```bash
python app.py
```
Откройте в браузере: http://localhost:5000

---

## 📦 Блоки отчёта

| Блок | Описание |
|------|----------|
| `summary` | Сводка по проектам |
| `assignees` | Нагрузка по исполнителям |
| `detail` | Детализация по задачам |
| `issues` | Проблемные задачи |
| `internal` | Непонятное (NEW, local) |
| `risk_zone` | Risk Zone — зависшие задачи |

### 🔴 Risk Zone — описание

Блок **Risk Zone** показывает задачи с факторами риска:

| Фактор | Описание | Критерий |
|--------|----------|----------|
| **Без исполнителя** | Задача не назначена на конкретного человека | `assignee = null` |
| **Просрочена** | Дата исполнения (Due Date) истекла, но задача не закрыта | `duedate < today AND status NOT IN (Closed, Done)` |
| **Не двигается** | Задача не обновлялась более 5 дней и не закрыта | `updated < today - 5 days AND status NOT IN (Closed, Done)` |

Задачи сортируются по приоритету (от высокого к низкому).

---

## ⚙️ Конфигурация

### Файл `.env` (секреты, не хранить в git)

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `JIRA_SERVER` | ✅ | URL сервера Jira |
| `JIRA_USER` | ✅ | Логин для подключения |
| `JIRA_PASS` | ✅ | Пароль или токен |
| `EXCLUDED_PROJECTS` | ❌ | Проекты для исключения |
| `CLOSED_STATUS_IDS` | ❌ | ID статуса "Закрыт" (авто) |
| `EXCLUDED_ASSIGNEE_CLOSE` | ❌ | Пользователи-исключения |
| `SSL_VERIFY` | ❌ | Проверка SSL (false для внутренних серверов) |

### Файл `core/config.py` (общие настройки, хранить в git)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `FLASK_ENV` | `development` | Режим работы (`production` / `development`) |
| `DEV_PORT` | `5001` | Порт для dev-режима |
| `PROD_PORT` | `5000` | Порт для prod-режима |
| `FLASK_HOST` | `0.0.0.0` | Хост для веб-сервера |
| `LOG_LEVEL` | `DEBUG`/`INFO` | Уровень логирования (зависит от режима) |

**Примечание:** `core/config.py` содержит общие настройки и хранится в git. Секреты хранятся в `.env` (не tracked в git).

### Переключение режимов

Для **продакшена** добавьте в `.env`:
```ini
FLASK_ENV=production
```

После этого приложение запустится на порту **5000** с отключённым debug-режимом.

---

## 🏗️ Архитектура

### Компоненты системы

```
┌─────────────────┐
│   Web-интерфейс │
│   (Flask + UI)  │
└────────┬────────┘
         │
┌────────▼────────┐
│   app.py        │
│   (Web entry)   │
└────────┬────────┘
         │
┌────────▼────────┐
│  web/app.py     │
│   (Flask API)   │
└────────┬────────┘
         │
┌────────▼────────┐
│ core/services/  │
│ - IssueFetcher  │
│ - IssueValidator│
│ - ReportAggr.   │
│ - Orchestrator  │
└────────┬────────┘
         │
┌────────▼────────┐
│   Jira Server   │
│   (REST API)    │
└─────────────────┘
```

### Сервисы (core/services/)

| Сервис | Описание |
|--------|----------|
| `ClosedStatusService` | Проверка закрытых статусов |
| `IssueFetcher` | Получение задач из Jira |
| `IssueValidator` | Валидация задач на проблемы |
| `ReportAggregator` | Агрегация статистики |
| `ReportOrchestrator` | Координация сервисов |

### DTO и форматтеры

| Модуль | Описание |
|--------|----------|
| `core/dtos/issue_dto.py` | Модели данных задач |
| `core/formatters/verbose_formatter.py` | Форматирование extra_verbose |

---

## ✅ Валидация задач

Задача считается **проблемной**, если:

| Критерий | Поле Jira | Условие ошибки |
|----------|-----------|----------------|
| Нет даты решения | `resolutiondate` | Пустое значение |
| Нет фактического времени | `timespent` | `null` или `0` |
| Некорректный статус | `status.id` | ID в списке `CLOSED_STATUS_IDS` |

**Исключения:** 
- Пользователи из `EXCLUDED_ASSIGNEE_CLOSE` — для них статус "Закрыт" не считается ошибкой
- Если задача закрыта пользователем демона (JIRA_USER) — это корректно

---

## 📁 Структура проекта

```
jira_report/
├── app.py                  # Точка входа Web-приложения
├── requirements.txt        # Зависимости Python
├── pytest.ini             # Настройки тестов
├── .gitignore             # Игнорируемые файлы
├── README.md              # Этот файл
│
├── .github/                # GitHub Actions
│   └── workflows/
│       └── ci.yml         # CI/CD pipeline
│
├── core/                   # Ядро системы
│   ├── __init__.py
│   ├── config.py          # Конфигурация (настройки)
│   ├── jira_report.py     # Основная логика отчётов
│   ├── jql_builder.py     # Конструктор JQL-запросов
│   ├── problems_dict.py   # Справочник проблем
│   ├── utils.py           # Утилиты (санитизация, логирование)
│   │
│   ├── services/          # Сервисы
│   │   ├── __init__.py
│   │   ├── closed_status_service.py
│   │   ├── issue_fetcher.py
│   │   ├── issue_validator.py
│   │   ├── report_aggregator.py
│   │   └── report_orchestrator.py
│   │
│   ├── dtos/              # Модели данных
│   │   ├── __init__.py
│   │   └── issue_dto.py
│   │
│   ├── formatters/        # Форматтеры
│   │   ├── __init__.py
│   │   └── verbose_formatter.py
│   │
│   └── report_generator.py # Генератор отчётов (ООП)
│
├── web/                    # Веб-интерфейс
│   ├── __init__.py
│   ├── app.py             # Flask API и endpoints
│   ├── middleware.py      # Middleware
│   ├── validators.py      # Валидаторы API
│   └── telegram_routes.py # Telegram маршруты
│
├── services/               # Служебные файлы
│   ├── __init__.py
│   ├── install-service.sh # Скрипт установки службы
│   └── jira-report.service
│
├── configs/                # Конфигурационные шаблоны
│   ├── __init__.py
│   ├── .env.example
│   └── .env.local.example
│
├── templates/              # HTML шаблоны
│   └── index.html
│
├── scripts/                # Скрипты
│   └── init_db.py         # Инициализация БД
│
└── tests/                  # Тесты
    └── test_report.py
```

---

## 🔒 Безопасность

- ✅ Пароли хранятся в `.env` (не в коде)
- ✅ `.env` исключён из Git
- ✅ Поддержка Personal Access Token
- ✅ Локальное выполнение (без отправки данных вовне)
- ⚠️ SSL verification отключается только для внутренних серверов

**Рекомендации:**
1. Используйте отдельного сервисного пользователя Jira
2. Ограничьте права пользователя только на чтение
3. Регулярно обновляйте зависимости

---

## 🧪 Тестирование

```bash
# Запуск тестов
pytest tests/

# Проверка синтаксиса
python -m py_compile app.py core/jira_report.py core/config.py web/app.py
```

---

## 🛠️ Требования

| Компонент | Версия | Примечание |
|-----------|--------|------------|
| **Python** | **3.7.3+** | **Debian 10 buster (по умолчанию)** |
| ОС | Debian 10+ | Или совместимая (Ubuntu 18.04+, CentOS 8+) |
| Flask | 2.0.3 | Последняя версия с поддержкой 3.7 |
| pandas | 1.3.5 | Обработка данных |
| jira | 3.4.1 | API клиент |
| openpyxl | 3.1.2 | Excel экспорт |
| **SQLAlchemy** | 2.0.23 | База данных (история отчётов) |
| **weasyprint** | 52.5 | Экспорт в PDF (последняя для 3.7) |
| **APScheduler** | 3.9.1.post1 | Планировщик задач (3.10+ требует 3.8+) |
| **python-telegram-bot** | 13.15 | Telegram уведомления (20+ требует 3.8+) |

📖 **Полная документация по требованиям:** [PYTHON_3.7_REQUIREMENTS.md](PYTHON_3.7_REQUIREMENTS.md)

---

## 🔄 Запуск как служба (Linux/Debian)

Служба запускает **web-приложение** и обеспечивает его автоматическую перезагрузку.

### Установка

1. **Скопируйте и настройте .env:**
   ```bash
   cp configs/.env.example .env
   # Отредактируйте .env (укажите JIRA_SERVER, JIRA_USER, JIRA_PASS)
   # Для продакшена добавьте: FLASK_ENV=production
   ```

2. **Установите службу:**
   ```bash
   sudo ./services/install-service.sh --prod
   ```

3. **Проверка статуса:**
   ```bash
   systemctl status jira-report.service
   ```

4. **Просмотр логов:**
   ```bash
   journalctl -u jira-report.service -f
   ```

5. **Управление:**
   ```bash
   sudo systemctl start jira-report.service     # Запустить
   sudo systemctl stop jira-report.service      # Остановить
   sudo systemctl restart jira-report.service   # Перезапустить
   sudo systemctl disable jira-report.service   # Отключить
   ```

### Доступ к web-интерфейсу

После запуска службы откройте в браузере:
```
http://<server-ip>:5000
```

**Примечание:** Служба запускается в режиме `production` (порт 5000).

---

### Cron (альтернатива для разовых отчётов)

Для автоматизации используйте API веб-приложения:

```bash
# Пример вызова API через curl
curl -X POST http://localhost:5000/api/report \
  -H "Content-Type: application/json" \
  -d '{"projects": ["WEB"], "days": 30, "blocks": ["summary", "detail"]}'
```

---

## 🚀 GitHub Actions (CI/CD)

Проект использует GitHub Actions для автоматического тестирования и развёртывания.

### Настройка GitHub Actions

#### 1. Создайте секреты (Secrets)

Перейдите в **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Описание | Пример |
|-------------|----------|--------|
| `SERVER_HOST` | IP или домен сервера | `192.168.1.100` |
| `SERVER_USER` | Пользователь SSH | `deploy` |
| `SSH_PRIVATE_KEY` | Приватный SSH-ключ | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

#### 2. Настройте защиту ветки main

**Settings → Branches → Add branch protection rule**

- **Branch name:** `main`
- **Включите:**
  - ☑ Require a pull request before merging
  - ☑ Require status checks to pass before merging
  - ☑ Выберите: `test`, `lint`, `security`
  - ☑ Require branches to be up to date before merging

#### 3. Запуск тестов вручную (для ветки dev)

1. Перейдите в **Actions → Jira Report CI**
2. Нажмите **Run workflow**
3. Выберите ветку (например, `dev`)
4. Нажмите **Run workflow**

#### 4. Проверка результатов

| Результат | Значение |
|-----------|----------|
| ✅ Зелёная галочка | Все тесты прошли |
| ❌ Красный крест | Есть ошибки (смотрите логи) |
| 📊 Coverage | Отчёт по покрытию кодом на Codecov |

#### 5. Лимиты бесплатного тарифа

| Тариф | Минут/месяц | Хранение |
|-------|-------------|----------|
| Free | 2,000 | 500 MB |
| Pro | 3,000 | 2 GB |

**Наши тесты:** ~3-5 минут на запуск

**Рекомендация:** Запускайте для `dev` только вручную перед мержем

### Workflow процессы

| Событие | Действия |
|---------|----------|
| Push в `main` | Lint → Test → Security → Deploy |
| PR в `main` | Lint → Test → Security |
| Ручной запуск | Lint → Test → Security |

---

## 📄 Лицензия

Внутренний инструмент компании.

---

## 📞 Поддержка

По вопросам обращайтесь к разработчику.
