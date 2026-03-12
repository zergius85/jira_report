# -*- coding: utf-8 -*-
"""
Тесты для ReportGenerator и связанных классов
"""
import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.report_generator import (
    IssueDataExtractor,
    ReportBlockGenerator,
    ReportGenerator,
    RiskZoneAnalyzer
)


class TestIssueDataExtractor:
    """Тесты для IssueDataExtractor"""

    def setup_method(self):
        self.extractor = IssueDataExtractor(extra_verbose=False)
        self.extractor_verbose = IssueDataExtractor(extra_verbose=True)

    def test_extract_basic(self):
        mock_issue = Mock()
        mock_issue.key = 'TEST-123'
        mock_issue.id = '10001'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.timeoriginalestimate = 7200
        mock_issue.fields.issuetype.name = 'Task'
        mock_issue.fields.assignee.displayName = 'Ivanov'
        mock_issue.fields.duedate = '2024-12-31'
        mock_issue.fields.resolutiondate = '2024-12-30'
        mock_issue.fields.created = '2024-01-01'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.status.statusCategory.key = 'done'
        mock_issue.fields.summary = 'Test task'
        mock_project = Mock()
        mock_project.name = 'Test Project'
        mock_project.key = 'TEST'
        mock_issue.fields.project = mock_project
        
        result = self.extractor.extract(mock_issue, 'TEST', ['No assignee'])
        assert result['Ключ'] == 'TEST-123'
        assert result['Тип'] == 'Task'
        assert result['Исполнитель'] == 'Ivanov'
        assert result['Факт (ч)'] == '1.0'  # Теперь возвращается строка
        assert result['Оценка (ч)'] == '2.0'  # Теперь возвращается строка
        assert result['Проблемы'] == 'No assignee'

    def test_extract_no_assignee(self):
        mock_issue = Mock()
        mock_issue.key = 'TEST-124'
        mock_issue.fields.timespent = None
        mock_issue.fields.timeoriginalestimate = None
        mock_issue.fields.issuetype.name = 'Bug'
        mock_issue.fields.assignee = None
        mock_issue.fields.duedate = None
        mock_issue.fields.resolutiondate = None
        mock_issue.fields.created = '2024-01-01'
        mock_issue.fields.status = None
        mock_issue.fields.summary = 'Bug task'
        mock_project = Mock()
        mock_project.name = 'Test Project'
        mock_project.key = 'TEST'
        mock_issue.fields.project = mock_project
        
        result = self.extractor.extract(mock_issue, 'TEST', [])
        assert result['Исполнитель'] == 'Без исполнителя'
        assert result['Факт (ч)'] == '0.0'  # Теперь возвращается строка

    def test_extract_with_extra_verbose(self):
        mock_issue = Mock()
        mock_issue.key = 'TEST-125'
        mock_issue.id = '10005'
        mock_issue.fields.timespent = 0
        mock_issue.fields.timeoriginalestimate = 0
        mock_issue.fields.issuetype.name = 'Story'
        mock_issue.fields.assignee.displayName = 'Petrov'
        mock_issue.fields.assignee.id = 'user123'
        mock_issue.fields.duedate = '2024-06-01'
        mock_issue.fields.resolutiondate = None
        mock_issue.fields.created = '2024-01-01'
        mock_issue.fields.status.name = 'In Progress'
        mock_issue.fields.status.statusCategory.key = 'indeterminate'
        mock_issue.fields.status.id = '3'
        mock_issue.fields.summary = 'Story task'
        mock_project = Mock()
        mock_project.name = 'Test Project'
        mock_project.key = 'TEST'
        mock_project.id = '10000'
        mock_issue.fields.project = mock_project
        
        extractor = IssueDataExtractor(extra_verbose=True)
        result = extractor.extract(mock_issue, 'TEST', [])
        assert 'Petrov' in result['Исполнитель']
        assert 'user123' in result['Исполнитель']


class TestReportBlockGenerator:
    """Тесты для ReportBlockGenerator"""

    def setup_method(self):
        self.generator = ReportBlockGenerator('summary', extra_verbose=False)

    def test_generate_summary_basic(self):
        result = self.generator.generate_summary(
            proj_name='TEST', proj_correct=10, proj_issues=2,
            proj_estimated=80.0, proj_spent=75.5, issues_normal=None
        )
        assert result['Клиент (Проект)'] == 'TEST'
        assert result['Задач закрыто'] == 12
        assert result['Корректных'] == 10
        assert abs(result['Оценка (ч)'] - 80.0) < 0.01
        assert abs(result['Факт (ч)'] - 75.5) < 0.01

    def test_generate_summary_with_extra_verbose(self):
        mock_issue = Mock()
        mock_project = Mock()
        mock_project.id = '10000'
        mock_issue.fields.project = mock_project
        generator = ReportBlockGenerator('summary', extra_verbose=True)
        result = generator.generate_summary(
            proj_name='TEST', proj_correct=5, proj_issues=1,
            proj_estimated=40.0, proj_spent=42.0, issues_normal=[mock_issue]
        )
        # В extra_verbose режиме ID добавляется к значению, а не отдельной колонкой
        assert result['Клиент (Проект)'] == 'TEST [10000]'
        assert result['Оценка (ч)'] == '40.0 [timeoriginalestimate]'
        assert result['Факт (ч)'] == '42.0 [timespent]'
        assert result['Отклонение'] == -2.0


class TestRiskZoneAnalyzer:
    """Тесты для RiskZoneAnalyzer"""

    def setup_method(self):
        self.analyzer = RiskZoneAnalyzer()

    def test_analyze_no_assignee(self):
        """Тест задачи без исполнителя"""
        mock_issue = Mock()
        mock_issue.fields.assignee = None
        mock_issue.fields.duedate = None
        mock_issue.fields.status = None
        mock_issue.fields.updated = None
        
        result = self.analyzer.analyze(mock_issue)
        assert 'Без исполнителя' in result

    def test_analyze_overdue(self):
        """Тест просроченной задачи"""
        past_date = datetime.now() - timedelta(days=10)
        mock_issue = Mock()
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.duedate = past_date.strftime('%Y-%m-%d')
        mock_issue.fields.status.name = 'Open'
        mock_issue.fields.updated = past_date.strftime('%Y-%m-%dT%H:%M:%S')
        
        result = self.analyzer.analyze(mock_issue)
        assert any('Просрочена' in r for r in result)

    def test_analyze_no_risks(self):
        """Тест задачи без рисков"""
        future_date = datetime.now() + timedelta(days=10)
        mock_issue = Mock()
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.duedate = future_date.strftime('%Y-%m-%d')
        mock_issue.fields.status.name = 'In Progress'
        mock_issue.fields.updated = future_date.strftime('%Y-%m-%dT%H:%M:%S')
        
        result = self.analyzer.analyze(mock_issue)
        assert len(result) == 0


class TestReportGenerator:
    """Тесты для ReportGenerator"""

    def setup_method(self):
        self.patch_jira = patch('core.report_generator.get_jira_connection')
        self.mock_jira = self.patch_jira.start()
        self.mock_jira.return_value = Mock()

    def teardown_method(self):
        self.patch_jira.stop()

    def test_init(self):
        generator = ReportGenerator(
            project_keys=['TEST'], start_date='2024-01-01',
            end_date='2024-01-31', days=30, verbose=False
        )
        assert generator.project_keys == ['TEST']
        assert generator.start_date_input == '2024-01-01'
        assert generator.days == 30

    def test_init_with_defaults(self):
        generator = ReportGenerator()
        assert generator.project_keys == []
        assert generator.days == 30
        assert generator.blocks is not None

    def test_risk_analyzer_component(self):
        """Тест компонента RiskZoneAnalyzer в ReportGenerator"""
        generator = ReportGenerator(project_keys=[])
        assert generator.risk_analyzer is not None
        assert hasattr(generator.risk_analyzer, 'analyze')


class TestGenerateReportWrapper:
    """Тесты для функции-обёртки generate_report"""

    @patch('core.report_generator.ReportGenerator')
    def test_generate_report_calls_generator(self, mock_generator_class):
        from core.report_generator import generate_report
        mock_generator = Mock()
        mock_generator.generate.return_value = {'period': {}, 'summary': []}
        mock_generator_class.return_value = mock_generator
        result = generate_report(project_keys=['TEST'], start_date='2024-01-01', days=30)
        mock_generator_class.assert_called_once()
        mock_generator.generate.assert_called_once()
        assert result == {'period': {}, 'summary': []}
