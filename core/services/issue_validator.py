# -*- coding: utf-8 -*-
"""
Сервис валидации задач Jira.

Инкапсулирует логику проверки задач на корректность.
"""
from typing import List, Optional, Any, Dict
from datetime import datetime
import logging

from core.problems_dict import (
    check_no_assignee,
    check_no_time_spent,
    check_no_resolution_date,
    check_overdue,
    check_late_creation,
    check_inactive,
    check_changelog,
    format_problem,
    PROBLEM_TYPES,
)
from core.config import (
    CLOSED_STATUS_IDS,
    EXCLUDED_ASSIGNEE_CLOSE,
    EXCLUDED_PROJECTS_NO_TIMESPENT,
    RISK_ZONE_INACTIVITY_THRESHOLD,
    JIRA_USER,
)
from core.services.closed_status_service import is_status_closed

logger = logging.getLogger(__name__)


class IssueValidator:
    """
    Сервис для валидации задач Jira.
    
    Проверяет задачи на:
    - Отсутствие исполнителя
    - Отсутствие фактического времени
    - Отсутствие даты решения
    - Просрочку планирования
    - Просрочку даты решения
    - Неактивность
    - Некорректный статус "Закрыт"
    """
    
    def __init__(
        self,
        closed_status_ids: Optional[List[str]] = None,
        jira: Any = None
    ):
        """
        Инициализация валидатора.
        
        Args:
            closed_status_ids: ID закрытых статусов
            jira: Объект подключения к Jira (для проверки changelog)
        """
        self.closed_status_ids = closed_status_ids or CLOSED_STATUS_IDS
        self.jira = jira
    
    def validate(
        self,
        issue: Any,
        project_key: Optional[str] = None
    ) -> List[str]:
        """
        Проверить задачу на корректность.
        
        Args:
            issue: Объект задачи Jira
            project_key: Ключ проекта (для исключений)
            
        Returns:
            List[str]: Список проблем
        """
        problems = []
        
        # Проверка: нет исполнителя
        if check_no_assignee(issue):
            problems.append(PROBLEM_TYPES['NO_ASSIGNEE']['short_name'])
        
        # Проверка: нет фактического времени
        if check_no_time_spent(issue):
            if not project_key or project_key.upper() not in [
                p.upper() for p in EXCLUDED_PROJECTS_NO_TIMESPENT
            ]:
                problems.append(PROBLEM_TYPES['NO_TIME_SPENT']['short_name'])
        
        # Проверка: нет даты решения
        if check_no_resolution_date(issue):
            problems.append(PROBLEM_TYPES['NO_RESOLUTION_DATE']['short_name'])
        
        # Проверка: просрочка планирования
        if self._check_late_creation(issue):
            days_diff = self._get_days_diff(issue.fields.created, issue.fields.duedate)
            problems.append(format_problem('LATE_CREATION', days_diff=days_diff))

        # Проверка: просрочена
        if check_overdue(issue):
            days_overdue = self._get_days_overdue(issue.fields.duedate)
            problems.append(format_problem('OVERDUE', days_overdue=days_overdue))

        # Проверка: неактивна
        if self._check_inactive(issue):
            days_inactive = self._get_days_inactive(issue.fields.updated)
            problems.append(format_problem('INACTIVE', days_inactive=days_inactive))

        # Проверка статуса "Закрыт"
        is_correct, error_message = self._check_status(issue)
        if error_message:
            problems.append(error_message)
        elif not is_correct:
            problems.append(PROBLEM_TYPES['INCORRECT_STATUS']['short_name'])

        return problems
    
    def _check_late_creation(self, issue: Any) -> bool:
        """Проверка: создана позже даты решения."""
        if not hasattr(issue.fields, 'created') or not issue.fields.created:
            return False
        if not hasattr(issue.fields, 'duedate') or not issue.fields.duedate:
            return False

        threshold = PROBLEM_TYPES['LATE_CREATION'].get('threshold_days', 7)
        return check_late_creation(issue, threshold)

    def _get_days_diff(self, created: str, duedate: str) -> int:
        """Получить разницу в днях между created и duedate."""
        try:
            created_date = datetime.strptime(created[:10], '%Y-%m-%d')
            due_date = datetime.strptime(duedate[:10], '%Y-%m-%d')
            return (created_date - due_date).days
        except Exception:
            return 0

    def _get_days_overdue(self, duedate: str) -> int:
        """Получить количество дней просрочки."""
        try:
            due_date = datetime.strptime(duedate[:10], '%Y-%m-%d')
            return (datetime.now() - due_date).days
        except Exception:
            return 0

    def _get_days_inactive(self, updated: str) -> int:
        """Получить количество дней неактивности."""
        try:
            updated_dt = datetime.strptime(updated[:19], '%Y-%m-%dT%H:%M:%S')
            return (datetime.now() - updated_dt).days
        except Exception:
            return 0
    
    def _check_inactive(self, issue: Any) -> bool:
        """Проверка: неактивна."""
        threshold = PROBLEM_TYPES['INACTIVE'].get(
            'threshold_days',
            RISK_ZONE_INACTIVITY_THRESHOLD
        )
        return check_inactive(issue, threshold, self.closed_status_ids)
    
    def _check_status(self, issue: Any) -> tuple:
        """
        Проверка статуса "Закрыт".

        Args:
            issue: Объект задачи Jira

        Returns:
            tuple: (is_correct, error_message)
                - is_correct: True если статус корректен
                - error_message: Сообщение об ошибке или None
        """
        if not hasattr(issue.fields, 'status') or not issue.fields.status:
            return (True, None)

        status_id = issue.fields.status.id
        status_name = issue.fields.status.name

        # Проверяем только если статус "Закрыт"
        if not is_status_closed(status_name=status_name, status_id=status_id):
            return (True, None)

        # Проверяем исполнителя на исключение
        assignee_name = ''
        if issue.fields.assignee:
            assignee_name = (
                issue.fields.assignee.name
                if hasattr(issue.fields.assignee, 'name')
                else issue.fields.assignee.displayName
            )
            assignee_name = assignee_name or ''

        for exc in EXCLUDED_ASSIGNEE_CLOSE:
            if exc.lower() in assignee_name.lower():
                return (True, None)

        # Проверяем changelog через функцию из problems_dict
        is_correct, error_message = check_changelog(
            issue,
            self.closed_status_ids,
            EXCLUDED_ASSIGNEE_CLOSE,
            JIRA_USER
        )
        return (is_correct, error_message)
