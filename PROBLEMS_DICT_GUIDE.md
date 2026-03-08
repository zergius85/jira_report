# 📘 Справочник проблем — Руководство по интеграции

**Версия:** 1.0  
**Дата:** 8 марта 2026

---

## 📋 Обзор

Справочник проблем (`core/problems_dict.py`) — централизованное определение всех типов проблем, которые могут быть обнаружены в задачах Jira.

**Цели:**
- Устранить дублирование кода проверок
- Централизованное управление типами проблем
- Согласованность названий по всему проекту
- Простое добавление новых типов проблем

---

## 📖 Структура справочника

### PROBLEM_TYPES

Словарь из 7 типов проблем:

```python
PROBLEM_TYPES = {
    'NO_ASSIGNEE': {
        'id': 'no_assignee',
        'short_name': 'Без исполнителя',
        'description': 'Задача не назначена на конкретного исполнителя',
        'category': 'assignee',
        'severity': 'high',
        'check_function': 'check_no_assignee',
        'filter_name': 'Без исполнителя',
        'icon': '👤',
        'color': '#e53935',
        'jql_condition': 'assignee is EMPTY',
    },
    # ... ещё 6 типов
}
```

### Поля типа проблемы

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | str | Уникальный идентификатор (snake_case) |
| `short_name` | str | Короткое название для отображения |
| `description` | str | Подробное описание проблемы |
| `category` | str | Категория для группировки |
| `severity` | str | Важность: high, medium, low |
| `check_function` | str | Имя функции проверки |
| `filter_name` | str | Название для фильтра в UI |
| `icon` | str | Иконка (эмодзи) |
| `color` | str | HEX цвет для UI |
| `jql_condition` | str | JQL условие для поиска |
| `threshold_days` | int | (опционально) Порог дней |

---

## 🔍 Типы проблем

### 1. NO_ASSIGNEE — Без исполнителя

- **ID:** `no_assignee`
- **Категория:** assignee
- **Важность:** high
- **Цвет:** 🔴 #e53935
- **Проверка:** `check_no_assignee(issue)`
- **JQL:** `assignee is EMPTY`

### 2. NO_TIME_SPENT — Нет фактического времени

- **ID:** `no_time_spent`
- **Категория:** time
- **Важность:** medium
- **Цвет:** 🔵 #1e88e5
- **Проверка:** `check_no_time_spent(issue)`
- **JQL:** `timespent is EMPTY OR timespent = 0`

### 3. NO_RESOLUTION_DATE — Нет даты решения

- **ID:** `no_resolution_date`
- **Категория:** time
- **Важность:** medium
- **Цвет:** 🌊 #3498db
- **Проверка:** `check_no_resolution_date(issue)`
- **JQL:** `resolutiondate is EMPTY`

### 4. INCORRECT_STATUS — Некорректный статус

- **ID:** `incorrect_status`
- **Категория:** status
- **Важность:** high
- **Цвет:** 🟣 #8e24aa
- **Проверка:** `check_incorrect_status(issue, closed_status_ids)`
- **JQL:** `status in (Closed, Done) AND resolution is EMPTY`

### 5. OVERDUE — Просрочена

- **ID:** `overdue`
- **Категория:** deadline
- **Важность:** high
- **Цвет:** 🟠 #fb8c00
- **Проверка:** `check_overdue(issue)`
- **JQL:** `duedate < now() AND status not in (Closed, Done)`

### 6. LATE_CREATION — Создана позже дедлайна

- **ID:** `late_creation`
- **Категория:** deadline
- **Важность:** medium
- **Цвет:** 🟠 #fb8c00 (группируется с просроченными)
- **Проверка:** `check_late_creation(issue, threshold_days=7)`
- **JQL:** `created > duedate`
- **Порог:** 7 дней

### 7. INACTIVE — Не двигается

- **ID:** `inactive`
- **Категория:** activity
- **Важность:** medium
- **Цвет:** 🟡 #fbc02d
- **Проверка:** `check_inactive(issue, threshold_days=5)`
- **JQL:** `updated < -5d AND status not in (Closed, Done)`
- **Порог:** 5 дней

---

## 🛠️ Использование

### Импорт

```python
from core.problems_dict import (
    PROBLEM_TYPES,
    get_problem_type_by_id,
    get_problem_type_by_name,
    get_problems_by_category,
    get_problems_by_severity,
    get_filter_names,
    check_no_assignee,
    check_overdue,
    # ... другие функции
)
```

### Примеры

#### 1. Получение информации о проблеме

```python
# По ID
problem = get_problem_type_by_id('no_assignee')
print(problem['short_name'])  # 'Без исполнителя'
print(problem['color'])       # '#e53935'

# По названию
problem = get_problem_type_by_name('Просрочена')
print(problem['severity'])    # 'high'
```

#### 2. Фильтрация по категории

```python
# Все проблемы дедлайна
deadline_problems = get_problems_by_category('deadline')
# [OVERDUE, LATE_CREATION]

# Все проблемы высокой важности
high_severity = get_problems_by_severity('high')
# [NO_ASSIGNEE, INCORRECT_STATUS, OVERDUE]
```

#### 3. Проверка задачи

```python
from core.jira_report import validate_issue

# Получение списка проблем задачи
problems = validate_issue(issue, jira, closed_status_ids)

# problems = ['Без исполнителя', 'Просрочена']
```

#### 4. Использование в UI

```python
# Получить все имена для фильтра
filters = get_filter_names()
# ['Без исполнителя', 'Просрочена', 'Нет фактического', ...]

# Получить категории для группировки
categories = get_problem_categories()
# {'assignee': 'Проблемы с исполнителем', ...}
```

---

## 📊 Категории проблем

| Категория | Описание | Проблемы |
|-----------|----------|----------|
| `assignee` | Проблемы с исполнителем | NO_ASSIGNEE |
| `time` | Проблемы со временем | NO_TIME_SPENT, NO_RESOLUTION_DATE |
| `status` | Проблемы со статусом | INCORRECT_STATUS |
| `deadline` | Проблемы с дедлайном | OVERDUE, LATE_CREATION |
| `activity` | Проблемы с активностью | INACTIVE |

---

## 🎨 Уровни важности

| Уровень | Описание | Проблемы |
|---------|----------|----------|
| `high` | Критичные, требуют немедленного внимания | NO_ASSIGNEE, INCORRECT_STATUS, OVERDUE |
| `medium` | Средние, желательно исправить | NO_TIME_SPENT, NO_RESOLUTION_DATE, LATE_CREATION, INACTIVE |
| `low` | Незначительные | (пока нет) |

---

## 🔧 Интеграция в коде

### core/jira_report.py

Функция `validate_issue()` использует справочник:

```python
from core.problems_dict import (
    check_no_assignee,
    check_no_time_spent,
    check_overdue,
    PROBLEM_TYPES,
)

def validate_issue(issue, jira, closed_status_ids):
    problems = []
    
    # Проверка через функцию справочника
    if check_no_assignee(issue):
        problems.append(PROBLEM_TYPES['NO_ASSIGNEE']['short_name'])
    
    if check_overdue(issue):
        problems.append(PROBLEM_TYPES['OVERDUE']['short_name'])
    
    return problems
```

### templates/index.html

UI использует названия из справочника:

```javascript
// Фильтры проблем
const filters = [
    'Без исполнителя',  // PROBLEM_TYPES['NO_ASSIGNEE']['filter_name']
    'Просрочена',       // PROBLEM_TYPES['OVERDUE']['filter_name']
    'Нет фактического', // PROBLEM_TYPES['NO_TIME_SPENT']['filter_name']
];
```

---

## ➕ Добавление новой проблемы

### Шаг 1: Добавить в справочник

```python
# core/problems_dict.py

PROBLEM_TYPES['NEW_PROBLEM'] = {
    'id': 'new_problem',
    'short_name': 'Новая проблема',
    'description': 'Описание проблемы',
    'category': 'time',  # или другая категория
    'severity': 'medium',
    'check_function': 'check_new_problem',
    'filter_name': 'Новая проблема',
    'icon': '🆕',
    'color': '#ff0000',
    'jql_condition': 'custom_field is EMPTY',
}
```

### Шаг 2: Создать функцию проверки

```python
# core/problems_dict.py

def check_new_problem(issue: Any) -> bool:
    """Проверка: новая проблема."""
    # Логика проверки
    return not hasattr(issue.fields, 'custom_field')
```

### Шаг 3: Экспортировать функцию

```python
# core/problems_dict.py

__all__ = [
    # ...
    'check_new_problem',
]
```

### Шаг 4: Использовать в validate_issue()

```python
# core/jira_report.py

from core.problems_dict import check_new_problem, PROBLEM_TYPES

def validate_issue(issue, jira, closed_status_ids):
    problems = []
    
    if check_new_problem(issue):
        problems.append(PROBLEM_TYPES['NEW_PROBLEM']['short_name'])
    
    return problems
```

---

## 🧪 Тестирование

### Пример теста

```python
# tests/test_report.py

from core.problems_dict import PROBLEM_TYPES, check_no_assignee

def test_no_assignee():
    mock_issue = Mock()
    mock_issue.fields.assignee = None
    
    assert check_no_assignee(mock_issue) == True
    
def test_validate_issue_integration():
    from core.jira_report import validate_issue
    
    mock_issue = create_mock_issue(assignee=None)
    problems = validate_issue(mock_issue)
    
    assert PROBLEM_TYPES['NO_ASSIGNEE']['short_name'] in problems
```

---

## 📈 Метрики

| Метрика | Значение |
|---------|----------|
| **Всего типов проблем** | 7 |
| **Категорий** | 5 |
| **Уровней важности** | 2 (high, medium) |
| **Функций проверки** | 7 |
| **Вспомогательных функций** | 6 |

---

## 📝 Changelog

### Версия 1.0 (8 марта 2026)

- ✅ Создан справочник проблем
- ✅ 7 типов проблем
- ✅ 7 функций проверки
- ✅ Интеграция в `core/jira_report.py`
- ✅ UI фильтры с счётчиками
- ✅ Группировка на диаграмме

---

## 📞 Поддержка

По вопросам добавления новых типов проблем обращайтесь к разработчику или создавайте Issue на GitHub.
