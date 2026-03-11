# -*- coding: utf-8 -*-
"""
Оркестратор генерации отчётов.

Координирует работу всех сервисов для генерации отчёта.
"""
from typing import List, Dict, Any, Optional
import logging

import pandas as pd

from core.services.issue_fetcher import IssueFetcher
from core.services.issue_validator import IssueValidator
from core.services.report_aggregator import ReportAggregator
from core.services import is_status_closed
from core.formatters import VerboseFormatter
from core.config import CLOSED_STATUS_IDS, EXCLUDED_PROJECTS
from core.jira_report import get_closed_status_ids, convert_seconds_to_hours
from core.dtos import IssueDTO

logger = logging.getLogger(__name__)


class ReportOrchestrator:
    """
    Оркестратор для генерации отчётов.
    
    Координирует работу:
    - IssueFetcher (получение данных)
    - IssueValidator (валидация)
    - ReportAggregator (агрегация)
    """
    
    def __init__(
        self,
        project_keys: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
        assignee_filter: Optional[List[str]] = None,
        issue_types: Optional[List[str]] = None,
        blocks: Optional[List[str]] = None,
        extra_verbose: bool = False,
        include_risk_zone: bool = True
    ):
        """
        Инициализация оркестратора.
        
        Args:
            project_keys: Список проектов
            start_date: Дата начала
            end_date: Дата окончания
            days: Количество дней
            assignee_filter: Фильтр по исполнителям
            issue_types: Фильтр по типам задач
            blocks: Блоки отчёта
            extra_verbose: Показывать ID
            include_risk_zone: Включать Risk Zone
        """
        self.blocks = blocks
        self.extra_verbose = extra_verbose
        self.include_risk_zone = include_risk_zone
        
        # Инициализация сервисов
        self.fetcher = IssueFetcher(
            project_keys=project_keys,
            start_date=start_date,
            end_date=end_date,
            days=days,
            assignee_filter=assignee_filter,
            issue_types=issue_types
        )
        
        closed_status_ids = CLOSED_STATUS_IDS
        if not closed_status_ids or closed_status_ids[0] == '':
            closed_status_ids = get_closed_status_ids()
        
        self.validator = IssueValidator(
            closed_status_ids=closed_status_ids
        )
        
        self.aggregator = ReportAggregator(extra_verbose=extra_verbose)
        self.formatter = VerboseFormatter(extra_verbose=extra_verbose)
        
        # Данные
        self.projects_map: Dict[str, str] = {}
        self.issues_data: List[Dict[str, Any]] = []
    
    def generate(self) -> Dict[str, Any]:
        """
        Сгенерировать отчёт.
        
        Returns:
            Dict[str, Any]: Данные отчёта
        """
        # 1. Проверка доступности Jira
        from core.jira_report import check_jira_availability
        jira_available, error_msg = check_jira_availability()
        if not jira_available:
            raise ConnectionError(f"Jira недоступна: {error_msg}")
        
        # 2. Получение проектов
        self.projects_map = self.fetcher.get_projects()
        
        # 3. Получение задач
        issues_normal = self.fetcher.fetch_issues(date_field='duedate')
        issues_all = self.fetcher.fetch_issues(date_field='created')
        
        # 4. Обработка задач
        self.issues_data = self._process_issues(issues_normal, issues_all)
        
        # 5. Агрегация
        summary_data = self.aggregator.aggregate_by_projects(
            self.issues_data, self.projects_map
        )
        assignees_data = self.aggregator.aggregate_by_assignees(self.issues_data)
        problem_issues = self.aggregator.collect_problem_issues(self.issues_data)
        
        # 6. Формирование DataFrame
        df_summary = pd.DataFrame(summary_data) if summary_data else pd.DataFrame()
        df_assignees = pd.DataFrame(assignees_data) if assignees_data else pd.DataFrame()
        df_detail = pd.DataFrame([i['detail'] for i in self.issues_data]) if self.issues_data else pd.DataFrame()
        df_issues = pd.DataFrame(problem_issues) if problem_issues else pd.DataFrame()
        
        # 7. Сортировка
        if not df_detail.empty:
            df_detail = df_detail.sort_values(
                by=['Тип', 'Проект', 'Дата решения'],
                ascending=[True, True, True]
            )
        
        # 8. Risk Zone
        df_risk = pd.DataFrame()
        if self.include_risk_zone and 'risk_zone' in (self.blocks or []):
            risk_data = self._generate_risk_zone(issues_normal)
            if risk_data:
                df_risk = pd.DataFrame(risk_data)
                df_risk = df_risk.sort_values('Приоритет', ascending=False)
        
        # 9. Формирование результата
        result = {
            'period': f"{self.fetcher.start_date_str} — {self.fetcher.end_date_str}",
            'blocks': self.blocks or [],
            'total_projects': len(df_summary),
            'total_tasks': len(df_detail),
            'total_correct': len(df_detail[df_detail['Проблемы'] == '']) if not df_detail.empty else 0,
            'total_issues': len(df_issues),
            'total_spent': df_summary['Факт (ч)'].sum() if not df_summary.empty else 0,
            'total_estimated': df_summary['Оценка (ч)'].sum() if not df_summary.empty else 0,
        }
        
        # Добавляем блоки
        if 'summary' in (self.blocks or []):
            result['summary'] = df_summary
        if 'assignees' in (self.blocks or []):
            result['assignees'] = df_assignees
        if 'detail' in (self.blocks or []):
            result['detail'] = df_detail
        if 'issues' in (self.blocks or []):
            result['issues'] = df_issues
        if 'risk_zone' in (self.blocks or []):
            result['risk_zone'] = df_risk
        
        return result
    
    def _process_issues(
        self,
        issues_normal: List[Dict],
        issues_all: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Обработать задачи.
        
        Args:
            issues_normal: Задачи для detail/summary
            issues_all: Все задачи для проблемных
            
        Returns:
            List[Dict]: Обработанные задачи
        """
        result = []
        
        for issue_data in issues_normal:
            processed = self._process_single_issue(issue_data)
            result.append(processed)
        
        return result
    
    def _process_single_issue(self, issue_data: Dict) -> Dict[str, Any]:
        """
        Обработать одну задачу.
        
        Args:
            issue_data: Данные задачи из REST API
            
        Returns:
            Dict: Обработанные данные
        """
        fields = issue_data.get('fields', {})
        proj_key = fields.get('project', {}).get('key', '')
        
        # DTO для валидации
        issue_dto = IssueDTO.from_dict(issue_data)
        problems = self.validator.validate(issue_dto, project_key=proj_key)
        
        # Данные
        spent = convert_seconds_to_hours(fields.get('timespent'))
        estimated = convert_seconds_to_hours(fields.get('timeoriginalestimate'))
        
        status = fields.get('status', {})
        status_id = status.get('id', '')
        status_name = status.get('name', '-')
        status_category = status.get('statusCategory', {}).get('key', '-')
        
        assignee = fields.get('assignee', {})
        assignee_name = assignee.get('displayName', 'Без исполнителя') if assignee else 'Без исполнителя'
        assignee_id = assignee.get('accountId', '')
        
        # Форматирование
        base_url = f"{self.fetcher.jira.server}/browse/{issue_data.get('key', '')}"
        url = self.formatter.format_url(base_url)
        
        detail_data = {
            'URL': url,
            'Проект': fields.get('project', {}).get('name', proj_key),
            'Ключ': issue_data.get('key', ''),
            'Тип': fields.get('issuetype', {}).get('name', 'Задача'),
            'Задача': fields.get('summary', ''),
            'Исполнитель': assignee_name,
            'Статус': f"{status_name} ({status_category})",
            'Дата создания': fields.get('created', '-')[:10] if fields.get('created') else '-',
            'Дата исполнения': fields.get('duedate', '-')[:10] if fields.get('duedate') else '-',
            'Дата решения': fields.get('resolutiondate', '-')[:10] if fields.get('resolutiondate') else '-',
            'Факт (ч)': spent,
            'Оценка (ч)': estimated,
            'Проблемы': ', '.join(problems) if problems else ''
        }
        
        # Применяем форматирование extra_verbose
        if self.extra_verbose:
            detail_data = self.formatter.format_issue_data(
                detail_data,
                extra_data={
                    'project_id': fields.get('project', {}).get('id', ''),
                    'status_id': status_id,
                    'type_id': fields.get('issuetype', {}).get('id', ''),
                    'assignee_id': assignee_id,
                    'created': fields.get('created', ''),
                    'duedate': fields.get('duedate', ''),
                    'resolutiondate': fields.get('resolutiondate', ''),
                }
            )
        
        return {
            'detail': detail_data,
            'project_key': proj_key,
            'project_id': fields.get('project', {}).get('id', ''),
            'spent': spent,
            'estimated': estimated,
            'problems': problems,
            'assignee': assignee_name,
            'creator': fields.get('creator', {}).get('displayName', 'N/A'),
            'url': base_url,
            'key': issue_data.get('key', ''),
            'summary': fields.get('summary', ''),
            'created': fields.get('created', '-')[:10] if fields.get('created') else '-',
            'duedate': fields.get('duedate', '-')[:10] if fields.get('duedate') else '-',
        }
    
    def _generate_risk_zone(self, issues: List[Dict]) -> List[Dict]:
        """
        Сгенерировать Risk Zone.
        
        Args:
            issues: Список задач
            
        Returns:
            List[Dict]: Рисковые задачи
        """
        from datetime import datetime
        from core.config import RISK_ZONE_INACTIVITY_THRESHOLD
        
        risk_issues = []
        today = datetime.now()
        
        for issue_data in issues:
            fields = issue_data.get('fields', {})
            status = fields.get('status', {})
            status_id = status.get('id', '')
            status_name = status.get('name', '')
            
            risk_factors = []
            
            # 1. Без исполнителя
            if not fields.get('assignee'):
                risk_factors.append('Без исполнителя')
            
            # 2. Просрочена
            duedate = fields.get('duedate')
            if duedate:
                due_date = datetime.strptime(duedate[:10], '%Y-%m-%d')
                if due_date < today and not is_status_closed(status_name=status_name, status_id=status_id):
                    days_overdue = (today - due_date).days
                    risk_factors.append(f'Просрочена на {days_overdue} дн.')
            
            # 3. Не двигается
            updated = fields.get('updated')
            if updated:
                updated_dt = datetime.strptime(updated[:19], '%Y-%m-%dT%H:%M:%S')
                days_inactive = (today - updated_dt).days
                if days_inactive > RISK_ZONE_INACTIVITY_THRESHOLD and not is_status_closed(status_name=status_name, status_id=status_id):
                    risk_factors.append(f'Не двигается {days_inactive} дн.')
            
            if risk_factors:
                assignee = fields.get('assignee', {})
                priority = fields.get('priority', {})
                
                row = {
                    'URL': self.formatter.format_url(f"{self.fetcher.jira.server}/browse/{issue_data.get('key', '')}"),
                    'Ключ': issue_data.get('key', ''),
                    'Задача': fields.get('summary', ''),
                    'Исполнитель': assignee.get('displayName', 'Без исполнителя') if assignee else 'Без исполнителя',
                    'Статус': status_name,
                    'Факторы риска': '; '.join(risk_factors),
                    'Приоритет': priority.get('name', 'Normal') if priority else 'Normal'
                }
                risk_issues.append(row)
        
        return risk_issues
