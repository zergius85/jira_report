# 📋 Рекомендации по развитию проекта

Реестр улучшений для Jira Report System

**Статус на:** Март 2026

---

## ✅ Реализованные улучшения

### 1. Структурирование проекта

**Статус:** ✅ Реализовано

**Описание:** Проект разделён на логические модули:
- `core/` — ядро системы (логика отчётов, конфигурация)
- `web/` — веб-интерфейс (Flask API)
- `services/` — служебные файлы (systemd, скрипты установки)
- `configs/` — шаблоны конфигурационных файлов
- `templates/` — HTML шаблоны
- `tests/` — тесты

**Преимущества:**
- Чёткое разделение ответственности
- Упрощённое тестирование
- Легче поддерживать и расширять

---

### 2. Health check endpoint

**Статус:** ✅ Реализовано

**Описание:** Добавлен endpoint `/health` для мониторинга работоспособности.

**Использование:**
```bash
curl http://localhost:5000/health
# {"status": "ok", "timestamp": "2026-03-05T...", "checks": {"jira": "ok"}}
```

**Расположение:** `web/app.py`, функция `health_check()`

---

### 3. Retry-логика для Jira API

**Статус:** ✅ Реализовано (библиотека tenacity)

**Описание:** Подключение к Jira использует автоматические повторные попытки.

**Расположение:** `core/jira_report.py`, функция `_get_jira_connection_impl()`

---

### 4. Кэширование API endpoints

**Статус:** ✅ Реализовано (Flask-Caching)

**Описание:** Списки проектов и исполнителей кэшируются на 5 минут (только production).

**Расположение:** `web/app.py`

---

### 5. Risk Zone — зависшие задачи

**Статус:** ✅ Реализовано

**Описание:** Новый блок отчёта для выявления задач с факторами риска:
- Без исполнителя
- Просроченные (Due Date истёк)
- Не двигались > 5 дней

**Расположение:** `core/jira_report.py`, блок "RISK ZONE"

---

## 🔴 Критично для production

### 6. Gunicorn вместо Flask dev-сервера

**Статус:** ⏳ Требуется внедрение

**Проблема:** `app.run()` — development-сервер, не для production.

**Решение:**

```bash
# Добавить в requirements.txt
gunicorn>=20.0.0
```

Обновить `services/jira-report.service.template`:
```ini
[Service]
ExecStart=/usr/local/bin/gunicorn -w 4 -b 0.0.0.0:5000 web.app:app
Restart=always
```

**Преимущества:**
- Многопоточность (4 worker'а)
- Стабильность при нагрузке
- Правильная обработка сигналов

---

### 7. Валидация входных данных API

**Статус:** ⏳ Требуется внедрение

**Проблема:** Недостаточная проверка параметров от пользователя.

**Решение:** Добавить декоратор в `web/app.py`:

```python
from functools import wraps

def validate_json(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        return f(*args, **kwargs)
    return decorated

@app.route('/api/report', methods=['POST'])
@validate_json
def api_report():
    data = request.get_json()
    # Дальше валидация полей...
```

---

## 🟡 Средний приоритет

### 8. Явная пагинация запросов

**Статус:** ⏳ Требуется внедрение

**Проблема:** При >5000 задач за период данные могут потеряться.

**Решение:** Заменить в `core/jira_report.py`:

```python
def search_all_issues(jira, jql, batch_size=100):
    all_issues = []
    start_at = 0
    while True:
        batch = jira.search_issues(jql, startAt=start_at, maxResults=batch_size)
        if not batch:
            break
        all_issues.extend(batch)
        if len(batch) < batch_size:
            break
        start_at += batch_size
    return all_issues
```

---

### 9. Ротация логов

**Статус:** ⏳ Требуется внедрение

**Проблема:** Логи пишутся только в systemd journal, нет файла.

**Решение:** Добавить в `web/app.py`:

```python
from logging.handlers import RotatingFileHandler
import os

if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler('logs/jira_report.log', 
                                    maxBytes=10*1024*1024, 
                                    backupCount=5)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
```

---

### 10. Бэкап конфигурации

**Статус:** ⏳ Требуется внедрение

**Проблема:** `.env` — единственное место хранения конфига.

**Решение:** Создать `scripts/backup-config.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/jira-report"
mkdir -p "$BACKUP_DIR"
cp .env "$BACKUP_DIR/.env.$(date +%Y%m%d_%H%M%S)"
# Хранить последние 10 бэкапов
ls -t "$BACKUP_DIR" | tail -n +11 | xargs -r rm
```

---

### 11. Версионирование конфигурации

**Статус:** ⏳ Требуется внедрение

**Проблема:** Нет проверки совместимости `.env` при обновлении.

**Решение:** Добавить в `.env`:

```ini
CONFIG_VERSION=1.1
```

Проверка в `core/config.py`:

```python
REQUIRED_VERSION = '1.1'
config_version = os.getenv('CONFIG_VERSION', '1.0')
if config_version != REQUIRED_VERSION:
    logger.warning(f"Версия конфига {config_version} != {REQUIRED_VERSION}")
```

---

## 🟢 Низкий приоритет

### 12. Экспорт в CSV

**Статус:** ⏳ Требуется внедрение

**Проблема:** Только Excel, не все любят xlsx.

**Решение:** Добавить endpoint в `web/app.py`:

```python
@app.route('/api/download/csv', methods=['POST'])
def api_download_csv():
    # Аналогично /api/download, но:
    output = io.StringIO()
    df.to_csv(output, index=False, sep=';')
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='report.csv'
    )
```

---

### 13. Расширенное кэширование

**Статус:** ⏳ Частично реализовано

**Проблема:** Кэш только для `/api/projects` и `/api/assignees`.

**Решение:** Добавить кэш для `/api/issue-types` и результатов отчётов.

---

### 14. Docker-контейнеризация

**Статус:** ⏳ Требуется внедрение

**Решение:** Создать `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

ENV FLASK_ENV=production
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "web.app:app"]
```

---

### 15. CI/CD пайплайн

**Статус:** ⏳ Требуется внедрение

**Решение:** Добавить `.github/workflows/test.yml`:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
```

---

## 📊 План внедрения

| Этап | Задачи | Время |
|------|--------|-------|
| 1 | Gunicorn + Валидация API | 30 мин |
| 2 | Пагинация + Ротация логов | 45 мин |
| 3 | Бэкапы + Версионирование | 30 мин |
| 4 | Docker + CI/CD | 60 мин |

---

## 📝 Changelog

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2026-03-05 | 2.0.0 | Структурирование проекта, Risk Zone, обновлённая документация |
| 2024-01-01 | 1.0.0 | Начальная версия документа |
