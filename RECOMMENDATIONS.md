# 📋 Рекомендации по развитию проекта

## Реестр улучшений для Jira Report System

---

## 🔴 Критично для production

### 1. Gunicorn вместо Flask dev-сервера

**Проблема:** `app.run()` — это development-сервер, не предназначен для production.

**Решение:**

```bash
# Добавить в requirements.txt
gunicorn>=20.0.0
```

```ini
# Обновить /etc/systemd/system/jira-report.service
[Service]
ExecStart=/usr/local/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always
```

**Преимущества:**
- Многопоточность (4 worker'а)
- Стабильность при нагрузке
- Правильная обработка сигналов

---

### 2. Health check endpoint

**Проблема:** Нет способа проверить работоспособность службы для мониторинга.

**Решение:** Добавить в `app.py`:

```python
@app.route('/health')
def health():
    try:
        jira = get_jira_connection()
        jira.myself()
        return jsonify({'status': 'ok', 'jira': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 503
```

**Использование:**
```bash
curl http://localhost:5000/health
# {"status": "ok", "jira": "connected"}
```

---

## 🟡 Средний приоритет

### 3. Retry-логика для Jira API

**Проблема:** При временной недоступности Jira запросы падают сразу.

**Решение:** Добавить в `jira_report.py`:

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_jira_connection():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    jira = JIRA(
        server=JIRA_SERVER,
        basic_auth=(JIRA_USER, JIRA_PASS),
        options={'verify': SSL_VERIFY},
        session=session
    )
    return jira
```

---

### 4. Явная пагинация запросов

**Проблема:** При >5000 задач за период данные могут потеряться.

**Решение:** Заменить в `generate_report()`:

```python
# Было:
issues = jira.search_issues(jql, maxResults=False)

# Стало:
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

issues = search_all_issues(jira, jql)
```

---

### 5. Валидация входных данных API

**Проблема:** Недостаточная проверка параметров от пользователя.

**Решение:** Добавить в `app.py`:

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

## 🟢 Низкий приоритет

### 6. Ротация логов

**Проблема:** Логи пишутся только в systemd journal, нет файла.

**Решение:** Добавить в `app.py`:

```python
from logging.handlers import RotatingFileHandler
import os

if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler('logs/jira_report.log', maxBytes=10*1024*1024, backupCount=5)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
```

---

### 7. Бэкап конфигурации

**Проблема:** `.env` — единственное место хранения конфига.

**Решение:** Создать `backup-config.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/jira-report"
mkdir -p "$BACKUP_DIR"
cp .env "$BACKUP_DIR/.env.$(date +%Y%m%d_%H%M%S)"
# Хранить последние 10 бэкапов
ls -t "$BACKUP_DIR" | tail -n +11 | xargs -r rm
```

---

### 8. Версионирование конфигурации

**Проблема:** Нет проверки совместимости `.env` при обновлении.

**Решение:** Добавить в `.env`:

```ini
CONFIG_VERSION=1.0
```

Проверка в `jira_report.py`:

```python
REQUIRED_VERSION = '1.0'
config_version = os.getenv('CONFIG_VERSION', '1.0')
if config_version != REQUIRED_VERSION:
    logger.warning(f"Версия конфига {config_version} != {REQUIRED_VERSION}")
```

---

### 9. Кэширование списков проектов и исполнителей

**Проблема:** Каждый запрос `/api/projects` и `/api/assignees` ходит в Jira.

**Решение:** Добавить кэш на 5 минут:

```python
from functools import lru_cache
from datetime import datetime, timedelta

projects_cache = {'data': None, 'expires': None}

def get_projects_cached():
    if projects_cache['data'] and projects_cache['expires'] > datetime.now():
        return projects_cache['data']
    
    jira = get_jira_connection()
    projects = jira.projects()
    projects_cache['data'] = projects
    projects_cache['expires'] = datetime.now() + timedelta(minutes=5)
    return projects
```

---

### 10. Экспорт в CSV

**Проблема:** Только Excel, не все любят xlsx.

**Решение:** Добавить endpoint:

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

## 📊 План внедрения

| Этап | Задачи | Время |
|------|--------|-------|
| 1 | Gunicorn + Health check | 30 мин |
| 2 | Retry-логика + Пагинация | 45 мин |
| 3 | Валидация API + Ротация логов | 30 мин |
| 4 | Кэш + Бэкапы + Версионирование | 40 мин |

---

## 📝 Changelog

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2024-01-01 | 1.0.0 | Начальная версия документа |
