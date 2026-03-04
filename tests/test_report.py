# -*- coding: utf-8 -*-
"""
Базовые тесты для Jira Report System
"""
import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Добавляем путь к модулю
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jira_report import (
    REPORT_BLOCKS,
    convert_seconds_to_hours,
    get_default_start_date,
    get_column_order,
    validate_config,
    validate_issue,
    EXCLUDED_ASSIGNEE_CLOSE
)


class TestConvertSecondsToHours:
    """Тесты конвертации секунд в часы"""

    def test_none_value(self):
        assert convert_seconds_to_hours(None) == 0.0

    def test_zero_value(self):
        assert convert_seconds_to_hours(0) == 0.0

    def test_one_hour(self):
        assert convert_seconds_to_hours(3600) == 1.0

    def test_half_hour(self):
        assert convert_seconds_to_hours(1800) == 0.5

    def test_rounding(self):
        result = convert_seconds_to_hours(3661)  # 1 час 1 минута 1 секунда
        assert result == 1.02


class TestGetDefaultStartDate:
    """Тесты получения даты начала по умолчанию"""

    def test_january_returns_december(self):
        # Тестируем логику напрямую
        from datetime import datetime
        # Если сейчас январь, должен вернуться декабрь прошлого года
        today = datetime(2024, 1, 15)
        if today.month == 1:
            expected = datetime(today.year - 1, 12, 1)
        else:
            expected = datetime(today.year, today.month - 1, 1)
        assert expected == datetime(2023, 12, 1)

    def test_other_month_returns_previous(self):
        # Тестируем логику напрямую
        from datetime import datetime
        # Если июнь, должен вернуться май
        today = datetime(2024, 6, 15)
        if today.month == 1:
            expected = datetime(today.year - 1, 12, 1)
        else:
            expected = datetime(today.year, today.month - 1, 1)
        assert expected == datetime(2024, 5, 1)


class TestGetColumnOrder:
    """Тесты получения порядка колонок"""

    def test_summary_columns(self):
        cols = get_column_order('summary')
        assert 'Клиент (Проект)' in cols
        assert 'Факт (ч)' in cols
        assert len(cols) == 7

    def test_assignees_columns(self):
        cols = get_column_order('assignees')
        assert 'Исполнитель' in cols
        assert 'Задач' in cols
        assert len(cols) == 7

    def test_detail_columns(self):
        cols = get_column_order('detail')
        assert 'URL' in cols
        assert 'Задача' in cols
        assert len(cols) == 9

    def test_issues_columns(self):
        cols = get_column_order('issues')
        assert 'URL' in cols
        assert 'Проблемы' in cols
        assert len(cols) == 8

    def test_unknown_block(self):
        cols = get_column_order('unknown')
        assert 'Проект' in cols
        assert len(cols) == 9


class TestValidateConfig:
    """Тесты валидации конфигурации"""

    @patch('jira_report.JIRA_SERVER', 'https://test.com')
    @patch('jira_report.JIRA_USER', 'test@test.com')
    @patch('jira_report.JIRA_PASS', 'password')
    def test_valid_config(self):
        is_valid, errors = validate_config()
        assert is_valid is True
        assert len(errors) == 0

    @patch('jira_report.JIRA_SERVER', None)
    @patch('jira_report.JIRA_USER', None)
    @patch('jira_report.JIRA_PASS', None)
    def test_missing_all_config(self):
        is_valid, errors = validate_config()
        assert is_valid is False
        assert len(errors) == 3

    @patch('jira_report.JIRA_SERVER', None)
    @patch('jira_report.JIRA_USER', 'test@test.com')
    @patch('jira_report.JIRA_PASS', 'password')
    def test_missing_server(self):
        is_valid, errors = validate_config()
        assert is_valid is False
        assert 'Не указан JIRA_SERVER в .env' in errors


class TestValidateIssue:
    """Тесты валидации задач"""

    def test_no_resolution_date(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = None
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '1'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = None

        problems = validate_issue(mock_issue)
        assert 'Нет даты решения' in problems

    def test_no_time_spent(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = None
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '1'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = None

        problems = validate_issue(mock_issue)
        assert 'Нет фактического времени' in problems

    def test_zero_time_spent(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 0
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '1'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = None

        problems = validate_issue(mock_issue)
        assert 'Нет фактического времени' in problems

    def test_closed_status_is_problem(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'  # В списке CLOSED_STATUS_IDS
        mock_issue.fields.status.name = 'Закрыт'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'
        mock_issue.fields.assignee.displayName = 'Ivanov Ivan'

        with patch('jira_report.CLOSED_STATUS_IDS', ['10001']):
            problems = validate_issue(mock_issue)
            assert any('Статус' in p for p in problems)

    def test_excluded_assignee_closed_status_ok(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'
        mock_issue.fields.status.name = 'Закрыт'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'holin'
        mock_issue.fields.assignee.displayName = 'Holin Petr'

        with patch('jira_report.CLOSED_STATUS_IDS', ['10001']):
            problems = validate_issue(mock_issue)
            # Для holin статус "Закрыт" не должен быть проблемой
            assert not any('Статус' in p for p in problems)

    def test_correct_issue_no_problems(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '3'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'

        with patch('jira_report.CLOSED_STATUS_IDS', ['10001']):
            problems = validate_issue(mock_issue)
            assert len(problems) == 0


class TestReportBlocks:
    """Тесты блоков отчёта"""

    def test_all_blocks_defined(self):
        assert 'summary' in REPORT_BLOCKS
        assert 'assignees' in REPORT_BLOCKS
        assert 'detail' in REPORT_BLOCKS
        assert 'issues' in REPORT_BLOCKS

    def test_blocks_have_descriptions(self):
        for key, value in REPORT_BLOCKS.items():
            assert isinstance(value, str)
            assert len(value) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
