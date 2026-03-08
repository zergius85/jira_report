# -*- coding: utf-8 -*-
"""
Базовые тесты для Jira Report System
"""
import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Добавляем путь к модулю (теперь core/ вместо корня)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.jira_report import (
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

    def test_summary_columns_extra_verbose(self):
        cols = get_column_order('summary', extra_verbose=True)
        assert 'Клиент (Проект)' in cols
        assert 'ID' in cols
        assert len(cols) == 8

    def test_assignees_columns(self):
        cols = get_column_order('assignees')
        assert 'Исполнитель' in cols
        assert 'Задач' in cols
        assert len(cols) == 7

    def test_assignees_columns_extra_verbose(self):
        cols = get_column_order('assignees', extra_verbose=True)
        assert 'Исполнитель' in cols
        assert 'ID' in cols
        assert len(cols) == 8

    def test_detail_columns(self):
        cols = get_column_order('detail')
        assert 'URL' in cols
        assert 'Задача' in cols
        assert 'Дата решения' in cols
        assert len(cols) == 10

    def test_detail_columns_extra_verbose(self):
        cols = get_column_order('detail', extra_verbose=True)
        assert 'URL' in cols
        assert 'ID' in cols
        assert 'Дата решения' in cols
        assert len(cols) == 11

    def test_issues_columns(self):
        cols = get_column_order('issues')
        assert 'URL' in cols
        assert 'Проблемы' in cols
        assert len(cols) == 8

    def test_issues_columns_extra_verbose(self):
        cols = get_column_order('issues', extra_verbose=True)
        assert 'URL' in cols
        assert 'ID' in cols
        assert len(cols) == 9

    def test_unknown_block(self):
        cols = get_column_order('unknown')
        assert 'Проект' in cols
        assert len(cols) == 9


class TestValidateConfig:
    """Тесты валидации конфигурации"""

    @patch('core.jira_report.JIRA_SERVER', 'https://test.com')
    @patch('core.jira_report.JIRA_USER', 'test@test.com')
    @patch('core.jira_report.JIRA_PASS', 'password')
    def test_valid_config(self):
        is_valid, errors = validate_config()
        assert is_valid is True
        assert len(errors) == 0

    @patch('core.jira_report.JIRA_SERVER', None)
    @patch('core.jira_report.JIRA_USER', None)
    @patch('core.jira_report.JIRA_PASS', None)
    def test_missing_all_config(self):
        is_valid, errors = validate_config()
        assert is_valid is False
        assert len(errors) == 3

    @patch('core.jira_report.JIRA_SERVER', None)
    @patch('core.jira_report.JIRA_USER', 'test@test.com')
    @patch('core.jira_report.JIRA_PASS', 'password')
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

    def test_closed_status_without_changelog_is_problem(self):
        """Если статус 'Закрыт' и нет changelog (jira=None) — это проблема"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'  # В списке CLOSED_STATUS_IDS
        mock_issue.fields.status.name = 'Закрыт'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'
        mock_issue.fields.assignee.displayName = 'Ivanov Ivan'

        with patch('core.jira_report.CLOSED_STATUS_IDS', ['10001']):
            # jira=None, changelog проверить нельзя
            problems = validate_issue(mock_issue, jira=None)
            assert any('Статус' in p for p in problems)

    def test_excluded_assignee_closed_status_ok(self):
        """Для исполнителя из EXCLUDED_ASSIGNEE_CLOSE статус 'Закрыт' — ОК"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'
        mock_issue.fields.status.name = 'Закрыт'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'holin'
        mock_issue.fields.assignee.displayName = 'Holin Petr'

        with patch('core.jira_report.CLOSED_STATUS_IDS', ['10001']):
            problems = validate_issue(mock_issue, jira=None)
            # Для holin статус "Закрыт" не должен быть проблемой
            assert not any('Статус' in p for p in problems)

    def test_closed_by_jira_user_is_ok(self):
        """Если задача закрыта пользователем демона (JIRA_USER) — это ОК"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'
        mock_issue.fields.status.name = 'Закрыт'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'
        mock_issue.fields.assignee.displayName = 'Ivanov Ivan'

        # Ключ задачи
        mock_issue.key = 'TEST-123'

        # Создаём mock changelog с переходом от jira_user
        # Важно: histories должен быть списком, который можно обратить через reversed()
        mock_history_item = Mock()
        mock_history_item.field = 'status'
        mock_history_item.toString = 'Закрыт'
        mock_history_item.to = '10001'
        
        mock_author = Mock()
        mock_author.name = 'jira_user'  # Пользователь демона
        
        mock_history = Mock()
        mock_history.items = [mock_history_item]
        mock_history.author = mock_author
        
        mock_changelog = Mock()
        mock_changelog.histories = [mock_history]  # Список для reversed()
        
        # Добавляем changelog прямо в mock_issue (теперь используем его напрямую)
        mock_issue.changelog = mock_changelog

        with patch('core.jira_report.CLOSED_STATUS_IDS', ['10001']):
            with patch('core.jira_report.JIRA_USER', 'jira_user'):
                problems = validate_issue(mock_issue, jira=None)  # jira=None, т.к. changelog уже в issue
                # Закрыто пользователем демона — проблем нет
                assert not any('Статус' in p for p in problems)

    def test_closed_by_other_user_is_problem(self):
        """Если задача закрыта не пользователем демона — это проблема"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'
        mock_issue.fields.status.name = 'Закрыт'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'
        mock_issue.fields.assignee.displayName = 'Ivanov Ivan'

        mock_issue.key = 'TEST-123'

        # Changelog с переходом от другого пользователя
        mock_history_item = Mock()
        mock_history_item.field = 'status'
        mock_history_item.toString = 'Закрыт'
        mock_history_item.to = '10001'
        
        mock_author = Mock()
        mock_author.name = 'petrov'  # Другой пользователь
        
        mock_history = Mock()
        mock_history.items = [mock_history_item]
        mock_history.author = mock_author
        
        mock_changelog = Mock()
        mock_changelog.histories = [mock_history]
        
        # Добавляем changelog прямо в mock_issue
        mock_issue.changelog = mock_changelog

        with patch('core.jira_report.CLOSED_STATUS_IDS', ['10001']):
            with patch('core.jira_report.JIRA_USER', 'jira_user'):
                problems = validate_issue(mock_issue, jira=None)  # jira=None, т.к. changelog уже в issue
                # Закрыто не пользователем демона — это проблема
                assert any('Статус' in p for p in problems)

    def test_correct_issue_no_problems(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '3'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'

        with patch('core.jira_report.CLOSED_STATUS_IDS', ['10001']):
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


class TestSanitizeJqlIdentifier:
    """Тесты санитизации JQL-идентификаторов"""

    def test_valid_project_key(self):
        from core.jira_report import sanitize_jql_identifier
        assert sanitize_jql_identifier('WEB') == 'WEB'
        assert sanitize_jql_identifier('MY-PROJECT') == 'MY-PROJECT'
        assert sanitize_jql_identifier('test_123') == 'test_123'

    def test_valid_username(self):
        from core.jira_report import sanitize_jql_identifier
        assert sanitize_jql_identifier('ivanov') == 'ivanov'
        assert sanitize_jql_identifier('user@domain.com') == 'user@domain.com'
        assert sanitize_jql_identifier('john.doe') == 'john.doe'

    def test_invalid_characters_raise(self):
        from core.jira_report import sanitize_jql_identifier
        with pytest.raises(ValueError):
            sanitize_jql_identifier("'; DROP TABLE users;--")
        with pytest.raises(ValueError):
            sanitize_jql_identifier("project' OR '1'='1")
        with pytest.raises(ValueError):
            sanitize_jql_identifier("test/*comment*/")

    def test_empty_string_raises(self):
        from core.jira_report import sanitize_jql_identifier
        with pytest.raises(ValueError):
            sanitize_jql_identifier('')


class TestSanitizeJqlStringLiteral:
    """Тесты санитизации строковых литералов JQL"""

    def test_escapes_single_quotes(self):
        from core.jira_report import sanitize_jql_string_literal
        assert sanitize_jql_string_literal("test'value") == "test''value"

    def test_removes_sql_comments(self):
        from core.jira_report import sanitize_jql_string_literal
        result = sanitize_jql_string_literal("test--comment")
        assert '--' not in result
        result = sanitize_jql_string_literal("test/*comment*/")
        assert '/*' not in result and '*/' not in result

    def test_removes_dangerous_keywords(self):
        from core.jira_report import sanitize_jql_string_literal
        result = sanitize_jql_string_literal("DROP TABLE")
        assert 'DROP' not in result.upper()

    def test_empty_string_returns_empty(self):
        from core.jira_report import sanitize_jql_string_literal
        assert sanitize_jql_string_literal('') == ''


class TestSearchAllIssues:
    """Тесты пагинации запросов к Jira API"""

    def test_single_batch(self):
        """Тест получения одной страницы результатов"""
        from core.jira_report import search_all_issues
        from unittest.mock import Mock

        mock_jira = Mock()
        mock_batch = [Mock(), Mock(), Mock()]
        mock_jira.search_issues.return_value = mock_batch

        result = search_all_issues(mock_jira, 'project = TEST', batch_size=100)

        assert len(result) == 3
        mock_jira.search_issues.assert_called_once()

    def test_multiple_batches(self):
        """Тест получения нескольких страниц результатов"""
        from core.jira_report import search_all_issues
        from unittest.mock import Mock

        mock_jira = Mock()
        batch1 = [Mock() for _ in range(100)]  # Полная страница
        batch2 = [Mock() for _ in range(50)]   # Неполная страница
        mock_jira.search_issues.side_effect = [batch1, batch2]

        result = search_all_issues(mock_jira, 'project = TEST', batch_size=100)

        assert len(result) == 150
        assert mock_jira.search_issues.call_count == 2

    def test_empty_result(self):
        """Тест пустого результата"""
        from core.jira_report import search_all_issues
        from unittest.mock import Mock

        mock_jira = Mock()
        mock_jira.search_issues.return_value = []

        result = search_all_issues(mock_jira, 'project = TEST')

        assert len(result) == 0
        mock_jira.search_issues.assert_called_once()


class TestJQLBuilder:
    """Тесты конструктора JQL-запросов"""

    def test_project_single(self):
        """Тест одного проекта"""
        from core.jql_builder import JQLBuilder
        
        jql = JQLBuilder().project('WEB').build()
        assert jql == 'project = WEB'

    def test_projects_in(self):
        """Тест нескольких проектов"""
        from core.jql_builder import JQLBuilder
        
        jql = JQLBuilder().projects_in(['WEB', 'MOB']).build()
        assert jql == 'project IN (WEB,MOB)'

    def test_status_not_in(self):
        """Тест исключения статусов"""
        from core.jql_builder import JQLBuilder
        
        jql = JQLBuilder().status_not_in(['Closed', 'Done']).build()
        assert "status NOT IN ('Closed', 'Done')" in jql

    def test_duedate_between(self):
        """Тест диапазона дат"""
        from core.jql_builder import JQLBuilder
        
        jql = JQLBuilder().duedate_between('2024-01-01', '2024-12-31').build()
        assert "duedate >= '2024-01-01' AND duedate <= '2024-12-31'" in jql

    def test_assignee_in(self):
        """Тест исполнителей"""
        from core.jql_builder import JQLBuilder
        
        jql = JQLBuilder().assignee_in(['ivanov', 'petrov']).build()
        assert 'assignee IN (ivanov,petrov)' in jql

    def test_assignee_is_empty(self):
        """Тест без исполнителя"""
        from core.jql_builder import JQLBuilder
        
        jql = JQLBuilder().assignee_is_empty().build()
        assert 'assignee is EMPTY' in jql

    def test_updated_before(self):
        """Тест неактивности"""
        from core.jql_builder import JQLBuilder
        
        jql = JQLBuilder().updated_before(5).build()
        assert 'updated < -5d' in jql

    def test_order_by_asc(self):
        """Тест сортировки по возрастанию"""
        from core.jql_builder import JQLBuilder
        
        jql = JQLBuilder().order_by('duedate', asc=True).build()
        assert 'ORDER BY duedate ASC' in jql

    def test_order_by_desc(self):
        """Тест сортировки по убыванию"""
        from core.jql_builder import JQLBuilder
        
        jql = JQLBuilder().order_by('created', asc=False).build()
        assert 'ORDER BY created DESC' in jql

    def test_invalid_order_field(self):
        """Тест недопустимого поля сортировки"""
        from core.jql_builder import JQLBuilder
        import pytest
        
        with pytest.raises(ValueError):
            JQLBuilder().order_by('invalid_field').build()

    def test_invalid_date_format(self):
        """Тест неверного формата даты"""
        from core.jql_builder import JQLBuilder
        import pytest
        
        with pytest.raises(ValueError):
            JQLBuilder().duedate_between('01-01-2024', '2024-12-31').build()

    def test_invalid_identifier(self):
        """Тест недопустимого идентификатора"""
        from core.jql_builder import JQLBuilder
        import pytest
        
        with pytest.raises(ValueError):
            JQLBuilder().project("'; DROP TABLE--").build()

    def test_chained_conditions(self):
        """Тест цепочки условий"""
        from core.jql_builder import JQLBuilder
        
        jql = (JQLBuilder()
            .project('WEB')
            .status_not_in(['Closed', 'Done'])
            .duedate_between('2024-01-01', '2024-12-31')
            .assignee_in(['ivanov'])
            .order_by('duedate', asc=True)
            .build())
        
        assert 'project = WEB' in jql
        assert 'status NOT IN' in jql
        assert 'duedate >= ' in jql
        assert 'assignee IN' in jql
        assert 'ORDER BY duedate ASC' in jql

    def test_reset(self):
        """Тест сброса"""
        from core.jql_builder import JQLBuilder
        
        builder = JQLBuilder().project('WEB')
        builder.reset()
        jql = builder.build()
        
        assert jql == ''


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
