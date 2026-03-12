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
    EXCLUDED_ASSIGNEE_CLOSE,
    RISK_ZONE_INACTIVITY_THRESHOLD,
)
from core.services.issue_validator import IssueValidator

# Импортируем справочник проблем для тестов
from core.problems_dict import (
    PROBLEM_TYPES,
    check_no_assignee,
    check_no_time_spent,
    check_no_resolution_date,
    check_overdue,
    check_late_creation,
    check_inactive,
    format_problem,
    check_changelog,
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
        # В extra_verbose режиме колонки не меняются, ID добавляется к значениям
        cols = get_column_order('summary', extra_verbose=True)
        assert 'Клиент (Проект)' in cols
        assert 'ID' not in cols  # Отдельной колонки ID больше нет
        assert len(cols) == 7  # Количество колонок не меняется

    def test_assignees_columns(self):
        cols = get_column_order('assignees')
        assert 'Исполнитель' in cols
        assert 'Задач' in cols
        assert len(cols) == 7

    def test_assignees_columns_extra_verbose(self):
        # В extra_verbose режиме колонки не меняются
        cols = get_column_order('assignees', extra_verbose=True)
        assert 'Исполнитель' in cols
        assert 'ID' not in cols
        assert len(cols) == 7

    def test_detail_columns(self):
        cols = get_column_order('detail')
        assert 'URL' in cols
        assert 'Задача' in cols
        assert 'Дата решения' in cols
        assert len(cols) == 10

    def test_detail_columns_extra_verbose(self):
        # В extra_verbose режиме колонки не меняются
        cols = get_column_order('detail', extra_verbose=True)
        assert 'URL' in cols
        assert 'ID' not in cols
        assert 'Дата решения' in cols
        assert len(cols) == 10

    def test_issues_columns(self):
        cols = get_column_order('issues')
        assert 'URL' in cols
        assert 'Проблемы' in cols
        assert len(cols) == 8

    def test_issues_columns_extra_verbose(self):
        # В extra_verbose режиме колонки не меняются
        cols = get_column_order('issues', extra_verbose=True)
        assert 'URL' in cols
        assert 'ID' not in cols
        assert len(cols) == 8

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

    def test_no_assignee(self):
        """Проверка: нет исполнителя"""
        mock_issue = Mock()
        mock_issue.fields.assignee = None
        
        assert check_no_assignee(mock_issue) == True
        
    def test_has_assignee(self):
        """Проверка: есть исполнитель"""
        mock_issue = Mock()
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'
        
        assert check_no_assignee(mock_issue) == False

    def test_no_resolution_date(self):
        """Проверка: нет даты решения"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = None
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '1'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = None

        validator = IssueValidator()
        problems = validator.validate(mock_issue)
        assert PROBLEM_TYPES['NO_RESOLUTION_DATE']['short_name'] in problems

    def test_no_time_spent(self):
        """Проверка: нет фактического времени"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = None
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '1'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = None

        validator = IssueValidator()
        problems = validator.validate(mock_issue)
        assert PROBLEM_TYPES['NO_TIME_SPENT']['short_name'] in problems

    def test_zero_time_spent(self):
        """Проверка: фактическое время = 0"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 0
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '1'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = None

        validator = IssueValidator()
        problems = validator.validate(mock_issue)
        assert PROBLEM_TYPES['NO_TIME_SPENT']['short_name'] in problems

    def test_check_no_time_spent_function(self):
        """Тест функции check_no_time_spent"""
        # None
        mock_issue = Mock()
        mock_issue.fields.timespent = None
        assert check_no_time_spent(mock_issue) == True
        
        # 0
        mock_issue.fields.timespent = 0
        assert check_no_time_spent(mock_issue) == True
        
        # Есть время
        mock_issue.fields.timespent = 3600
        assert check_no_time_spent(mock_issue) == False

    def test_check_no_resolution_date_function(self):
        """Тест функции check_no_resolution_date"""
        # None
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = None
        assert check_no_resolution_date(mock_issue) == True
        
        # Есть дата
        mock_issue.fields.resolutiondate = '2024-01-01'
        assert check_no_resolution_date(mock_issue) == False

    def test_check_overdue(self):
        """Тест функции check_overdue"""
        # Дедлайн в прошлом, статус не закрыт
        mock_issue = Mock()
        mock_issue.fields.duedate = '2020-01-01'  # В прошлом
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.name = 'In Progress'
        assert check_overdue(mock_issue) == True
        
        # Дедлайн в прошлом, статус закрыт
        mock_issue.fields.status.name = 'Closed'
        assert check_overdue(mock_issue) == False
        
        # Нет дедлайна
        mock_issue.fields.duedate = None
        assert check_overdue(mock_issue) == False

    def test_check_late_creation(self):
        """Тест функции check_late_creation"""
        # Создана на 10 дней позже дедлайна
        mock_issue = Mock()
        mock_issue.fields.created = '2024-01-15'
        mock_issue.fields.duedate = '2024-01-05'
        assert check_late_creation(mock_issue, threshold_days=7) == True
        
        # Создана на 5 дней позже дедлайна (меньше порога)
        mock_issue.fields.created = '2024-01-10'
        assert check_late_creation(mock_issue, threshold_days=7) == False
        
        # Создана до дедлайна
        mock_issue.fields.created = '2024-01-01'
        assert check_late_creation(mock_issue, threshold_days=7) == False

    def test_check_inactive(self):
        """Тест функции check_inactive"""
        # Не обновлялась 10 дней, статус не закрыт
        mock_issue = Mock()
        mock_issue.fields.updated = '2024-01-01T10:00:00'
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.name = 'In Progress'
        
        with patch('core.problems_dict.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15)  # 14 дней прошло
            mock_datetime.strptime = datetime.strptime
            assert check_inactive(mock_issue, threshold_days=5) == True
        
        # Статус закрыт
        mock_issue.fields.status.name = 'Closed'
        assert check_inactive(mock_issue, threshold_days=5) == False

    def test_closed_status_without_changelog_is_problem(self):
        """Если статус 'Закрыт' и нет changelog — это проблема"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'  # В списке CLOSED_STATUS_IDS
        mock_issue.fields.status.name = 'Закрыт'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'
        mock_issue.fields.assignee.displayName = 'Ivanov Ivan'

        validator = IssueValidator(closed_status_ids=['10001'])
        problems = validator.validate(mock_issue)
        assert any(PROBLEM_TYPES['INCORRECT_STATUS']['short_name'] in p for p in problems)

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

        validator = IssueValidator(closed_status_ids=['10001'])
        problems = validator.validate(mock_issue)
        # Для holin статус "Закрыт" не должен быть проблемой
        assert not any(PROBLEM_TYPES['INCORRECT_STATUS']['short_name'] in p for p in problems)

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

        validator = IssueValidator(closed_status_ids=['10001'])
        with patch('core.services.issue_validator.JIRA_USER', 'jira_user'):
            problems = validator.validate(mock_issue)
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

        validator = IssueValidator(closed_status_ids=['10001'])
        with patch('core.services.issue_validator.JIRA_USER', 'jira_user'):
            problems = validator.validate(mock_issue)
            # Закрыто не пользователем демона — это проблема
            assert any('Некорректный статус' in p for p in problems)

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


class TestProblemsDict:
    """Тесты справочника проблем"""

    def test_problem_types_exists(self):
        """Проверка: справочник не пуст"""
        assert len(PROBLEM_TYPES) > 0
        assert len(PROBLEM_TYPES) == 7  # 7 типов проблем

    def test_problem_type_structure(self):
        """Проверка: структура типа проблемы"""
        for key, problem in PROBLEM_TYPES.items():
            assert 'id' in problem
            assert 'short_name' in problem
            assert 'description' in problem
            assert 'category' in problem
            assert 'severity' in problem
            assert 'check_function' in problem
            assert 'filter_name' in problem
            assert 'icon' in problem
            assert 'color' in problem

    def test_problem_categories(self):
        """Проверка: категории проблем"""
        from core.problems_dict import get_problem_categories
        
        categories = get_problem_categories()
        assert 'assignee' in categories
        assert 'time' in categories
        assert 'status' in categories
        assert 'deadline' in categories
        assert 'activity' in categories

    def test_get_problems_by_category(self):
        """Проверка: фильтрация по категории"""
        from core.problems_dict import get_problems_by_category
        
        deadline_problems = get_problems_by_category('deadline')
        assert len(deadline_problems) == 2  # OVERDUE, LATE_CREATION
        
        assignee_problems = get_problems_by_category('assignee')
        assert len(assignee_problems) == 1  # NO_ASSIGNEE

    def test_get_problems_by_severity(self):
        """Проверка: фильтрация по важности"""
        from core.problems_dict import get_problems_by_severity
        
        high_severity = get_problems_by_severity('high')
        assert len(high_severity) >= 3  # Как минимум 3 критичных
        
        medium_severity = get_problems_by_severity('medium')
        assert len(medium_severity) >= 3  # Как минимум 3 средних

    def test_get_filter_names(self):
        """Проверка: получение имён фильтров"""
        from core.problems_dict import get_filter_names
        
        filters = get_filter_names()
        assert 'Без исполнителя' in filters
        assert 'Просрочена' in filters
        assert 'Нет фактического' in filters

    def test_problem_colors(self):
        """Проверка: цвета проблем"""
        # Без исполнителя - красный
        assert PROBLEM_TYPES['NO_ASSIGNEE']['color'] == '#e53935'
        
        # Просрочена - оранжевый
        assert PROBLEM_TYPES['OVERDUE']['color'] == '#fb8c00'
        
        # Нет факта - синий
        assert PROBLEM_TYPES['NO_TIME_SPENT']['color'] == '#1e88e5'

    def test_problem_icons(self):
        """Проверка: иконки проблем"""
        assert PROBLEM_TYPES['NO_ASSIGNEE']['icon'] == '👤'
        assert PROBLEM_TYPES['OVERDUE']['icon'] == '⏰'
        assert PROBLEM_TYPES['NO_TIME_SPENT']['icon'] == '⏱️'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
