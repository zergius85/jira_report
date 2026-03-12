# 🧪 Запуск тестов Jira Report System

**Версия:** 1.0  
**Дата:** 8 марта 2026

---

## 📋 Требования

- Python 3.7.3+
- pytest 7.0.0+
- Все зависимости из requirements.txt

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
# Активировать виртуальное окружение
source venv/bin/activate  # Linux
venv\Scripts\activate     # Windows

# Установить зависимости
pip install -r requirements.txt
```

### 2. Запуск всех тестов

```bash
# Базовый запуск
python -m pytest tests/ -v

# С покрытием кода
python -m pytest tests/ -v --cov=core --cov-report=html

# Только тесты справочника проблем
python -m pytest tests/test_report.py::TestProblemsDict -v

# Только тесты валидации
python -m pytest tests/test_report.py::TestValidateIssue -v
```

---

## 📊 Структура тестов

### tests/test_report.py

| Класс тестов | Описание | Кол-во |
|--------------|----------|--------|
| **TestConvertSecondsToHours** | Конвертация секунд в часы | 5 |
| **TestGetDefaultStartDate** | Дата начала по умолчанию | 2 |
| **TestGetColumnOrder** | Порядок колонок | 8 |
| **TestValidateIssue** | Валидация задач | 15+ |
| **TestProblemsDict** | Справочник проблем | 8 |
| **TestJQLBuilder** | Построение JQL | 14 |
| **TestSanitizeJqlIdentifier** | Санитизация JQL | 5 |
| **TestSearchAllIssues** | Пагинация поиска | 3 |

**Всего:** 60+ тестов

---

## 🧪 Тесты справочника проблем

### Запуск

```bash
python -m pytest tests/test_report.py::TestProblemsDict -v
```

### Ожидаемый вывод

```
tests/test_report.py::TestProblemsDict::test_problem_types_exists PASSED
tests/test_report.py::TestProblemsDict::test_problem_type_structure PASSED
tests/test_report.py::TestProblemsDict::test_problem_categories PASSED
tests/test_report.py::TestProblemsDict::test_get_problems_by_category PASSED
tests/test_report.py::TestProblemsDict::test_get_problems_by_severity PASSED
tests/test_report.py::TestProblemsDict::test_get_filter_names PASSED
tests/test_report.py::TestProblemsDict::test_problem_colors PASSED
tests/test_report.py::TestProblemsDict::test_problem_icons PASSED

==================== 8 passed in 0.15s ====================
```

### Описание тестов

#### test_problem_types_exists
Проверяет, что справочник содержит 7 типов проблем.

#### test_problem_type_structure
Проверяет структуру каждого типа проблемы:
- id, short_name, description
- category, severity
- check_function, filter_name
- icon, color

#### test_problem_categories
Проверяет 5 категорий:
- assignee, time, status, deadline, activity

#### test_get_problems_by_category
Фильтрация по категориям:
- deadline: 2 проблемы (OVERDUE, LATE_CREATION)
- assignee: 1 проблема (NO_ASSIGNEE)

#### test_get_problems_by_severity
Фильтрация по важности:
- high: ≥3 критичных
- medium: ≥3 средних

#### test_get_filter_names
Проверяет имена для UI фильтров.

#### test_problem_colors
Проверяет HEX цвета проблем.

#### test_problem_icons
Проверяет иконки (эмодзи).

---

## 🧪 Тесты валидации задач

### Запуск

```bash
python -m pytest tests/test_report.py::TestValidateIssue -v
```

### Ожидаемый вывод

```
tests/test_report.py::TestValidateIssue::test_no_assignee PASSED
tests/test_report.py::TestValidateIssue::test_has_assignee PASSED
tests/test_report.py::TestValidateIssue::test_no_resolution_date PASSED
tests/test_report.py::TestValidateIssue::test_no_time_spent PASSED
tests/test_report.py::TestValidateIssue::test_zero_time_spent PASSED
tests/test_report.py::TestValidateIssue::test_check_no_time_spent_function PASSED
tests/test_report.py::TestValidateIssue::test_check_no_resolution_date_function PASSED
tests/test_report.py::TestValidateIssue::test_check_overdue PASSED
tests/test_report.py::TestValidateIssue::test_check_late_creation PASSED
tests/test_report.py::TestValidateIssue::test_check_inactive PASSED
tests/test_report.py::TestValidateIssue::test_closed_status_without_changelog_is_problem PASSED
tests/test_report.py::TestValidateIssue::test_excluded_assignee_closed_status_ok PASSED
tests/test_report.py::TestValidateIssue::test_closed_by_jira_user_is_ok PASSED

==================== 13 passed in 0.25s ====================
```

---

## 🔧 Отладка тестов

### Запуск одного теста

```bash
python -m pytest tests/test_report.py::TestProblemsDict::test_problem_colors -v
```

### Запуск с выводом логов

```bash
python -m pytest tests/test_report.py -v -s
```

### Запуск с coverage

```bash
# Установить плагин
pip install pytest-cov

# Запустить с покрытием
python -m pytest tests/ --cov=core --cov-report=html

# Открыть отчёт
# Linux: firefox htmlcov/index.html
# Windows: start htmlcov\index.html
```

### Запуск с таймингами

```bash
python -m pytest tests/ -v --durations=10
```

---

## 📊 Покрытие кода

### Текущее покрытие

| Модуль | Покрытие |
|--------|----------|
| **core/problems_dict.py** | 95% |
| **core/jira_report.py** | 75% |
| **core/jql_builder.py** | 90% |
| **core/report_service.py** | 60% |
| **web/app.py** | 40% |

### Целевое покрытие

- **Критичные модули:** ≥90%
- **Основной код:** ≥75%
- **UI/API:** ≥50%

---

## 🐛 Частые проблемы

### Ошибка: ModuleNotFoundError

```bash
# Убедитесь, что активировано venv
source venv/bin/activate

# Проверьте путь
export PYTHONPATH=/path/to/jira_report:$PYTHONPATH
```

### Ошибка: ImportError (SQLAlchemy)

```bash
# Установите зависимости
pip install -r requirements.txt
```

### Ошибка: pytest не найден

```bash
# Установите pytest
pip install pytest pytest-cov
```

### Тесты падают на Windows

```bash
# Проблема с кодировкой
# Установите PYTHONUTF8=1
set PYTHONUTF8=1

# Или используйте UTF-8 в коде
# -*- coding: utf-8 -*-
```

---

## 📝 Добавление новых тестов

### Шаблон теста

```python
# tests/test_report.py

class TestNewFeature:
    """Тесты новой функции"""

    def test_something(self):
        """Описание теста"""
        # Arrange
        mock_object = Mock()
        mock_object.field = 'value'
        
        # Act
        result = function_under_test(mock_object)
        
        # Assert
        assert result == expected_value
```

### Запуск нового теста

```bash
python -m pytest tests/test_report.py::TestNewFeature::test_something -v
```

---

## 🎯 CI/CD интеграция

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.7
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run tests
        run: pytest tests/ -v --cov=core
```

### Локальная проверка перед коммитом

```bash
# Запустить все тесты
pytest tests/ -v

# Проверить стиль
flake8 core/ web/ tests/

# Проверить типы (если используется mypy)
mypy core/
```

---

## 📊 Статистика тестов

| Метрика | Значение |
|---------|----------|
| **Всего тестов** | 60+ |
| **Проходит** | 100% |
| **Время выполнения** | < 5 сек |
| **Покрытие** | 75%+ |
| **Критичные модули** | 90%+ |

---

## 📞 Поддержка

По вопросам тестирования обращайтесь к разработчику или создавайте Issues на GitHub.

**GitHub:** https://github.com/zergius85/jira_report/issues
