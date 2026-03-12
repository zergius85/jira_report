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

# Подробные описания проблем для tooltip
PROBLEM_DESCRIPTIONS = {
    'Без исполнителя': 'Задача не назначена на конкретного исполнителя (assignee = null)',
    'Нет фактического времени': 'Не указано фактическое время выполнения (timespent = null или 0)',
    'Нет даты решения': 'Задача закрыта, но не указана дата решения (resolutiondate = null)',
    'Некорректный статус': 'Задача в статусе "Закрыт", но закрыта некорректно (не тем пользователем)',
    'Просрочена': 'Дата решения истекла, но задача не закрыта (duedate < сегодня AND status NOT IN (Closed, Done))',
    'Создана позже даты решения': 'Задача создана позже планового срока исполнения (created > duedate)',
    'Не двигается': 'Задача не обновлялась более 5 дней (updated < сегодня - 5 дней AND status NOT IN (Closed, Done))',
}

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
        'detail_template': 'Просрочена на {days_overdue} дн.',  # Шаблон для детального сообщения
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
        'detail_template': 'Создана на {days_diff} дн. позже даты решения',  # Шаблон для детального сообщения
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
        'detail_template': 'Не двигается {days_inactive} дн.',  # Шаблон для детального сообщения
    },

    # =============================================
    # Проблемы с проверкой истории (changelog)
    # =============================================
    'CHANGELOG_CHECK_FAILED': {
        'id': 'changelog_check_failed',
        'short_name': 'Не удалось проверить историю переходов',
        'description': 'Не удалось получить или проверить историю переходов в статусе "Закрыт"',
        'category': 'status',
        'severity': 'high',
        'check_function': 'check_changelog',
        'filter_name': 'История переходов',
        'icon': '⚠️',
        'color': '#f44336',  # Красный
        'jql_condition': 'status in (Closed, Done) AND changelog is EMPTY',
        'help_text': 'Задача в статусе "Закрыт", но невозможно определить кто её закрыл. Возможно задача была закрыта давно и история переходов не сохранилась.',
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

    # Используем сервис для проверки закрытого статуса
    from core.services.closed_status_service import is_status_closed

    status_name = issue.fields.status.name
    status_id = issue.fields.status.id
    
    if is_status_closed(status_name=status_name, status_id=status_id):
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

def format_problem(problem_key: str, **kwargs) -> str:
    """
    Форматирует сообщение проблемы с подстановкой значений.

    Если в PROBLEM_TYPES есть 'detail_template', использует его,
    иначе возвращает short_name.

    Args:
        problem_key: Ключ проблемы (например, 'OVERDUE')
        **kwargs: Параметры для подстановки в шаблон (days_overdue, days_diff, и т.д.)

    Returns:
        str: Отформатированное сообщение проблемы

    Пример:
        format_problem('OVERDUE', days_overdue=5) -> "Просрочена на 5 дн."
    """
    problem = PROBLEM_TYPES.get(problem_key)
    if not problem:
        return problem_key

    template = problem.get('detail_template')
    if template:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            # Если шаблон не удалось заполнить, возвращаем short_name
            return problem['short_name']
    else:
        return problem['short_name']


def check_changelog(
    issue: Any,
    closed_status_ids: List[str],
    excluded_assignees: List[str],
    jira_user: str
) -> tuple:
    """
    Проверяет корректность закрытия задачи по changelog.

    Логика:
    - Статус "Готово" [10001] — всегда OK, независимо от кто закрыл
    - Статус "Закрыт" [6] — должен закрыть пользователь из EXCLUDED_ASSIGNEE_CLOSE (holin)

    Args:
        issue: Задача Jira
        closed_status_ids: Список ID закрытых статусов
        excluded_assignees: Список имён исполнителей-исключений (кто может закрывать)
        jira_user: Имя пользователя-бота (не используется в текущей логике)

    Returns:
        tuple: (is_correct, error_message)
            - is_correct: True если закрытие корректно
            - error_message: Сообщение об ошибке или None
    """
    # Проверяем, что задача в закрытом статусе
    if not hasattr(issue.fields, 'status') or not issue.fields.status:
        return (True, None)  # Нет статуса — не проверяем

    status_id = issue.fields.status.id
    if status_id not in closed_status_ids:
        return (True, None)  # Статус не закрытый — не проверяем

    # Проверяем, не является ли исполнитель исключением
    # Если исполнитель в списке исключений — задача закрыта корректно
    assignee_name = ''
    if issue.fields.assignee:
        assignee_name = (
            issue.fields.assignee.name
            if hasattr(issue.fields.assignee, 'name')
            else issue.fields.assignee.displayName
        )
        assignee_name = assignee_name or ''

    for exc in excluded_assignees:
        if exc.lower() in assignee_name.lower():
            return (True, None)  # Исполнитель в исключениях — ок

    # Проверяем changelog — ищем кто перевёл задачу в закрытый статус
    try:
        if hasattr(issue, 'changelog') and issue.changelog:
            # Ищем последний переход в закрытый статус
            for history in reversed(issue.changelog.histories):
                for item in history.items:
                    if item.field == 'status' and hasattr(item, 'to'):
                        if item.to in closed_status_ids:
                            # Нашли переход в закрытый статус — проверяем автора
                            author_name = ''
                            if hasattr(history, 'author') and history.author:
                                author_name = (
                                    history.author.name
                                    if hasattr(history.author, 'name')
                                    else history.author.displayName
                                )
                                author_name = author_name or ''

                            # Проверяем, кто закрыл задачу
                            for exc in excluded_assignees:
                                if exc.lower() in author_name.lower():
                                    return (True, None)  # Закрыл пользователь из исключений — ок

                            # Закрыл кто-то другой — это ошибка
                            return (False, None)

            # Не нашли переход в закрытый статус в changelog
            return (False, PROBLEM_TYPES['CHANGELOG_CHECK_FAILED']['short_name'])
        else:
            # Changelog отсутствует — не можем проверить кто закрыл
            return (False, PROBLEM_TYPES['CHANGELOG_CHECK_FAILED']['short_name'])

    except Exception as e:
        # Если не удалось получить changelog
        logger.debug(f"Ошибка при проверке changelog: {e}")
        return (False, PROBLEM_TYPES['CHANGELOG_CHECK_FAILED']['short_name'])


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


def get_problem_description(problem_name: str) -> str:
    """
    Получить подробное описание проблемы для tooltip.

    Args:
        problem_name: Короткое название проблемы (например, 'Без исполнителя')

    Returns:
        str: Подробное описание или исходное название если не найдено
    """
    return PROBLEM_DESCRIPTIONS.get(problem_name, problem_name)


# =============================================
# ЭКСПОРТ
# =============================================

__all__ = [
    'PROBLEM_TYPES',
    'PROBLEM_DESCRIPTIONS',
    'get_problem_type_by_id',
    'get_problem_type_by_name',
    'get_problems_by_category',
    'get_problems_by_severity',
    'get_filter_names',
    'get_problem_categories',
    'get_problem_description',
    'format_problem',
    'check_changelog',
    'check_no_assignee',
    'check_no_time_spent',
    'check_no_resolution_date',
    'check_incorrect_status',
    'check_overdue',
    'check_late_creation',
    'check_inactive',
]
