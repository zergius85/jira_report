# -*- coding: utf-8 -*-
"""
Справочник типов проблем для задач Jira.

Централизованное определение всех типов проблем, которые могут быть обнаружены
в задачах. Используется для валидации, отчётности и фильтрации.

Использование:
    from core.problems_dict import PROBLEM_TYPES, get_problem_type, check_problem
    
    # Проверка типа проблемы
    if problem_type == PROBLEM_TYPES['NO_ASSIGNEE']['id']:
        ...
    
    # Получение всех проблем для задачи
    problems = validate_issue(issue)
"""

from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from core.config import EXCLUDED_ASSIGNEE_CLOSE, JIRA_USER


# =============================================
# ТИПЫ ПРОБЛЕМ
# =============================================

PROBLEM_TYPES: Dict[str, Dict[str, Any]] = {
    # =============================================
    # Проблемы с исполнителем
    # =============================================
    'NO_ASSIGNEE': {
        'id': 'no_assignee',
        'short_name': 'Без исполнителя',
        'description': 'Задача не назначена на конкретного исполнителя',
        'category': 'assignee',  # Категория для группировки
        'severity': 'high',  # high, medium, low
        'check_function': 'check_no_assignee',
        'filter_name': 'Без исполнителя',  # Для фильтра в UI
        'icon': '👤',
        'color': '#e53935',  # Красный
        'jql_condition': 'assignee is EMPTY',
    },
    
    # =============================================
    # Проблемы со временем
    # =============================================
    'NO_TIME_SPENT': {
        'id': 'no_time_spent',
        'short_name': 'Нет фактического времени',
        'description': 'Не указано фактическое время выполнения (Time Spent)',
        'category': 'time',
        'severity': 'medium',
        'check_function': 'check_no_time_spent',
        'filter_name': 'Нет фактического',
        'icon': '⏱️',
        'color': '#1e88e5',  # Синий
        'jql_condition': 'timespent is EMPTY OR timespent = 0',
    },
    
    'NO_RESOLUTION_DATE': {
        'id': 'no_resolution_date',
        'short_name': 'Нет даты решения',
        'description': 'Задача закрыта, но не указана дата решения',
        'category': 'time',
        'severity': 'medium',
        'check_function': 'check_no_resolution_date',
        'filter_name': 'Нет даты решения',
        'icon': '📅',
        'color': '#3498db',  # Голубой
        'jql_condition': 'resolutiondate is EMPTY',
    },
    
    # =============================================
    # Проблемы со статусом
    # =============================================
    'INCORRECT_STATUS': {
        'id': 'incorrect_status',
        'short_name': 'Некорректный статус',
        'description': 'Задача в статусе "Закрыт", но закрыта некорректно',
        'category': 'status',
        'severity': 'high',
        'check_function': 'check_incorrect_status',
        'filter_name': 'Статус',
        'icon': '❌',
        'color': '#8e24aa',  # Фиолетовый
        'jql_condition': 'status in (Closed, Done) AND resolution is EMPTY',
    },
    
    # =============================================
    # Проблемы с датой решения
    # =============================================
    'OVERDUE': {
        'id': 'overdue',
        'short_name': 'Просрочена',
        'description': 'Дата решения истекла, но задача не закрыта',
        'category': 'deadline',
        'severity': 'high',
        'check_function': 'check_overdue',
        'filter_name': 'Просрочена',
        'icon': '⏰',
        'color': '#fb8c00',  # Оранжевый
        'jql_condition': 'duedate < now() AND status not in (Closed, Done)',
    },

    'LATE_CREATION': {
        'id': 'late_creation',
        'short_name': 'Создана позже даты решения',
        'description': 'Задача создана позже планового срока исполнения',
        'category': 'deadline',
        'severity': 'medium',
        'check_function': 'check_late_creation',
        'filter_name': 'Просрочена',  # Группируем с просроченными
        'icon': '⏰',
        'color': '#fb8c00',  # Оранжевый (как у просроченных)
        'jql_condition': 'created > duedate',
        'threshold_days': 7,  # Минимальное количество дней для проблемы
    },
    
    # =============================================
    # Проблемы с активностью
    # =============================================
    'INACTIVE': {
        'id': 'inactive',
        'short_name': 'Не двигается',
        'description': 'Задача не обновлялась более порога неактивности',
        'category': 'activity',
        'severity': 'medium',
        'check_function': 'check_inactive',
        'filter_name': 'Не двигается',
        'icon': '😴',
        'color': '#fbc02d',  # Жёлтый
        'jql_condition': 'updated < -5d AND status not in (Closed, Done)',
        'threshold_days': 5,  # Порог неактивности (дни)
    },
}


# =============================================
# ФУНКЦИИ ПРОВЕРКИ
# =============================================

def check_no_assignee(issue: Any) -> bool:
    """Проверка: нет исполнителя."""
    return not hasattr(issue.fields, 'assignee') or not issue.fields.assignee


def check_no_time_spent(issue: Any) -> bool:
    """Проверка: нет фактического времени."""
    return (not hasattr(issue.fields, 'timespent') or 
            issue.fields.timespent is None or 
            issue.fields.timespent == 0)


def check_no_resolution_date(issue: Any) -> bool:
    """Проверка: нет даты решения."""
    return (not hasattr(issue.fields, 'resolutiondate') or 
            not issue.fields.resolutiondate)


def check_incorrect_status(issue: Any, closed_status_ids: List[str]) -> bool:
    """
    Проверка: некорректный статус "Закрыт".
    
    Args:
        issue: Задача Jira
        closed_status_ids: Список ID закрытых статусов
    
    Returns:
        bool: True если статус некорректен
    """
    if not hasattr(issue.fields, 'status') or not issue.fields.status:
        return False
    
    status_id = issue.fields.status.id
    if status_id not in closed_status_ids:
        return False

    # Проверяем, не является ли исполнитель исключением
    assignee_name = ''
    if issue.fields.assignee:
        assignee_name = issue.fields.assignee.name if hasattr(issue.fields.assignee, 'name') else issue.fields.assignee.displayName

    for exc in EXCLUDED_ASSIGNEE_CLOSE:
        if exc.lower() in assignee_name.lower():
            return False
    
    # Проверяем changelog
    try:
        if hasattr(issue, 'changelog') and issue.changelog:
            for history in reversed(issue.changelog.histories):
                for item in history.items:
                    if item.field == 'status' and hasattr(item, 'to'):
                        if item.to in closed_status_ids:
                            author_name = ''
                            if hasattr(history, 'author') and history.author:
                                author_name = history.author.name if hasattr(history.author, 'name') else history.author.displayName
                            
                            if JIRA_USER and JIRA_USER.lower() in author_name.lower():
                                return False
                            break
    except Exception:
        pass
    
    return True


def check_overdue(issue: Any) -> bool:
    """Проверка: просрочена (дата решения истекла)."""
    if not hasattr(issue.fields, 'duedate') or not issue.fields.duedate:
        return False
    
    if not hasattr(issue.fields, 'status') or not issue.fields.status:
        return False
    
    status_name = issue.fields.status.name.lower()
    if status_name in ['закрыт', 'closed', 'done']:
        return False
    
    try:
        due_date = datetime.strptime(issue.fields.duedate[:10], '%Y-%m-%d')
        return due_date < datetime.now()
    except Exception:
        return False


def check_late_creation(issue: Any, threshold_days: int = 7) -> bool:
    """
    Проверка: создана позже даты решения.

    Args:
        issue: Задача Jira
        threshold_days: Минимальное количество дней просрочки

    Returns:
        bool: True если создана позже даты решения на threshold_days+ дней
    """
    if (not hasattr(issue.fields, 'created') or not issue.fields.created or
        not hasattr(issue.fields, 'duedate') or not issue.fields.duedate):
        return False
    
    try:
        created_date = datetime.strptime(issue.fields.created[:10], '%Y-%m-%d')
        due_date = datetime.strptime(issue.fields.duedate[:10], '%Y-%m-%d')
        days_diff = (created_date - due_date).days
        return days_diff >= threshold_days
    except Exception:
        return False


def check_inactive(issue: Any, threshold_days: int = 5) -> bool:
    """
    Проверка: задача не двигается.
    
    Args:
        issue: Задача Jira
        threshold_days: Порог неактивности (дни)
    
    Returns:
        bool: True если задача не обновлялась более threshold_days
    """
    if not hasattr(issue.fields, 'updated') or not issue.fields.updated:
        return False
    
    if not hasattr(issue.fields, 'status') or not issue.fields.status:
        return False
    
    status_name = issue.fields.status.name.lower()
    if status_name in ['закрыт', 'closed', 'done']:
        return False
    
    try:
        updated = datetime.strptime(issue.fields.updated[:19], '%Y-%m-%dT%H:%M:%S')
        days_inactive = (datetime.now() - updated).days
        return days_inactive > threshold_days
    except Exception:
        return False


# =============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================

def get_problem_type_by_id(problem_id: str) -> Optional[Dict[str, Any]]:
    """
    Получить тип проблемы по ID.
    
    Args:
        problem_id: ID проблемы (например, 'no_assignee')
    
    Returns:
        Dict: Информация о проблеме или None
    """
    for key, value in PROBLEM_TYPES.items():
        if value['id'] == problem_id:
            return value
    return None


def get_problem_type_by_name(problem_name: str) -> Optional[Dict[str, Any]]:
    """
    Получить тип проблемы по имени (короткому названию).
    
    Args:
        problem_name: Короткое название (например, 'Без исполнителя')
    
    Returns:
        Dict: Информация о проблеме или None
    """
    for key, value in PROBLEM_TYPES.items():
        if value['short_name'] == problem_name:
            return value
    return None


def get_problems_by_category(category: str) -> List[Dict[str, Any]]:
    """
    Получить проблемы по категории.
    
    Args:
        category: Категория (assignee, time, status, deadline, activity)
    
    Returns:
        List[Dict]: Список проблем категории
    """
    return [v for v in PROBLEM_TYPES.values() if v.get('category') == category]


def get_problems_by_severity(severity: str) -> List[Dict[str, Any]]:
    """
    Получить проблемы по уровню важности.
    
    Args:
        severity: Уровень (high, medium, low)
    
    Returns:
        List[Dict]: Список проблем уровня
    """
    return [v for v in PROBLEM_TYPES.values() if v.get('severity') == severity]


def get_filter_names() -> List[str]:
    """
    Получить список всех имён для фильтрации.
    
    Returns:
        List[str]: Уникальные имена фильтров
    """
    return list(set(v['filter_name'] for v in PROBLEM_TYPES.values()))


def get_problem_categories() -> Dict[str, str]:
    """
    Получить категории проблем с описаниями.

    Returns:
        Dict: Категория → описание
    """
    return {
        'assignee': 'Проблемы с исполнителем',
        'time': 'Проблемы со временем',
        'status': 'Проблемы со статусом',
        'deadline': 'Проблемы с датой решения',
        'activity': 'Проблемы с активностью',
    }


# =============================================
# ЭКСПОРТ
# =============================================

__all__ = [
    'PROBLEM_TYPES',
    'get_problem_type_by_id',
    'get_problem_type_by_name',
    'get_problems_by_category',
    'get_problems_by_severity',
    'get_filter_names',
    'get_problem_categories',
    'check_no_assignee',
    'check_no_time_spent',
    'check_no_resolution_date',
    'check_incorrect_status',
    'check_overdue',
    'check_late_creation',
    'check_inactive',
]
