# 📊 Логика работы кнопки "Эта неделя"

**Версия:** v2.5.0  
**Дата обновления:** 12.03.2026

---

## 📋 Содержание

1. [Общая схема работы](#общая-схема-работы)
2. [Frontend: Вычисление дат](#frontend-вычисление-дат)
3. [Backend: API Endpoint](#backend-api-endpoint)
4. [Jira Query Language (JQL) запросы](#jira-query-language-jql-запросы)
5. [Обработка данных](#обработка-данных)
6. [Risk Zone: Проверка рисков](#risk-zone-проверка-рисков)
7. [Формирование ответа](#формирование-ответа)

---

## 🔄 Общая схема работы

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         КЛИЕНТ (Браузер)                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  index.html + JavaScript                                        │   │
│  │  • applyQuickPreset('this_week')                                │   │
│  │  • generateReport()                                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              │ POST /api/report                         │
│                              │ {projects, assignees, days, blocks...}   │
│                              ▼                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                         BACKEND (Flask)                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  web/app.py: @app.route('/api/report')                          │   │
│  │  • validate_json_request                                        │   │
│  │  • conditional_cache (5 мин, production)                        │   │
│  │  • normalize_filter()                                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              │ generate_report()                        │
│                              ▼                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                         CORE (Ядро)                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  core/jira_report.py: generate_report()                         │   │
│  │  • check_jira_availability()                                    │   │
│  │  • get_jira_connection()                                        │   │
│  │  • fetch_issues_via_rest() × 2                                  │   │
│  │  • IssueValidator.validate()                                    │   │
│  │  • Risk Zone проверка                                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              │ REST API                                 │
│                              ▼                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                         JIRA SERVER                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  • GET /rest/api/2/serverInfo                                   │   │
│  │  • GET /rest/api/2/search?jql=...                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🖥️ Frontend: Вычисление дат

### Файл: `templates/index.html`

**Функция:** `applyQuickPreset(presetName)` (строки ~1475-1545)

### Логика вычисления дат для "Эта неделя"

```javascript
case 'this_week':
    presetName = 'Эта неделя';
    // Эта неделя (Пн-сегодня)
    // getDay(): 0=Вс, 1=Пн, 2=Вт, ..., 6=Сб
    
    const currentDayOfWeek = today.getDay();
    
    // Вычисляем сколько дней назад был понедельник
    // Если сегодня Вс (0), то понедельник был 6 дней назад
    // Если сегодня Пн (1), то понедельник был 0 дней назад
    // Если сегодня Вт (2), то понедельник был 1 день назад
    const mondayOffset = currentDayOfWeek === 0 ? 6 : currentDayOfWeek - 1;
    
    // Находим понедельник текущей недели
    const weekMonday = new Date(today);
    weekMonday.setDate(today.getDate() - mondayOffset);
    
    startDate = weekMonday;  // Понедельник
    endDate = new Date(today);  // Сегодня
```

### Примеры вычислений

| Сегодня | Day() | mondayOffset | Start Date | End Date | Дней |
|---------|-------|--------------|------------|----------|------|
| Пн      | 1     | 0            | Пн         | Пн       | 1    |
| Вт      | 2     | 1            | Пн         | Вт       | 2    |
| Ср      | 3     | 2            | Пн         | Ср       | 3    |
| Чт      | 4     | 3            | Пн         | Чт       | 4    |
| Пт      | 5     | 4            | Пн         | Пт       | 5    |
| Сб      | 6     | 5            | Пн         | Сб       | 6    |
| Вс      | 0     | 6            | Пн         | Вс       | 7    |

### Формирование параметров запроса

```javascript
function getParams() {
    return {
        projects: projects.length > 0 ? projects : null,
        assignees: assignees.length > 0 ? assignees : null,
        issue_types: issueTypes.length > 0 ? issueTypes : null,
        start_date: "2026-03-09",  // Пример: понедельник
        end_date: "2026-03-12",    // Пример: сегодня (четверг)
        days: 4,                   // (12-9)+1 = 4 дня
        blocks: ["summary", "assignees", "detail", "issues", "risk_zone"],
        extra_verbose: false
    };
}
```

---

## 🔌 Backend: API Endpoint

### Файл: `web/app.py`

**Endpoint:** `POST /api/report` (строки ~595-700)

### Декораторы

```python
@app.route('/api/report', methods=['POST'])
@validate_json_request        # Проверяет Content-Type и валидность JSON
@conditional_cache(timeout=300)  # Кэш 5 минут (только production)
def api_report():
```

### Обработка запроса

```python
# 1. Извлечение параметров
data = request.get_json()
projects_raw = data.get('projects', []) or data.get('project', '').strip() or None
assignees_raw = data.get('assignees', []) or data.get('assignee', '').strip() or None
issue_types_raw = data.get('issue_types', []) or data.get('issue_type', '').strip() or None

# 2. Нормализация фильтров
projects = normalize_filter(projects_raw, upper=True) if projects_raw else []
assignees = normalize_filter(assignees_raw) if assignees_raw else []
issue_types = normalize_filter(issue_types_raw) if issue_types_raw else []

start_date = data.get('start_date', '').strip() or None
end_date = data.get('end_date', '').strip() or None
days = int(data.get('days', 0) or 0)
blocks = data.get('blocks', None)
extra_verbose = data.get('extra_verbose', False)

# 3. Валидация
if days < 0 or days > MAX_REPORT_DAYS:
    return jsonify({'error': f'Период должен быть от 0 до {MAX_REPORT_DAYS} дней'}), 400

# 4. Вызов ядра
report = generate_report(
    project_keys=projects,
    start_date=start_date,
    end_date=end_date,
    days=days,
    assignee_filter=assignees,
    issue_types=issue_types,
    blocks=blocks,
    verbose=False,
    extra_verbose=extra_verbose
)
```

---

## 🔍 Jira Query Language (JQL) запросы

### Файл: `core/jira_report.py`

**Функция:** `generate_report()` (строки ~481-1300)

### Шаг 1: Проверка доступности Jira

**Метод:** HTTP GET запрос (без Jira client)

```python
def check_jira_availability() -> Tuple[bool, str]:
    response = requests.get(
        f'{JIRA_SERVER}/rest/api/2/serverInfo',
        auth=HTTPBasicAuth(JIRA_USER, JIRA_PASS),
        verify=SSL_VERIFY,
        timeout=10
    )
```

**Запрос:**
```
GET https://jira.example.com/rest/api/2/serverInfo
Authorization: Basic base64(username:password)
```

**Ответ (успех):**
```json
{
  "baseUrl": "https://jira.example.com",
  "version": "9.4.0",
  "versionNumbers": [9, 4, 0],
  "deploymentType": "Server"
}
```

---

### Шаг 2: Получение списка проектов

**Если проекты не указаны** (все проекты) → используется оптимизация:

```python
# JQL для получения всех проектов за период
jql_all_projects = (
    f"created >= '{start_date_safe}' "
    f"AND created <= '{issues_end_safe}' "
    f"ORDER BY created DESC"
)

# Получаем все задачи за период для определения проектов
all_issues_temp = search_all_issues(
    jira,
    jql_all_projects,
    fields='project',
    batch_size=100
)
```

**Запрос к Jira:**
```
GET /rest/api/2/search?jql=created+%3E%3D+'2026-03-09'+AND+created+%3C%3D+'2026-05-12'+ORDER+BY+created+DESC&fields=project&maxResults=100
```

**Ответ:**
```json
{
  "expand": "schema,names",
  "startAt": 0,
  "maxResults": 100,
  "total": 42,
  "issues": [
    {
      "key": "WEB-123",
      "fields": {
        "project": {
          "key": "WEB",
          "name": "Website Project",
          "id": "10001"
        }
      }
    },
    ...
  ]
}
```

---

### Шаг 3: Два основных JQL-запроса (ОПТИМИЗАЦИЯ)

**Вместо N запросов на проект → 2 глобальных запроса**

#### Запрос 1: Для обычных задач (по duedate)

```python
# Формирование фильтра по проектам
projects_jql = ','.join([sanitize_jql_identifier(p) for p in projects_keys])
# Пример: "WEB,MOBILE,API"

# Фильтр по типам задач (если указан)
issue_type_filter = ''
if issue_types and len(issue_types) > 0:
    sanitized_types = [sanitize_jql_identifier(t) for t in issue_types]
    issue_type_filter = ' AND issuetype IN (' + ','.join(sanitized_types) + ')'
    # Пример: " AND issuetype IN (1,2,3)"

# Фильтр по исполнителям (если указан)
assignee_filter_jql = ''
if assignee_filter and len(assignee_filter) > 0:
    sanitized_assignees = [sanitize_jql_identifier(a) for a in assignee_filter]
    assignee_filter_jql = ' AND assignee IN (' + ','.join(sanitized_assignees) + ')'
    # Пример: " AND assignee IN (ivanov,petrov)"

# Итоговый JQL для обычных задач
if days > 0:
    jql_normal_global = (
        f"project IN ({projects_jql}) "
        f"AND (duedate >= '{start_date_safe}' "
        f"OR duedate is null)"
        f"{issue_type_filter}"
        f"{assignee_filter_jql} "
        f"ORDER BY duedate ASC"
    )
else:
    jql_normal_global = (
        f"project IN ({projects_jql}) "
        f"AND duedate is null"
        f"{issue_type_filter}"
        f"{assignee_filter_jql} "
        f"ORDER BY created DESC"
    )
```

**Пример JQL (days=4, с 09.03 по 12.03):**
```jql
project IN (WEB,MOBILE,API) 
AND (duedate >= '2026-03-09' OR duedate is null)
AND issuetype IN (1,2,3)
AND assignee IN (ivanov,petrov)
ORDER BY duedate ASC
```

**URL-кодированный запрос:**
```
GET /rest/api/2/search?jql=project+IN+(WEB,MOBILE,API)+AND+(duedate+%3E%3D+'2026-03-09'+OR+duedate+is+null)+AND+issuetype+IN+(1,2,3)+AND+assignee+IN+(ivanov,petrov)+ORDER+BY+duedate+ASC&fields=*all&maxResults=100
```

---

#### Запрос 2: Для проблемных задач (по created + 2 месяца)

```python
# Для проблемных задач: период + 2 месяца вперёд
# issues_end_str = end_date + 2 месяца

if days > 0:
    jql_issues_global = (
        f"project IN ({projects_jql}) "
        f"AND created >= '{start_date_safe}' "
        f"AND created <= '{issues_end_safe}'"
        f"{issue_type_filter}"
        f"{assignee_filter_jql} "
        f"ORDER BY created ASC"
    )
else:
    jql_issues_global = (
        f"project IN ({projects_jql}) "
        f"AND created is not null"
        f"{issue_type_filter}"
        f"{assignee_filter_jql} "
        f"ORDER BY created DESC"
    )
```

**Пример JQL (для отчёта с 09.03 по 12.03, issues_end = 12.05):**
```jql
project IN (WEB,MOBILE,API) 
AND created >= '2026-03-09' 
AND created <= '2026-05-12'
AND issuetype IN (1,2,3)
AND assignee IN (ivanov,petrov)
ORDER BY created ASC
```

**Почему +2 месяца?**  
Чтобы захватить задачи, которые были созданы в отчётном периоде, но могли быть закрыты позже (для корректного отображения проблемных задач).

---

### Шаг 4: Выполнение запросов через REST API

**Функция:** `fetch_issues_via_rest(jira, jql)`

```python
def fetch_issues_via_rest(jira, jql_query, fields='*all', batch_size=100):
    """
    Получает все задачи через REST API с пагинацией.
    """
    all_issues = []
    start_at = 0
    
    while True:
        response = jira._session.get(
            f'{jira.server}/rest/api/2/search',
            params={
                'jql': jql_query,
                'fields': fields,
                'maxResults': batch_size,
                'startAt': start_at
            }
        )
        
        data = response.json()
        all_issues.extend(data.get('issues', []))
        
        # Проверка на наличие ещё данных
        if len(data.get('issues', [])) < batch_size:
            break
        
        start_at += batch_size
    
    return all_issues
```

**Запрос 1 (нормальные задачи):**
```
GET /rest/api/2/search?jql=project+IN+(WEB,MOBILE,API)+AND+(duedate+%3E%3D+'2026-03-09'+OR+duedate+is+null)+ORDER+BY+duedate+ASC&fields=*all&maxResults=100&startAt=0
```

**Запрос 2 (проблемные задачи):**
```
GET /rest/api/2/search?jql=project+IN+(WEB,MOBILE,API)+AND+created+%3E%3D+'2026-03-09'+AND+created+%3C%3D+'2026-05-12'+ORDER+BY+created+ASC&fields=*all&maxResults=100&startAt=0
```

---

### Шаг 5: Получение дополнительных данных (Risk Zone)

**Функция:** Проверка Risk Zone (строки ~1119-1200)

Для Risk Zone **не требуется дополнительных запросов** — используются данные из `issues_normal_global`.

**Проверка для каждой задачи:**

```python
for issue_data in all_issues_normal:
    fields = issue_data.get('fields', {})
    risk_factors = []
    
    # 1. Задачи без исполнителя
    assignee = fields.get('assignee')
    if not assignee:
        risk_factors.append('Без исполнителя')
    
    # 2. Задачи с истёкшим сроком (Due Date)
    duedate = fields.get('duedate')
    if duedate:
        due_date = datetime.strptime(duedate[:10], '%Y-%m-%d')
        if due_date.date() < today.date() and not is_status_closed(status_name, status_id):
            days_overdue = (today.date() - due_date.date()).days
            risk_factors.append(f'Просрочена на {days_overdue} дн.')
    
    # 3. Задачи, которые не двигались > порога
    updated = fields.get('updated')
    if updated:
        updated_dt = datetime.strptime(updated[:19], '%Y-%m-%dT%H:%M:%S')
        days_inactive = (today - updated_dt).days
        if days_inactive > RISK_ZONE_INACTIVITY_THRESHOLD and not is_status_closed(status_name, status_id):
            risk_factors.append(f'Не двигается {days_inactive} дн.')
```

**Порог неактивности:** `RISK_ZONE_INACTIVITY_THRESHOLD = 5` дней (из config.py)

---

## 📊 Обработка данных

### Валидация задач

**Файл:** `core/services/issue_validator.py`

**Функция:** `IssueValidator.validate(issue, project_key)`

```python
def validate(self, issue: IssueDTO, project_key: str) -> List[str]:
    """
    Проверяет задачу на наличие проблем.
    Возвращает список проблем.
    """
    problems = []
    fields = issue.fields
    
    # 1. Проверка исполнителя
    if not fields.assignee:
        problems.append('Без исполнителя')
    
    # 2. Проверка статуса
    if fields.status and fields.status.name not in self.closed_statuses:
        # Задача не закрыта
        if not fields.timespent or fields.timespent == 0:
            problems.append('Нет времени')
    
    # 3. Проверка даты решения
    if fields.resolutiondate and fields.resolutiondate == '-':
        problems.append('Нет даты решения')
    
    # 4. Проверка времени
    if fields.timespent and fields.timeoriginalestimate:
        if fields.timespent > fields.timeoriginalestimate * 1.5:
            problems.append('Перерасход времени')
    
    return problems
```

**Словарь проблем:** `core/problems_dict.py`

```python
PROBLEM_DESCRIPTIONS = {
    'Без исполнителя': 'Задача не назначена на исполнителя',
    'Нет времени': 'Не указано фактическое время (timespent)',
    'Нет даты решения': 'Не заполнена дата решения (resolutiondate)',
    'Перерасход времени': 'Фактическое время превышает оценку более чем на 50%',
    'Просрочена': 'Дата исполнения (duedate) истекла',
    'Не двигается': 'Задача не обновлялась более 5 дней'
}
```

---

### Агрегация статистики по проектам

```python
# Словарь для агрегации: proj_key → {spent, estimated, correct, issues}
project_stats = {
    proj_key: {'name': proj_name, 'spent': 0, 'estimated': 0, 'correct': 0, 'issues': 0}
    for proj_key, proj_name in projects_map.items()
}

# Обработка каждой задачи
for issue_data in issues_normal_global:
    fields = issue_data.get('fields', {})
    proj_key = fields.get('project', {}).get('key', '')
    
    timespent = fields.get('timespent')
    timeoriginalestimate = fields.get('timeoriginalestimate')
    spent = convert_seconds_to_hours(timespent)
    estimated = convert_seconds_to_hours(timeoriginalestimate)
    
    # Валидация
    problems = validator.validate(mock_issue, proj_key)
    
    # Агрегация
    if not problems:
        project_stats[proj_key]['spent'] += spent
        project_stats[proj_key]['estimated'] += estimated
        project_stats[proj_key]['correct'] += 1
    else:
        project_stats[proj_key]['issues'] += 1
```

---

## 🔴 Risk Zone: Проверка рисков

### Файл: `core/jira_report.py` (строки ~1119-1200)

**Логика проверки:**

```python
today = datetime.now()
risk_issues = []

for issue_data in all_issues_normal:
    fields = issue_data.get('fields', {})
    issue_key = issue_data.get('key', '')
    risk_factors = []
    
    status = fields.get('status', {})
    status_name = status.get('name', '')
    status_id = status.get('id', '')
    
    # ========== ФАКТОР 1: Без исполнителя ==========
    assignee = fields.get('assignee')
    if not assignee:
        risk_factors.append('Без исполнителя')
    
    # ========== ФАКТОР 2: Просрочена ==========
    duedate = fields.get('duedate')
    if duedate:
        due_date = datetime.strptime(duedate[:10], '%Y-%m-%d')
        
        # Проверка: duedate < сегодня И статус НЕ закрытый
        if due_date.date() < today.date() and not is_status_closed(status_name, status_id):
            days_overdue = (today.date() - due_date.date()).days
            risk_factors.append(f'Просрочена на {days_overdue} дн.')
    
    # ========== ФАКТОР 3: Не двигается ==========
    updated = fields.get('updated')
    if updated:
        updated_dt = datetime.strptime(updated[:19], '%Y-%m-%dT%H:%M:%S')
        days_inactive = (today - updated_dt).days
        
        # Проверка: не обновлялась > 5 дней И статус НЕ закрытый
        if days_inactive > RISK_ZONE_INACTIVITY_THRESHOLD and not is_status_closed(status_name, status_id):
            risk_factors.append(f'Не двигается {days_inactive} дн.')
    
    # Если есть факторы риска — добавляем в отчёт
    if risk_factors:
        risk_issues.append({
            'URL': f"{JIRA_SERVER}/browse/{issue_key}",
            'Ключ': issue_key,
            'Задача': fields.get('summary', ''),
            'Исполнитель': assignee.get('displayName', 'Без исполнителя') if assignee else 'Без исполнителя',
            'Статус': status_name,
            'Факторы риска': '; '.join(risk_factors),
            'Приоритет': fields.get('priority', {}).get('name', 'Normal')
        })
```

**Пример записи Risk Zone:**

| URL | Ключ | Задача | Исполнитель | Статус | Факторы риска | Приоритет |
|-----|------|--------|-------------|--------|---------------|-----------|
| https://jira/browse/WEB-123 | WEB-123 | Добавить кнопку | Без исполнителя | In Progress | Без исполнителя; Просрочена на 3 дн. | High |
| https://jira/browse/WEB-124 | WEB-124 | Исправить баг | Иванов А. | Open | Не двигается 7 дн. | Normal |

---

## 📤 Формирование ответа

### Структура ответа API

**Файл:** `web/app.py` (строки ~655-695)

```python
response = {
    'success': True,
    'period': '2026-03-09 — 2026-03-12',
    'totals': {
        'projects': 5,
        'tasks': 42,
        'correct': 35,
        'issues': 7,
        'spent': 125.5,
        'estimated': 140.0
    },
    'blocks': ['summary', 'assignees', 'detail', 'issues', 'risk_zone'],
    'summary': [
        {'Клиент (Проект)': 'Website Project', 'Задач закрыто': 15, 'Корректных': 12, 'С ошибками': 3, ...},
        ...
    ],
    'assignees': [
        {'Исполнитель': 'Иванов А.', 'Задач': 10, 'Корректных': 8, 'С ошибками': 2, ...},
        ...
    ],
    'detail': [
        {'URL': 'https://jira/browse/WEB-123', 'Дата решения': '2026-03-10', ...},
        ...
    ],
    'issues': [
        {'URL': 'https://jira/browse/WEB-124', 'Проблемы': 'Без исполнителя, Нет времени', ...},
        ...
    ],
    'risk_zone': [
        {'URL': 'https://jira/browse/WEB-125', 'Факторы риска': 'Просрочена на 5 дн.', ...},
        ...
    ]
}
```

### Frontend: Обработка ответа

**Файл:** `templates/index.html` (строки ~2274-2350)

```javascript
async function generateReport() {
    const params = getParams();
    
    const response = await fetch('/api/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
    });
    
    const data = await response.json();
    
    // Обновление статистики
    document.getElementById('stat_projects').textContent = data.totals.projects;
    document.getElementById('stat_tasks').textContent = data.totals.tasks;
    document.getElementById('stat_correct').textContent = data.totals.correct;
    document.getElementById('stat_issues').textContent = data.totals.issues;
    
    // Обновление KPI
    updateKPI(data, previousData);
    
    // Рендер таблиц
    renderTable('summary', data.summary);
    renderTable('assignees', data.assignees);
    renderTable('detail', data.detail);
    renderTable('issues', data.issues);
    renderTable('risk', data.risk_zone);
    
    // Рендер графиков
    renderCharts(data);
    
    // Переключение на вкладку "Дашборд"
    switchTab('dashboard');
}
```

---

## 📈 Графики (Chart.js)

**Файл:** `templates/index.html` (строки ~2700-2900)

**Функция:** `renderCharts(data)`

```javascript
function renderCharts(data) {
    // 1. Динамика закрытия задач (по дате решения)
    renderClosedChart(data.detail);
    
    // 2. Динамика создания задач (по дате создания)
    renderCreatedChart(data.detail);
    
    // 3. Нагрузка по исполнителям
    renderAssigneesChart(data.assignees);
    
    // 4. Статусы задач
    renderStatusesChart(data.detail);
    
    // 5. Типы задач
    renderTypesChart(data.detail);
    
    // 6. Типы проблем
    renderProblemsChart(data.issues);
}
```

---

## 📊 Сводная таблица JQL-запросов

| № | Название | JQL | Поля | Цель |
|---|----------|-----|------|------|
| 1 | Проверка Jira | `GET /rest/api/2/serverInfo` | — | Проверка доступности |
| 2 | Проекты (если не указаны) | `created >= '2026-03-09' AND created <= '2026-05-12'` | `project` | Определение активных проектов |
| 3 | Нормальные задачи | `project IN (WEB,MOBILE) AND (duedate >= '2026-03-09' OR duedate is null)` | `*all` | Основной отчёт + Risk Zone |
| 4 | Проблемные задачи | `project IN (WEB,MOBILE) AND created >= '2026-03-09' AND created <= '2026-05-12'` | `*all` | Задачи с проблемами |

---

## ⚡ Оптимизация производительности

### До оптимизации
```
N проектов × 2 запроса = 2N запросов к Jira
Пример: 10 проектов → 20 запросов
```

### После оптимизации
```
2 глобальных запроса для всех проектов
Пример: 10 проектов → 2 запроса
```

### Кэширование

| Компонент | Время кэша | Режим |
|-----------|------------|-------|
| `/api/report` | 5 минут | Production |
| `/api/projects` | 5 минут | Production |
| `/api/assignees` | 5 минут | Production |
| `_project_cache` | 1 час | Все |

---

## 🔧 Конфигурация

**Файл:** `core/config.py`

```python
# Период отчёта
MAX_REPORT_DAYS = 365  # Максимум дней для отчёта

# Risk Zone
RISK_ZONE_INACTIVITY_THRESHOLD = 5  # Дней без активности

# Пагинация
MAX_SEARCH_RESULTS = 1000  # Максимум результатов поиска
MAX_EXCEL_ROWS = 100000    # Максимум строк в Excel

# Закрытые статусы (авто-определение)
CLOSED_STATUS_IDS = ['3', '4', '5', '6', '10', '10003']
```

---

## 📁 Карта файлов

```
jira_report/
├── templates/
│   └── index.html          # Frontend: кнопка "Эта неделя", generateReport()
├── web/
│   ├── app.py              # Backend: /api/report endpoint
│   └── middleware.py       # Middleware: валидация, обработка ошибок
├── core/
│   ├── jira_report.py      # Ядро: generate_report(), JQL-запросы
│   ├── config.py           # Конфигурация
│   ├── problems_dict.py    # Словарь проблем
│   ├── utils.py            # Утилиты: sanitize_jql_identifier()
│   └── services/
│       ├── issue_validator.py      # Валидация задач
│       └── closed_status_service.py  # Проверка закрытых статусов
└── .env                    # Настройки: JIRA_SERVER, JIRA_USER, JIRA_PASS
```

---

## 📝 Пример полного цикла

### Исходные данные
- **Дата:** Четверг, 12 марта 2026
- **Проекты:** WEB, MOBILE
- **Исполнители:** ivanov, petrov
- **Типы задач:** Задача, Баг

### Шаг 1: Вычисление дат (Frontend)
```javascript
today = new Date(2026, 2, 12)  // 12 марта (месяцы с 0!)
currentDayOfWeek = 4           // Четверг
mondayOffset = 4 - 1 = 3
weekMonday = 12 - 3 = 9 марта
startDate = "2026-03-09"
endDate = "2026-03-12"
days = 4
```

### Шаг 2: Запрос к API
```json
POST /api/report
{
  "projects": ["WEB", "MOBILE"],
  "assignees": ["ivanov", "petrov"],
  "issue_types": ["1", "2"],
  "start_date": "2026-03-09",
  "end_date": "2026-03-12",
  "days": 4,
  "blocks": ["summary", "assignees", "detail", "issues", "risk_zone"],
  "extra_verbose": false
}
```

### Шаг 3: JQL-запросы к Jira
```jql
-- Запрос 1: Нормальные задачи
project IN (WEB,MOBILE) 
AND (duedate >= '2026-03-09' OR duedate is null)
AND issuetype IN (1,2)
AND assignee IN (ivanov,petrov)
ORDER BY duedate ASC

-- Запрос 2: Проблемные задачи
project IN (WEB,MOBILE) 
AND created >= '2026-03-09' 
AND created <= '2026-05-12'
AND issuetype IN (1,2)
AND assignee IN (ivanov,petrov)
ORDER BY created ASC
```

### Шаг 4: Результат
```json
{
  "success": true,
  "period": "2026-03-09 — 2026-03-12",
  "totals": {
    "projects": 2,
    "tasks": 15,
    "correct": 12,
    "issues": 3,
    "spent": 45.5,
    "estimated": 52.0
  },
  "risk_zone": [
    {
      "key": "WEB-125",
      "summary": "Исправить баг",
      "assignee": "Без исполнителя",
      "risk_factors": "Без исполнителя; Просрочена на 2 дн."
    }
  ]
}
```

---

## 🎯 Ключевые выводы

1. **2 запроса вместо N** — оптимизация через глобальные JQL
2. **REST API напрямую** — быстрее чем jira-client
3. **Кэширование** — 5 минут для API, 1 час для проектов
4. **Risk Zone без доп. запросов** — проверка по данным из основного запроса
5. **Валидация на клиенте** — `IssueValidator` проверяет все проблемы
6. **Пагинация** — автоматическая подгрузка при >100 результатов

---

**Документ создан:** 12.03.2026  
**Автор:** Qwen Code Analysis
