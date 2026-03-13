# -*- coding: utf-8 -*-
"""
Тесты для IssueFetcher.

Тестируются:
- fetch_issues_split_by_duedate()
- Разделение задач на с duedate и без
- Фильтрация по периоду created
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from dateutil.relativedelta import relativedelta

from core.services.issue_fetcher import IssueFetcher


class MockIssue:
    """Моки для задач Jira."""
    
    def __init__(self, key, project_key, has_duedate=True, duedate=None, created=None):
        self.key = key
        self.fields = Mock()
        self.fields.project = Mock()
        self.fields.project.key = project_key
        
        if has_duedate and duedate:
            self.fields.duedate = duedate
        else:
            self.fields.duedate = None
            
        self.fields.created = created or datetime.now().strftime('%Y-%m-%d')


class TestIssueFetcherSplitByDuedate:
    """Тесты для метода fetch_issues_split_by_duedate()."""

    @patch('core.services.issue_fetcher.get_jira_connection')
    @patch('core.services.issue_fetcher.fetch_issues_via_rest')
    @patch('core.services.issue_fetcher.get_metadata_cache')
    def test_split_returns_dict_with_keys(self, mock_cache, mock_fetch, mock_jira):
        """Метод возвращает dict с ключами 'with_duedate' и 'without_duedate'."""
        # Настраиваем моки
        mock_jira_instance = Mock()
        mock_jira.return_value = mock_jira_instance
        
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache_instance.set = Mock()
        mock_cache.return_value = mock_cache_instance
        
        # Возвращаем пустой список задач
        mock_fetch.return_value = []
        
        fetcher = IssueFetcher(
            project_keys=['TEST'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            days=30
        )
        fetcher.jira = mock_jira_instance
        fetcher.projects_map = {'TEST': 'Test Project'}
        
        result = fetcher.fetch_issues_split_by_duedate()
        
        assert isinstance(result, dict)
        assert 'with_duedate' in result
        assert 'without_duedate' in result
        assert isinstance(result['with_duedate'], list)
        assert isinstance(result['without_duedate'], list)

    @patch('core.services.issue_fetcher.get_jira_connection')
    @patch('core.services.issue_fetcher.fetch_issues_via_rest')
    @patch('core.services.issue_fetcher.get_metadata_cache')
    def test_split_separates_issues(self, mock_cache, mock_fetch, mock_jira):
        """Метод корректно разделяет задачи с duedate и без."""
        # Настраиваем моки
        mock_jira_instance = Mock()
        mock_jira.return_value = mock_jira_instance
        
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache_instance.set = Mock()
        mock_cache.return_value = mock_cache_instance
        
        # Создаём тестовые задачи
        issue_with_duedate = Mock()
        issue_with_duedate.fields = Mock()
        issue_with_duedate.fields.duedate = '2024-01-15'
        issue_with_duedate.fields.project = Mock()
        issue_with_duedate.fields.project.key = 'TEST'
        
        issue_without_duedate = Mock()
        issue_without_duedate.fields = Mock()
        issue_without_duedate.fields.duedate = None
        issue_without_duedate.fields.project = Mock()
        issue_without_duedate.fields.project.key = 'TEST'
        
        mock_fetch.return_value = [issue_with_duedate, issue_without_duedate]
        
        fetcher = IssueFetcher(
            project_keys=['TEST'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            days=30
        )
        fetcher.jira = mock_jira_instance
        fetcher.projects_map = {'TEST': 'Test Project'}
        
        result = fetcher.fetch_issues_split_by_duedate()
        
        # Проверяем разделение
        assert len(result['with_duedate']) == 1
        assert len(result['without_duedate']) == 1
        assert result['with_duedate'][0] == issue_with_duedate
        assert result['without_duedate'][0] == issue_without_duedate

    @patch('core.services.issue_fetcher.get_jira_connection')
    @patch('core.services.issue_fetcher.fetch_issues_via_rest')
    @patch('core.services.issue_fetcher.get_metadata_cache')
    def test_with_duedate_contains_only_with_duedate(self, mock_cache, mock_fetch, mock_jira):
        """with_duedate содержит только задачи с duedate."""
        mock_jira_instance = Mock()
        mock_jira.return_value = mock_jira_instance
        
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache_instance.set = Mock()
        mock_cache.return_value = mock_cache_instance
        
        # Создаём混合 задачи
        issues = []
        for i in range(5):
            issue = Mock()
            issue.fields = Mock()
            issue.fields.project = Mock()
            issue.fields.project.key = 'TEST'
            
            if i % 2 == 0:
                issue.fields.duedate = f'2024-01-{10+i}'
            else:
                issue.fields.duedate = None
            
            issues.append(issue)
        
        mock_fetch.return_value = issues
        
        fetcher = IssueFetcher(
            project_keys=['TEST'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            days=30
        )
        fetcher.jira = mock_jira_instance
        fetcher.projects_map = {'TEST': 'Test Project'}
        
        result = fetcher.fetch_issues_split_by_duedate()
        
        # Проверяем, что все задачи в with_duedate имеют duedate
        for issue in result['with_duedate']:
            assert issue.fields.duedate is not None
        
        # Проверяем, что все задачи в without_duedate не имеют duedate
        for issue in result['without_duedate']:
            assert issue.fields.duedate is None
        
        # Проверяем общее количество
        assert len(result['with_duedate']) + len(result['without_duedate']) == 5

    @patch('core.services.issue_fetcher.get_jira_connection')
    @patch('core.services.issue_fetcher.fetch_issues_via_rest')
    @patch('core.services.issue_fetcher.get_metadata_cache')
    def test_fetch_issues_called_with_created(self, mock_cache, mock_fetch, mock_jira):
        """Метод использует fetch_issues с date_field='created'."""
        mock_jira_instance = Mock()
        mock_jira.return_value = mock_jira_instance
        
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache_instance.set = Mock()
        mock_cache.return_value = mock_cache_instance
        
        mock_fetch.return_value = []
        
        fetcher = IssueFetcher(
            project_keys=['TEST'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            days=30
        )
        fetcher.jira = mock_jira_instance
        fetcher.projects_map = {'TEST': 'Test Project'}
        
        # Сохраняем оригинальный метод
        original_fetch = fetcher.fetch_issues
        fetch_issues_called = False
        
        def mock_fetch_issues(date_field='created'):
            nonlocal fetch_issues_called
            fetch_issues_called = True
            assert date_field == 'created'
            return []
        
        fetcher.fetch_issues = mock_fetch_issues
        
        result = fetcher.fetch_issues_split_by_duedate()
        
        assert fetch_issues_called is True

    @patch('core.services.issue_fetcher.get_jira_connection')
    @patch('core.services.issue_fetcher.fetch_issues_via_rest')
    @patch('core.services.issue_fetcher.get_metadata_cache')
    def test_empty_issues_return_empty_lists(self, mock_cache, mock_fetch, mock_jira):
        """При отсутствии задач возвращаются пустые списки."""
        mock_jira_instance = Mock()
        mock_jira.return_value = mock_jira_instance
        
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache_instance.set = Mock()
        mock_cache.return_value = mock_cache_instance
        
        mock_fetch.return_value = []
        
        fetcher = IssueFetcher(
            project_keys=['TEST'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            days=30
        )
        fetcher.jira = mock_jira_instance
        fetcher.projects_map = {'TEST': 'Test Project'}
        
        result = fetcher.fetch_issues_split_by_duedate()
        
        assert result['with_duedate'] == []
        assert result['without_duedate'] == []


class TestIssueFetcherDateHandling:
    """Тесты для обработки дат в IssueFetcher."""

    def test_issues_end_date_calculated_with_2_months(self):
        """issues_end_obj рассчитывается как end_date + 2 месяца."""
        fetcher = IssueFetcher(
            project_keys=['TEST'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            days=30
        )
        
        # end_date = 2024-01-31
        # issues_end = end_date + 2 месяца = 2024-03-31
        expected_end = datetime(2024, 1, 31)
        expected_issues_end = datetime(2024, 3, 31)
        
        assert fetcher.end_date_obj == expected_end
        assert fetcher.issues_end_obj == expected_issues_end

    def test_issues_end_date_with_days_parameter(self):
        """issues_end_obj рассчитывается при использовании days."""
        fetcher = IssueFetcher(
            project_keys=['TEST'],
            start_date='2024-01-01',
            days=30
        )
        
        # start_date = 2024-01-01
        # end_date = start_date + 30 - 1 = 2024-01-30
        # issues_end = start_date + 30 дней + 2 месяца
        expected_issues_end = datetime(2024, 1, 1) + timedelta(days=30) + relativedelta(months=2)
        
        assert fetcher.issues_end_obj == expected_issues_end
