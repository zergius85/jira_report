# -*- coding: utf-8 -*-
"""
Сервис валидации задач Jira.

Инкапсулирует логику проверки задач на корректность.
"""
from typing import List, Optional, Any, Dict
import logging

from core.problems_dict import (
    check_no_assignee,
    check_no_time_spent,
    check_no_resolution_date,
    check_overdue,
    check_late_creation,
    check_inactive,
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
            problems.append(self._format_late_creation(issue))
        
        # Проверка: просрочена
        if check_overdue(issue):
            problems.append(PROBLEM_TYPES['OVERDUE']['short_name'])
        
        # Проверка: неактивна
        if self._check_inactive(issue):
            problems.append(self._format_inactive(issue))
        
        # Проверка статуса "Закрыт"
        if self._check_status(issue):
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
    
    def _format_late_creation(self, issue: Any) -> str:
        """Форматировать проблему просрочки планирования."""
        try:
            created_date = datetime.strptime(issue.fields.created[:10], '%Y-%m-%d')
            due_date = datetime.strptime(issue.fields.duedate[:10], '%Y-%m-%d')
            days_diff = (created_date - due_date).days
            return f"Создана на {days_diff} дн. позже даты решения"
        except Exception:
            return PROBLEM_TYPES['LATE_CREATION']['short_name']
    
    def _check_inactive(self, issue: Any) -> bool:
        """Проверка: неактивна."""
        threshold = PROBLEM_TYPES['INACTIVE'].get(
            'threshold_days',
            RISK_ZONE_INACTIVITY_THRESHOLD
        )
        return check_inactive(issue, threshold)
    
    def _format_inactive(self, issue: Any) -> str:
        """Форматировать проблему неактивности."""
        try:
            updated = datetime.strptime(issue.fields.updated[:19], '%Y-%m-%dT%H:%M:%S')
            days_inactive = (datetime.now() - updated).days
            return f"Не двигается {days_inactive} дн."
        except Exception:
            return PROBLEM_TYPES['INACTIVE']['short_name']
    
    def _check_status(self, issue: Any) -> bool:
        """
        Проверка статуса "Закрыт".
        
        Returns:
            bool: True если статус "Закрыт" установлен некорректно
        """
        if not hasattr(issue.fields, 'status') or not issue.fields.status:
            return False
        
        status_id = issue.fields.status.id
        status_name = issue.fields.status.name
        
        # Проверяем только если статус "Закрыт"
        if not is_status_closed(status_name=status_name, status_id=status_id):
            return False
        
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
                return False
        
        # Проверяем changelog
        return self._check_changelog(issue)
    
    def _check_changelog(self, issue: Any) -> bool:
        """
        Проверить changelog задачи.
        
        Returns:
            bool: True если changelog некорректен
        """
        try:
            # Проверяем наличие changelog
            if hasattr(issue, 'changelog') and issue.changelog:
                for history in reversed(issue.changelog.histories):
                    for item in history.items:
                        if item.field == 'status' and item.toString:
                            if hasattr(item, 'to') and item.to in self.closed_status_ids:
                                # Проверяем автора перехода
                                author_name = ''
                                if hasattr(history, 'author') and history.author:
                                    author_name = (
                                        history.author.name
                                        if hasattr(history.author, 'name')
                                        else history.author.displayName
                                    )
                                    author_name = author_name or ''
                                
                                # Если переход сделал бот — это корректно
                                if JIRA_USER and JIRA_USER.lower() in author_name.lower():
                                    return False
                
                # Changelog есть, но корректного перехода не найдено
                return True
            else:
                # Changelog отсутствует
                logger.warning(f"⚠️  Отсутствует changelog для {issue.key}")
                return True
        except Exception as e:
            logger.warning(f"⚠️  Ошибка при проверке changelog для {issue.key}: {e}")
            return True


# Импорт datetime
from datetime import datetime
