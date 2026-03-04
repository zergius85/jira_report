# рџ“‹ Р РµРєРѕРјРµРЅРґР°С†РёРё РїРѕ СЂР°Р·РІРёС‚РёСЋ РїСЂРѕРµРєС‚Р°

## Р РµРµСЃС‚СЂ СѓР»СѓС‡С€РµРЅРёР№ РґР»СЏ Jira Report System

---

## рџ”ґ РљСЂРёС‚РёС‡РЅРѕ РґР»СЏ production

### 1. Gunicorn РІРјРµСЃС‚Рѕ Flask dev-СЃРµСЂРІРµСЂР°

**РџСЂРѕР±Р»РµРјР°:** `app.run()` вЂ” СЌС‚Рѕ development-СЃРµСЂРІРµСЂ, РЅРµ РїСЂРµРґРЅР°Р·РЅР°С‡РµРЅ РґР»СЏ production.

**Р РµС€РµРЅРёРµ:**

```bash
# Р”РѕР±Р°РІРёС‚СЊ РІ requirements.txt
gunicorn>=20.0.0
```

```ini
# РћР±РЅРѕРІРёС‚СЊ /etc/systemd/system/jira-report.service
[Service]
ExecStart=/usr/local/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always
```

**РџСЂРµРёРјСѓС‰РµСЃС‚РІР°:**
- РњРЅРѕРіРѕРїРѕС‚РѕС‡РЅРѕСЃС‚СЊ (4 worker'Р°)
- РЎС‚Р°Р±РёР»СЊРЅРѕСЃС‚СЊ РїСЂРё РЅР°РіСЂСѓР·РєРµ
- РџСЂР°РІРёР»СЊРЅР°СЏ РѕР±СЂР°Р±РѕС‚РєР° СЃРёРіРЅР°Р»РѕРІ

---

### 2. Health check endpoint

**РџСЂРѕР±Р»РµРјР°:** РќРµС‚ СЃРїРѕСЃРѕР±Р° РїСЂРѕРІРµСЂРёС‚СЊ СЂР°Р±РѕС‚РѕСЃРїРѕСЃРѕР±РЅРѕСЃС‚СЊ СЃР»СѓР¶Р±С‹ РґР»СЏ РјРѕРЅРёС‚РѕСЂРёРЅРіР°.

**Р РµС€РµРЅРёРµ:** Р”РѕР±Р°РІРёС‚СЊ РІ `app.py`:

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

**РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ:**
```bash
curl http://localhost:5000/health
# {"status": "ok", "jira": "connected"}
```

---

## рџџЎ РЎСЂРµРґРЅРёР№ РїСЂРёРѕСЂРёС‚РµС‚

### 3. Retry-Р»РѕРіРёРєР° РґР»СЏ Jira API

**РџСЂРѕР±Р»РµРјР°:** РџСЂРё РІСЂРµРјРµРЅРЅРѕР№ РЅРµРґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё Jira Р·Р°РїСЂРѕСЃС‹ РїР°РґР°СЋС‚ СЃСЂР°Р·Сѓ.

**Р РµС€РµРЅРёРµ:** Р”РѕР±Р°РІРёС‚СЊ РІ `jira_report.py`:

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

### 4. РЇРІРЅР°СЏ РїР°РіРёРЅР°С†РёСЏ Р·Р°РїСЂРѕСЃРѕРІ

**РџСЂРѕР±Р»РµРјР°:** РџСЂРё >5000 Р·Р°РґР°С‡ Р·Р° РїРµСЂРёРѕРґ РґР°РЅРЅС‹Рµ РјРѕРіСѓС‚ РїРѕС‚РµСЂСЏС‚СЊСЃСЏ.

**Р РµС€РµРЅРёРµ:** Р—Р°РјРµРЅРёС‚СЊ РІ `generate_report()`:

```python
# Р‘С‹Р»Рѕ:
issues = jira.search_issues(jql, maxResults=False)

# РЎС‚Р°Р»Рѕ:
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

### 5. Р’Р°Р»РёРґР°С†РёСЏ РІС…РѕРґРЅС‹С… РґР°РЅРЅС‹С… API

**РџСЂРѕР±Р»РµРјР°:** РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅР°СЏ РїСЂРѕРІРµСЂРєР° РїР°СЂР°РјРµС‚СЂРѕРІ РѕС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.

**Р РµС€РµРЅРёРµ:** Р”РѕР±Р°РІРёС‚СЊ РІ `app.py`:

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
    # Р”Р°Р»СЊС€Рµ РІР°Р»РёРґР°С†РёСЏ РїРѕР»РµР№...
```

---

## рџџў РќРёР·РєРёР№ РїСЂРёРѕСЂРёС‚РµС‚

### 6. Р РѕС‚Р°С†РёСЏ Р»РѕРіРѕРІ

**РџСЂРѕР±Р»РµРјР°:** Р›РѕРіРё РїРёС€СѓС‚СЃСЏ С‚РѕР»СЊРєРѕ РІ systemd journal, РЅРµС‚ С„Р°Р№Р»Р°.

**Р РµС€РµРЅРёРµ:** Р”РѕР±Р°РІРёС‚СЊ РІ `app.py`:

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

### 7. Р‘СЌРєР°Рї РєРѕРЅС„РёРіСѓСЂР°С†РёРё

**РџСЂРѕР±Р»РµРјР°:** `.env` вЂ” РµРґРёРЅСЃС‚РІРµРЅРЅРѕРµ РјРµСЃС‚Рѕ С…СЂР°РЅРµРЅРёСЏ РєРѕРЅС„РёРіР°.

**Р РµС€РµРЅРёРµ:** РЎРѕР·РґР°С‚СЊ `backup-config.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/jira-report"
mkdir -p "$BACKUP_DIR"
cp .env "$BACKUP_DIR/.env.$(date +%Y%m%d_%H%M%S)"
# РҐСЂР°РЅРёС‚СЊ РїРѕСЃР»РµРґРЅРёРµ 10 Р±СЌРєР°РїРѕРІ
ls -t "$BACKUP_DIR" | tail -n +11 | xargs -r rm
```

---

### 8. Р’РµСЂСЃРёРѕРЅРёСЂРѕРІР°РЅРёРµ РєРѕРЅС„РёРіСѓСЂР°С†РёРё

**РџСЂРѕР±Р»РµРјР°:** РќРµС‚ РїСЂРѕРІРµСЂРєРё СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё `.env` РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё.

**Р РµС€РµРЅРёРµ:** Р”РѕР±Р°РІРёС‚СЊ РІ `.env`:

```ini
CONFIG_VERSION=1.0
```

РџСЂРѕРІРµСЂРєР° РІ `jira_report.py`:

```python
REQUIRED_VERSION = '1.0'
config_version = os.getenv('CONFIG_VERSION', '1.0')
if config_version != REQUIRED_VERSION:
    logger.warning(f"Р’РµСЂСЃРёСЏ РєРѕРЅС„РёРіР° {config_version} != {REQUIRED_VERSION}")
```

---

### 9. РљСЌС€РёСЂРѕРІР°РЅРёРµ СЃРїРёСЃРєРѕРІ РїСЂРѕРµРєС‚РѕРІ Рё РёСЃРїРѕР»РЅРёС‚РµР»РµР№

**РџСЂРѕР±Р»РµРјР°:** РљР°Р¶РґС‹Р№ Р·Р°РїСЂРѕСЃ `/api/projects` Рё `/api/assignees` С…РѕРґРёС‚ РІ Jira.

**Р РµС€РµРЅРёРµ:** Р”РѕР±Р°РІРёС‚СЊ РєСЌС€ РЅР° 5 РјРёРЅСѓС‚:

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

### 10. Р­РєСЃРїРѕСЂС‚ РІ CSV

**РџСЂРѕР±Р»РµРјР°:** РўРѕР»СЊРєРѕ Excel, РЅРµ РІСЃРµ Р»СЋР±СЏС‚ xlsx.

**Р РµС€РµРЅРёРµ:** Р”РѕР±Р°РІРёС‚СЊ endpoint:

```python
@app.route('/api/download/csv', methods=['POST'])
def api_download_csv():
    # РђРЅР°Р»РѕРіРёС‡РЅРѕ /api/download, РЅРѕ:
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

## рџ“Љ РџР»Р°РЅ РІРЅРµРґСЂРµРЅРёСЏ

| Р­С‚Р°Рї | Р—Р°РґР°С‡Рё | Р’СЂРµРјСЏ |
|------|--------|-------|
| 1 | Gunicorn + Health check | 30 РјРёРЅ |
| 2 | Retry-Р»РѕРіРёРєР° + РџР°РіРёРЅР°С†РёСЏ | 45 РјРёРЅ |
| 3 | Р’Р°Р»РёРґР°С†РёСЏ API + Р РѕС‚Р°С†РёСЏ Р»РѕРіРѕРІ | 30 РјРёРЅ |
| 4 | РљСЌС€ + Р‘СЌРєР°РїС‹ + Р’РµСЂСЃРёРѕРЅРёСЂРѕРІР°РЅРёРµ | 40 РјРёРЅ |

---

## рџ“ќ Changelog

| Р”Р°С‚Р° | Р’РµСЂСЃРёСЏ | РР·РјРµРЅРµРЅРёСЏ |
|------|--------|-----------|
| 2024-01-01 | 1.0.0 | РќР°С‡Р°Р»СЊРЅР°СЏ РІРµСЂСЃРёСЏ РґРѕРєСѓРјРµРЅС‚Р° |
