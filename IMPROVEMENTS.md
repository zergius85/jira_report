# 💡 Предложения по улучшению кода

Документ содержит детальный анализ кода и конкретные предложения по рефакторингу.

**Дата анализа:** 5 марта 2026

---

## 📋 Содержание

1. [Архитектурные улучшения](#архитектурные-улучшения)
2. [Улучшения кода core/jira_report.py](#улучшения-кода-corejira_reportpy)
3. [Улучшения кода web/app.py](#улучшения-кода-webapppy)
4. [Улучшения конфигурации](#улучшения-конфигурации)
5. [Тестирование](#тестирование)

---

## Архитектурные улучшения

### 1. Выделение классов для основных сущностей

**Проблема:** Вся логика находится в функциях, нет инкапсуляции.

**Решение:** Создать классы:

```python
# core/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class JiraIssue:
    key: str
    id: str
    summary: str
    assignee: Optional[str]
    status: str
    timespent: Optional[int]
    timeoriginalestimate: Optional[int]
    resolutiondate: Optional[datetime]
    created: datetime
    issuetype: str
    problems: List[str]

@dataclass
class ReportBlock:
    name: str
    description: str
    data: Any
    columns: List[str]

@dataclass
class ReportResult:
    period: str
    blocks: List[ReportBlock]
    totals: Dict[str, Any]
```

**Преимущества:**
- Типизация данных
- Упрощение тестирования
- Лучшая читаемость

---

### 2. Разделение ответственности в jira_report.py

**Проблема:** Функция `generate_report()` делает слишком много (800+ строк).

**Решение:** Разбить на классы:

```python
# core/report_generator.py
class ReportGenerator:
    def __init__(self, jira_connection, config):
        self.jira = jira_connection
        self.config = config
    
    def generate(self, filters) -> ReportResult:
        issues = self._fetch_issues(filters)
        validated = self._validate_issues(issues)
        return self._build_report(validated)

# core/issue_fetcher.py
class IssueFetcher:
    def __init__(self, jira_connection):
        self.jira = jira_connection
    
    def fetch_by_project(self, project_key, jql) -> List[JiraIssue]:
        ...
    
    def fetch_all(self, jql) -> List[JiraIssue]:
        ...

# core/issue_validator.py
class IssueValidator:
    def __init__(self, config):
        self.config = config
    
    def validate(self, issue: JiraIssue) -> List[str]:
        problems = []
        if not issue.resolutiondate:
            problems.append('Нет даты решения')
        if not issue.timespent:
            problems.append('Нет фактического времени')
        return problems
```

---

### 3. Использование SQLAlchemy для кэширования

**Проблема:** При каждом запуске идёт запрос в Jira за всеми задачами.

**Решение:** Добавить локальную БД (SQLite) для кэширования:

```python
# core/database.py
from sqlalchemy import create_engine, Column, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class CachedIssue(Base):
    __tablename__ = 'issues'
    id = Column(String, primary_key=True)
    key = Column(String)
    summary = Column(String)
    # ... другие поля
    cached_at = Column(DateTime)

engine = create_engine('sqlite:///jira_cache.db')
Session = sessionmaker(bind=engine)
```

**Преимущества:**
- Ускорение повторных запусков
- Возможность работать офлайн
- История изменений

---

## Улучшения кода core/jira_report.py

### 4. Устранение дублирования кода

**Проблема:** Нормализация фильтров повторяется:

```python
# Сейчас (строки ~400-410):
if isinstance(project_keys, str):
    project_keys = [project_keys.upper()]
elif project_keys is None:
    project_keys = []
else:
    project_keys = [p.upper() for p in project_keys]

if isinstance(assignee_filter, str):
    assignee_filter = [assignee_filter]
elif assignee_filter is None:
    assignee_filter = []
```

**Решение:** Создать utility-функцию:

```python
# core/utils.py
def normalize_filter(value: Optional[Union[str, List[str]]]) -> List[str]:
    """Нормализует фильтр: строка -> список, None -> пустой список"""
    if value is None:
        return []
    if isinstance(value, str):
        return [value.upper()]
    return [v.upper() for v in value]

# Использование:
project_keys = normalize_filter(project_keys)
assignee_filter = normalize_filter(assignee_filter)
```

---

### 5. Обработка ошибок валидации

**Проблема:** Функция `validate_issue()` возвращает список проблем, но неясно, что делать с исключениями.

**Решение:** Создать результат валидации:

```python
# core/validation.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ValidationResult:
    is_valid: bool
    problems: List[str]
    warnings: List[str]
    error: Optional[str] = None  # Если произошла ошибка валидации

class IssueValidator:
    def validate(self, issue: JiraIssue) -> ValidationResult:
        try:
            problems = []
            warnings = []
            
            if not issue.resolutiondate:
                problems.append('Нет даты решения')
            if not issue.timespent:
                problems.append('Нет фактического времени')
            
            return ValidationResult(
                is_valid=len(problems) == 0,
                problems=problems,
                warnings=warnings
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                problems=[],
                warnings=[],
                error=str(e)
            )
```

---

### 6. Магические числа и строки

**Проблема:** В коде много магических значений:

```python
# Строка ~770
if days_inactive > 5 and issue.fields.status.name.lower() not in ['закрыт', 'closed', 'done']:
```

**Решение:** Вынести в константы:

```python
# core/constants.py
CLOSED_STATUSES = ['закрыт', 'closed', 'done', 'закрыто']
DEFAULT_INACTIVE_DAYS_THRESHOLD = 5
MAX_REPORT_DAYS = 365
DEFAULT_REPORT_DAYS = 30

# Использование:
if days_inactive > DEFAULT_INACTIVE_DAYS_THRESHOLD 
    and issue.fields.status.name.lower() not in CLOSED_STATUSES:
```

---

### 7. Формирование JQL-запросов

**Проблема:** JQL собирается конкатенацией строк:

```python
jql_normal = (f"project = {proj_key} "
              f"AND resolved >= '{start_date_str}' "
              f"AND resolved <= '{end_date_str}'"
              f"{issue_type_filter}"
              f"{assignee_filter_jql} "
              f"ORDER BY resolved ASC")
```

**Решение:** Использовать builder:

```python
# core/jql_builder.py
class JQLBuilder:
    def __init__(self):
        self.conditions = []
        self.order_by = None
    
    def project(self, key: str) -> 'JQLBuilder':
        self.conditions.append(f"project = {key}")
        return self
    
    def resolved_between(self, start: str, end: str) -> 'JQLBuilder':
        self.conditions.append(f"resolved >= '{start}' AND resolved <= '{end}'")
        return self
    
    def assignee_in(self, assignees: List[str]) -> 'JQLBuilder':
        if assignees:
            self.conditions.append(f"assignee IN ({','.join(assignees)})")
        return self
    
    def order_by(self, field: str, asc: bool = True) -> 'JQLBuilder':
        self.order_by = f"ORDER BY {field} {'ASC' if asc else 'DESC'}"
        return self
    
    def build(self) -> str:
        jql = " AND ".join(self.conditions)
        if self.order_by:
            jql += f" {self.order_by}"
        return jql

# Использование:
jql = (JQLBuilder()
    .project(proj_key)
    .resolved_between(start_date_str, end_date_str)
    .assignee_in(assignee_filter)
    .order_by('resolved', asc=True)
    .build())
```

---

## Улучшения кода web/app.py

### 8. Выделение API routes в blueprint

**Проблема:** Все routes в одном файле.

**Решение:** Использовать Flask Blueprints:

```python
# web/api/__init__.py
from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

# web/api/projects.py
from . import api_bp

@api_bp.route('/projects')
def api_projects():
    ...

# web/api/assignees.py
from . import api_bp

@api_bp.route('/assignees')
def api_assignees():
    ...

# web/app.py
from web.api import api_bp
app.register_blueprint(api_bp)
```

---

### 9. Централизованная обработка ошибок

**Проблема:** В каждом endpoint свой try/except.

**Решение:** Использовать error handlers:

```python
# web/error_handlers.py
from flask import jsonify
from werkzeug.exceptions import HTTPException

def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        return jsonify({
            'success': False,
            'error': e.description,
            'code': e.code
        }), e.code
    
    @app.errorhandler(Exception)
    def handle_generic_error(e):
        app.logger.error(f"Unhandled error: {e}")
        return jsonify({
            'success': False,
            'error': 'Внутренняя ошибка сервера'
        }), 500

# web/app.py
from web.error_handlers import register_error_handlers
register_error_handlers(app)
```

---

### 10. Валидация запросов API

**Проблема:** Параметры проверяются внутри каждой функции.

**Решение:** Использовать декоратор валидации:

```python
# web/validators.py
from functools import wraps
from flask import request, jsonify

def validate_report_request(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        errors = []
        
        days = data.get('days', 0)
        if not isinstance(days, int) or days < 0 or days > 365:
            errors.append('days должен быть от 0 до 365')
        
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
        
        return f(*args, **kwargs)
    return decorated

# Использование:
@app.route('/api/report', methods=['POST'])
@validate_report_request
def api_report():
    ...
```

---

## Улучшения конфигурации

### 11. Использование Pydantic для конфигурации

**Проблема:** Конфигурация загружается из env без валидации.

**Решение:** Использовать Pydantic:

```python
# core/config.py
from pydantic import BaseSettings, HttpUrl, Field
from typing import List

class Settings(BaseSettings):
    jira_server: HttpUrl = Field(..., env='JIRA_SERVER')
    jira_user: str = Field(..., env='JIRA_USER')
    jira_pass: str = Field(..., env='JIRA_PASS')
    
    excluded_projects: List[str] = Field(default_factory=list)
    ssl_verify: bool = True
    flask_env: str = 'development'
    
    class Config:
        env_file = '.env'
        case_sensitive = False

settings = Settings()

# Использование:
from core.config import settings
jira = JIRA(server=settings.jira_server, ...)
```

**Преимущества:**
- Автоматическая валидация типов
- Чёткая схема конфигурации
- Лучшая документация

---

### 12. Разделение секретов и настроек

**Проблема:** Все настройки в одном `.env`.

**Решение:** Разделить на `.env` (секреты) и `settings.yaml` (настройки):

```yaml
# settings.yaml
projects:
  excluded:
    - TEST
    - DEMO
  
report:
  default_days: 30
  max_days: 365
  
ui:
  items_per_page: 50
```

```python
# core/config.py
import yaml

class Config:
    def __init__(self):
        with open('settings.yaml') as f:
            settings = yaml.safe_load(f)
        
        self.excluded_projects = settings['projects']['excluded']
        self.default_days = settings['report']['default_days']
        
        # Секреты из env
        self.jira_server = os.getenv('JIRA_SERVER')
```

---

## Тестирование

### 13. Покрытие тестами

**Текущее состояние:** Тестируются только utility-функции.

**Цель:** Добавить тесты для:
- `generate_report()` — интеграционные тесты с mock Jira
- API endpoints — тесты с Flask test client
- Валидации — параметризованные тесты

```python
# tests/test_api.py
import pytest
from web.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_api_projects_success(client):
    response = client.get('/api/projects')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
```

---

### 14. Mock Jira для тестов

**Проблема:** Тесты требуют подключения к реальной Jira.

**Решение:** Создать фиктивную Jira:

```python
# tests/mocks.py
from unittest.mock import Mock

def create_mock_jira():
    jira = Mock()
    
    # Mock проектов
    project = Mock()
    project.key = 'TEST'
    project.name = 'Test Project'
    jira.projects.return_value = [project]
    
    # Mock search_issues
    issue = Mock()
    issue.key = 'TEST-1'
    issue.fields.status.name = 'Done'
    issue.fields.timespent = 3600
    jira.search_issues.return_value = [issue]
    
    return jira

# tests/test_report.py
def test_generate_report():
    mock_jira = create_mock_jira()
    with patch('core.jira_report.get_jira_connection', return_value=mock_jira):
        report = generate_report()
        assert report['total_tasks'] > 0
```

---

## 📊 Приоритеты внедрения

| Приоритет | Задача | Сложность | Время |
|-----------|--------|-----------|-------|
| 🔴 Высокий | Выделение классов (1-3) | Средняя | 4 часа |
| 🔴 Высокий | Устранение дублирования (4) | Низкая | 30 мин |
| 🟡 Средний | JQL Builder (7) | Средняя | 1 час |
| 🟡 Средний | Blueprint для API (8) | Низкая | 1 час |
| 🟢 Низкий | Pydantic config (11) | Средняя | 2 часа |
| 🟢 Низкий | Расширение тестов (13-14) | Высокая | 6 часов |

---

## 📝 Changelog предложений

| Дата | Предложение | Статус |
|------|-------------|--------|
| 2026-03-05 | Начальный анализ | ✅ Создано |
