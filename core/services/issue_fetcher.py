# -*- coding: utf-8 -*-
"""
Сервис получения данных из Jira.

Инкапсулирует логику запросов к Jira API.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from dateutil.relativedelta import relativedelta

from core.config import EXCLUDED_PROJECTS
from core.utils import sanitize_jql_identifier, sanitize_jql_string_literal
from core.jira_report import (
    get_jira_connection,
    search_all_issues,
    fetch_issues_via_rest,
    normalize_filter,
    get_default_start_date,
)
from core.services.cache_service import get_metadata_cache

logger = logging.getLogger(__name__)


class IssueFetcher:
    """
    Сервис для получения задач из Jira.
    
    Инкапсулирует логику:
    - Подключение к Jira
    - Формирование JQL-запросов
    - Получение проектов
    - Получение задач
    """
    
    def __init__(
        self,
        project_keys: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
        assignee_filter: Optional[List[str]] = None,
        issue_types: Optional[List[str]] = None
    ):
        """
        Инициализация fetcher'а.
        
        Args:
            project_keys: Список ключей проектов
            start_date: Дата начала (YYYY-MM-DD)
            end_date: Дата окончания (YYYY-MM-DD)
            days: Количество дней
            assignee_filter: Фильтр по исполнителям
            issue_types: Фильтр по типам задач
        """
        self.project_keys = normalize_filter(project_keys, upper=True) if project_keys else []
        self.assignee_filter = normalize_filter(assignee_filter) if assignee_filter else []
        self.issue_types = normalize_filter(issue_types) if issue_types else []
        
        # Обработка дат
        self.start_date_obj = self._parse_start_date(start_date)
        self.start_date_str = self.start_date_obj.strftime('%Y-%m-%d')
        
        self.end_date_obj, self.issues_end_obj = self._parse_dates(
            self.start_date_obj, end_date, days
        )
        self.end_date_str = self.end_date_obj.strftime('%Y-%m-%d')
        self.issues_end_str = self.issues_end_obj.strftime('%Y-%m-%d')
        
        self.jira = None
        self.projects_map: Dict[str, str] = {}
    
    def _parse_start_date(self, start_date: Optional[str]) -> datetime:
        """Разобрать дату начала."""
        if start_date:
            return datetime.strptime(start_date, '%Y-%m-%d')
        return get_default_start_date()
    
    def _parse_dates(
        self,
        start_date_obj: datetime,
        end_date: Optional[str],
        days: int
    ) -> Tuple[datetime, datetime]:
        """
        Разобрать даты.
        
        Returns:
            Tuple[datetime, datetime]: (end_date, issues_end_date)
        """
        if end_date:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            issues_end_obj = end_date_obj + relativedelta(months=2)
        elif days > 0:
            end_date_obj = start_date_obj + timedelta(days=days - 1)
            issues_end_obj = start_date_obj + timedelta(days=days) + relativedelta(months=2)
        else:
            end_date_obj = datetime.now()
            issues_end_obj = end_date_obj
        
        return end_date_obj, issues_end_obj
    
    def connect(self) -> None:
        """Подключиться к Jira."""
        self.jira = get_jira_connection()
    
    def get_projects(self) -> Dict[str, str]:
        """
        Получить список проектов.

        Returns:
            Dict[str, str]: {project_key: project_name}
        """
        if not self.jira:
            self.connect()

        # Формируем ключ кэша на основе параметров
        cache_key = f"projects:{self.start_date_str}:{self.end_date_str}:{','.join(self.project_keys) if self.project_keys else 'all'}"
        
        # Проверяем кэш
        cache = get_metadata_cache()
        cached_projects = cache.get(cache_key)
        if cached_projects is not None:
            logger.debug(f"Projects cache hit: {cache_key}")
            self.projects_map = cached_projects
            return self.projects_map
        
        logger.info("📋 Получение списка активных проектов...")

        if self.project_keys and len(self.project_keys) > 0:
            # Фильтр по выбранным проектам
            for proj_key in self.project_keys:
                try:
                    try:
                        from web.app import get_project_cached
                        proj = get_project_cached(self.jira, proj_key)
                    except ImportError:
                        proj = self.jira.project(proj_key)

                    if proj:
                        self.projects_map[proj.key] = proj.name
                except Exception:
                    logger.warning(f"Проект {proj_key} не найден")
        else:
            # Все активные проекты за период
            start_date_safe = sanitize_jql_string_literal(self.start_date_str)
            issues_end_safe = sanitize_jql_string_literal(self.issues_end_str)

            jql_all_projects = (
                f"created >= '{start_date_safe}' "
                f"AND created <= '{issues_end_safe}' "
                f"ORDER BY created DESC"
            )

            all_issues_temp = search_all_issues(
                self.jira,
                jql_all_projects,
                fields='project',
                batch_size=100
            )

            seen_projects = set()
            for issue in all_issues_temp:
                if hasattr(issue, 'fields') and issue.fields:
                    project = issue.fields.project
                    if project and project.key not in seen_projects:
                        seen_projects.add(project.key)

                        if project.key in EXCLUDED_PROJECTS:
                            continue

                        self.projects_map[project.key] = project.name

        # Сохраняем в кэш
        cache.set(cache_key, self.projects_map)
        logger.info(f"✅ Projects cached: {cache_key} ({len(self.projects_map)} projects)")

        return self.projects_map

    def _build_jql(self, date_field: str, order: str = 'ASC') -> str:
        """
        Построить JQL-запрос.
        
        Args:
            date_field: Поле даты ('duedate' или 'created')
            order: Порядок сортировки ('ASC' или 'DESC')
            
        Returns:
            str: JQL-запрос
        """
        start_date_safe = sanitize_jql_string_literal(self.start_date_str)
        end_date_safe = sanitize_jql_string_literal(
            self.issues_end_str if date_field == 'created' else self.end_date_str
        )
        
        # Проекты
        if self.project_keys:
            projects_jql = ','.join([
                sanitize_jql_identifier(p) for p in self.projects_map.keys()
            ])
            project_filter = f"project IN ({projects_jql})"
        else:
            projects_jql = ','.join([
                sanitize_jql_identifier(p) for p in self.projects_map.keys()
            ])
            project_filter = f"project IN ({projects_jql})" if projects_jql else ""
        
        # Типы задач
        issue_type_filter = ''
        if self.issue_types:
            sanitized_types = []
            for t in self.issue_types:
                try:
                    sanitized_types.append(sanitize_jql_identifier(t))
                except ValueError as e:
                    logger.warning(f"Пропущен недопустимый тип задачи '{t}': {e}")
            if sanitized_types:
                issue_type_filter = f' AND issuetype IN ({",".join(sanitized_types)})'
        
        # Исполнители
        assignee_filter_jql = ''
        if self.assignee_filter:
            sanitized_assignees = []
            for a in self.assignee_filter:
                try:
                    sanitized_assignees.append(sanitize_jql_identifier(a))
                except ValueError as e:
                    logger.warning(f"Пропущен недопустимый пользователь '{a}': {e}")
            if sanitized_assignees:
                assignee_filter_jql = f' AND assignee IN ({",".join(sanitized_assignees)})'
        
        # Формируем JQL
        if date_field == 'duedate':
            date_filter = (
                f"AND duedate >= '{start_date_safe}' "
                f"AND duedate <= '{end_date_safe}' "
                f"AND duedate is not null"
            )
        else:
            date_filter = (
                f"AND {date_field} >= '{start_date_safe}' "
                f"AND {date_field} <= '{end_date_safe}'"
            )
        
        jql = (
            f"{project_filter} "
            f"{date_filter} "
            f"{issue_type_filter}"
            f"{assignee_filter_jql} "
            f"ORDER BY {date_field} {order}"
        )
        
        return jql
    
    def fetch_issues(self, date_field: str = 'created') -> List[Dict[str, Any]]:
        """
        Получить задачи из Jira.
        
        Args:
            date_field: Поле даты для фильтрации ('duedate' или 'created')
            
        Returns:
            List[Dict]: Список задач
        """
        if not self.jira:
            self.connect()
        
        if not self.projects_map:
            self.get_projects()
        
        order = 'ASC' if date_field == 'duedate' else 'DESC'
        jql = self._build_jql(date_field, order)
        
        logger.info(f"🚀 Получение задач: {date_field}...")
        issues = fetch_issues_via_rest(self.jira, jql)
        logger.info(f"✅ Получено {len(issues)} задач")

        return issues

    def fetch_issues_split_by_duedate(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Получает задачи, созданные в [start, end+2months],
        и разделяет на две группы: с duedate и без.

        Returns:
            Dict[str, List[Dict]]: {
                'with_duedate': [...],      # для метрик и отчётов
                'without_duedate': [...]    # для вкладки Без даты
            }
        """
        # 1. Получаем ВСЕ задачи по created + 2 месяца
        all_issues = self.fetch_issues(date_field='created')

        # 2. Разделяем на группы
        with_duedate = [
            i for i in all_issues
            if hasattr(i, 'fields') and hasattr(i.fields, 'duedate') and i.fields.duedate
        ]
        without_duedate = [
            i for i in all_issues
            if not hasattr(i, 'fields') or not hasattr(i.fields, 'duedate') or not i.fields.duedate
        ]

        logger.info(f"✅ Разделение задач: {len(with_duedate)} с duedate, {len(without_duedate)} без duedate")

        return {
            'with_duedate': with_duedate,
            'without_duedate': without_duedate
        }
