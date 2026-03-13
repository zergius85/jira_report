# -*- coding: utf-8 -*-
"""
Сервис агрегации данных отчёта.

Инкапсулирует логику агрегации статистики по проектам и исполнителям.
"""
from typing import List, Dict, Any, Optional
import logging
import re
from datetime import datetime

import pandas as pd

from core.formatters import VerboseFormatter
from core.jira_report import convert_seconds_to_hours

logger = logging.getLogger(__name__)


class ReportAggregator:
    """
    Сервис для агрегации данных отчёта.

    Агрегирует:
    - Статистику по проектам
    - Статистику по исполнителям
    - Список проблемных задач
    """

    def __init__(self, extra_verbose: bool = False):
        """
        Инициализация агрегатора.

        Args:
            extra_verbose: Показывать ID объектов
        """
        self.extra_verbose = extra_verbose
        self.formatter = VerboseFormatter(extra_verbose=extra_verbose)

    @staticmethod
    def _has_duedate(issue: Dict[str, Any]) -> bool:
        """
        Проверяет наличие duedate у задачи.

        Args:
            issue: Данные задачи

        Returns:
            bool: True если есть duedate
        """
        return bool(issue.get('duedate'))

    def _filter_issues_with_duedate(
        self,
        issues_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Фильтрует задачи, оставляя только с duedate.

        Args:
            issues_data: Список задач

        Returns:
            List[Dict]: Задачи с duedate
        """
        filtered = [
            i for i in issues_data
            if self._has_duedate(i)
        ]
        logger.debug(f"Фильтрация duedate: {len(issues_data)} → {len(filtered)} задач с duedate")
        return filtered
    
    def aggregate_by_projects(
        self,
        issues_data: List[Dict[str, Any]],
        projects_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Агрегировать статистику по проектам.

        Args:
            issues_data: Список обработанных задач
            projects_map: {project_key: project_name}

        Returns:
            List[Dict]: Статистика по проектам
        """
        # Фильтруем только задачи с duedate для метрик
        issues_for_metrics = self._filter_issues_with_duedate(issues_data)
        
        project_stats: Dict[str, Dict[str, Any]] = {}

        for issue_data in issues_for_metrics:
            proj_key = issue_data.get('project_key', '')
            proj_name = projects_map.get(proj_key, proj_key)
            problems = issue_data.get('problems', [])
            spent = issue_data.get('spent', 0.0)
            estimated = issue_data.get('estimated', 0.0)

            if proj_key not in project_stats:
                project_stats[proj_key] = {
                    'name': proj_name,
                    'spent': 0.0,
                    'estimated': 0.0,
                    'correct': 0,
                    'issues': 0
                }

            if not problems:
                project_stats[proj_key]['spent'] += spent
                project_stats[proj_key]['estimated'] += estimated
                project_stats[proj_key]['correct'] += 1
            else:
                project_stats[proj_key]['issues'] += 1

        # Формируем результат
        summary_data = []
        for proj_key, stats in project_stats.items():
            if stats['correct'] > 0 or stats['issues'] > 0:
                row = self._format_summary_row(proj_key, stats, issues_for_metrics)
                summary_data.append(row)

        return summary_data
    
    def _format_summary_row(
        self,
        proj_key: str,
        stats: Dict[str, Any],
        issues_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Отформатировать строку сводки по проекту.
        
        Args:
            proj_key: Ключ проекта
            stats: Статистика проекта
            issues_data: Список задач для поиска ID проекта
            
        Returns:
            Dict: Строка сводки
        """
        # Ищем ID проекта
        proj_id = ''
        for issue in issues_data:
            if issue.get('project_key') == proj_key:
                proj_id = issue.get('project_id', '')
                break
        
        proj_name_display = stats['name']
        estimated_display = round(stats['estimated'], 2)
        spent_display = round(stats['spent'], 2)
        
        if self.extra_verbose:
            if proj_id:
                proj_name_display = f"{stats['name']} [{proj_id}]"
            estimated_display = f"{estimated_display} [timeoriginalestimate]"
            spent_display = f"{spent_display} [timespent]"
        
        return {
            'Клиент (Проект)': proj_name_display,
            'Задач закрыто': stats['correct'] + stats['issues'],
            'Корректных': stats['correct'],
            'С ошибками': stats['issues'],
            'Оценка (ч)': estimated_display,
            'Факт (ч)': spent_display,
            'Отклонение': round(stats['estimated'] - stats['spent'], 2)
        }
    
    def aggregate_by_assignees(
        self,
        issues_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Агрегировать статистику по исполнителям.

        Args:
            issues_data: Список обработанных задач

        Returns:
            List[Dict]: Статистика по исполнителям
        """
        # Фильтруем только задачи с duedate для метрик
        issues_for_metrics = self._filter_issues_with_duedate(issues_data)
        
        # Фильтруем задачи без исполнителя
        issues_with_assignee = [
            i for i in issues_for_metrics
            if 'Без исполнителя' not in i.get('assignee', '')
        ]

        if not issues_with_assignee:
            return []

        # Агрегация
        assignee_stats: Dict[str, Dict[str, Any]] = {}

        for issue_data in issues_with_assignee:
            assignee = issue_data.get('assignee', '')
            problems = issue_data.get('problems', [])
            spent = issue_data.get('spent', 0.0)
            estimated = issue_data.get('estimated', 0.0)

            if assignee not in assignee_stats:
                assignee_stats[assignee] = {
                    'tasks': 0,
                    'correct': 0,
                    'issues': 0,
                    'spent': 0.0,
                    'estimated': 0.0
                }

            assignee_stats[assignee]['tasks'] += 1
            if not problems:
                assignee_stats[assignee]['correct'] += 1
                assignee_stats[assignee]['spent'] += spent
                assignee_stats[assignee]['estimated'] += estimated
            else:
                assignee_stats[assignee]['issues'] += 1

        # Формируем результат
        assignees_data = []
        for assignee, stats in assignee_stats.items():
            row = {
                'Исполнитель': assignee,
                'Задач': stats['tasks'],
                'Корректных': stats['correct'],
                'С ошибками': stats['issues'],
                'Факт (ч)': round(stats['spent'], 2),
                'Оценка (ч)': round(stats['estimated'], 2),
                'Отклонение': round(stats['estimated'] - stats['spent'], 2)
            }
            assignees_data.append(row)

        # Сортировка по факту
        assignees_data.sort(key=lambda x: x.get('Факт (ч)', 0), reverse=True)

        # Добавляем ID для extra_verbose
        if self.extra_verbose:
            for row in assignees_data:
                assignee = row.get('Исполнитель', '')
                if '[' in assignee and ']' in assignee:
                    row_id = assignee.split('[')[-1].split(']')[0]
                    row['ID'] = row_id

        return assignees_data
    
    def collect_problem_issues(
        self,
        issues_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Собрать проблемные задачи.
        
        Args:
            issues_data: Список обработанных задач
            
        Returns:
            List[Dict]: Проблемные задачи
        """
        problem_issues = [
            i for i in issues_data
            if i.get('problems')
        ]
        
        # Формируем результат
        result = []
        for issue in problem_issues:
            row = {
                'URL': issue.get('url', ''),
                'URL_debug': f"/?debug={issue.get('key', '')}",
                'Проект': issue.get('project', ''),
                'Задача': issue.get('summary', ''),
                'Исполнитель': issue.get('assignee', ''),
                'Автор': issue.get('creator', 'N/A'),
                'Дата создания': issue.get('created', ''),
                'Дата исполнения': issue.get('duedate', ''),
                'Проблемы': ', '.join(issue.get('problems', []))
            }
            result.append(row)
        
        return result
