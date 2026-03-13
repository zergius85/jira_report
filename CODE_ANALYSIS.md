# АНАЛИЗ РЕПОЗИТОРИЯ jira_report

## СТРУКТУРА ПРОЕКТА (в целом хорошая)

```
jira_report/
    core/
        jira_report.py      (God Object — слишком большой файл)
        jql_builder.py      (Конструктор JQL — хорошо)
        problems_dict.py    (Справочник проблем)
        services/           (Сервисный слой — правильно)
            issue_fetcher.py
            issue_validator.py
            и другие
    web/
        app.py              (Flask API endpoints)
```

## НАЙДЕННЫЕ ПРОБЛЕМЫ

### 1. Дублирование кода (подтверждаю)

**Что дублируется:** Построение JQL
- Где встречается: `jql_builder.py`, `issue_fetcher.py`, `report_generator.py`
- Проблема: 3 разные реализации одной логики

**Что дублируется:** Проверка проблем
- Где встречается: `problems_dict.py` + `IssueValidator.check*()`
- Проблема: Одна и та же логика в двух местах

**Что дублируется:** Парсинг дат
- Где встречается: По всему коду `datetime.strptime(...)`
- Проблема: Нет единой утилиты, риск ошибок формата

**Что дублируется:** Санитизация
- Где встречается: Частично через `utils.py`, но не везде
- Проблема: Риск SQL/JQL-инъекций

---

### 2. Основная проблема: фильтрация по duedate + Без даты решения

**Текущая логика в `IssueFetcher._build_jql()`:**

```python
if date_field == 'duedate':
    # Исключает задачи без duedate!
    date_filter = f"AND duedate >= '{start}' AND duedate <= '{end}' AND duedate is not null"
else:  # created
    # Нет разделения на с/без duedate
    date_filter = f"AND created >= '{start}' AND created <= '{end}'"
```

**Что нужно по ТЗ:**

1. Все метрики и отчёты — ТОЛЬКО по `duedate`
2. Кнопка **Задачи без даты решения**:
   - брать период `[start, end] + 2 месяца` для `created`
   - фильтровать: `duedate is EMPTY`
   - выводить в отдельной вкладке
3. Задачи без `duedate` НЕ должны попадать в общие метрики

**Проблема:** Сейчас нет единой точки, которая:
- Получает задачи, созданные в `[start, end+2months]`
- Разделяет их на с `duedate` / без `duedate`
- Передаёт с `duedate` в метрики, а без — в отдельную вкладку

---

### 3. Архитектурные проблемы

- `jira_report.py` — около 1000+ строк, смешивает: подключение к Jira, поиск, валидацию, агрегацию, экспорт
- Нет единого интерфейса для стратегий фильтрации дат
- Обработка ошибок: местами `except Exception` без логирования контекста

---

## ЧТО СДЕЛАНО ХОРОШО

- ✅ Сервисный слой (`IssueFetcher`, `IssueValidator` и др.) — правильная декомпозиция
- ✅ Санитизация JQL-параметров через `sanitize_jql_*`
- ✅ Кэширование метаданных проектов
- ✅ Пагинация при поиске (`search_all_issues`)
- ✅ Retry-логика для подключения к Jira
- ✅ Type hints и конфигурация через `.env`

---

## ПЛАН ИСПРАВЛЕНИЙ

### Приоритет 1: Решить задачу с duedate

#### Шаг 1. Добавить метод в `IssueFetcher`:

```python
def fetch_issues_split_by_duedate(self) -> Dict[str, List]:
    """
    Получает задачи, созданные в [start, end+2months],
    и разделяет на две группы: с duedate и без.
    """
    # 1. Получаем ВСЕ задачи по created + 2 месяца
    all_issues = self.fetch_issues(date_field='created')
    
    # 2. Разделяем на группы
    with_duedate = [
        i for i in all_issues 
        if hasattr(i.fields, 'duedate') and i.fields.duedate
    ]
    without_duedate = [
        i for i in all_issues 
        if not hasattr(i.fields, 'duedate') or not i.fields.duedate
    ]
    
    return {
        'with_duedate': with_duedate,      # для метрик и отчётов
        'without_duedate': without_duedate  # для вкладки Без даты
    }
```

#### Шаг 2. Обновить `/api/no-duedate` endpoint:

```python
@app.route('/api/no-duedate', methods=['POST'])
def api_no_duedate():
    ... получение параметров ...
    
    fetcher = IssueFetcher(
        project_keys=projects,
        start_date=start_date,
        end_date=end_date,  # исходный период
        days=days,
        assignee_filter=assignees,
        issue_types=issue_types
    )
    fetcher.connect()
    
    # Используем новый метод
    result = fetcher.fetch_issues_split_by_duedate()
    
    return jsonify({
        'success': True,
        'count': len(result['without_duedate']),
        'issues': result['without_duedate']  # только задачи без duedate
    })
```

#### Шаг 3. Убедиться, что метрики считают ТОЛЬКО задачи с duedate:

В `ReportAggregator` и всех расчётах добавить фильтр:

```python
issues_for_metrics = [i for i in issues if getattr(i.fields, 'duedate', None)]
# Все расчёты (просрочка, cycle time, нагрузка) — только по issues_for_metrics
```

---

### Приоритет 2: Убрать дублирование

**Вынести всю логику JQL в `JQLBuilder`:**

Вместо трёх разных `_build_jql()`:

```python
# Для поиска всех задач
builder = JQLBuilder()
jql = (builder
    .projects_in(projects)
    .created_between(start_date, end_date_plus_2m)
    .issuetype_in(issue_types)
    .assignee_in(assignees)
    .order_by('created', asc=True)
    .build())

# Для отчётов по duedate
jql_duedate = (builder.reset()
    .projects_in(projects)
    .duedate_between(start_date, end_date)
    .add_condition("duedate is not null")  # явное условие
    .issuetype_in(issue_types)
    .assignee_in(assignees)
    .order_by('duedate', asc=True)
    .build())
```

**Создать утилиту для дат:**

```python
# core/utils.py
class DateUtils:
    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """Единая точка парсинга дат с обработкой ошибок"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str[:10], '%Y-%m-%d')
        except (ValueError, TypeError):
            logger.warning(f"Некорректный формат даты: {date_str}")
            return None
```

---

### Приоритет 3: Рефакторинг архитектуры

```
core/
    connection/
        jira_client.py      # Подключение, health-check
        retry_handler.py    # Retry-логика
    queries/
        jql_builder.py      # единственный источник JQL
        issue_queries.py    # Высокоуровневые запросы
    processing/
        issue_validator.py
        issue_enricher.py   # Добавление полей, расчёты
        date_filter_strategy.py  # новый интерфейс
    reporting/
        report_aggregator.py
        report_formatter.py
        export/
            excel_exporter.py
            pdf_exporter.py
```

**Интерфейс для стратегий фильтрации:**

```python
from abc import ABC, abstractmethod

class DateFilterStrategy(ABC):
    @abstractmethod
    def build_query(self, params: FilterParams) -> str: ...
    
    @abstractmethod
    def filter_issues(self, issues: List) -> List: ...

class DueDateFilter(DateFilterStrategy):
    """Фильтр для отчётов: только задачи с duedate"""
    ...

class CreatedDateWithSplitFilter(DateFilterStrategy):
    """Фильтр для вкладки Без даты: created + разделение"""
    ...
```

---

## ЧЕК-ЛИСТ ДЛЯ БЫСТРОГО ФИКСА

- [ ] В `IssueFetcher` добавить `fetch_issues_split_by_duedate()`
- [ ] Обновить `/api/no-duedate` использовать новый метод
- [ ] Во всех агрегаторах добавить фильтр: `if issue.fields.duedate`
- [ ] В UI добавить переключатель вкладок: С датой / Без даты
- [ ] Вынести дублирующийся JQL-код в `JQLBuilder`
- [ ] Создать `DateUtils.parse_date()` для единого парсинга
- [ ] Написать тесты для `JQLBuilder` (минимум 5 кейсов)

---

## КЛЮЧЕВОЙ ПРИНЦИП

> **Все бизнес-метрики должны рассчитываться только по задачам с duedate.**
> Задачи без даты — это отдельная категория для ручного разбора, они не должны загрязнять статистику.
