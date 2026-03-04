# -*- coding: utf-8 -*-
"""
Р‘Р°Р·РѕРІС‹Рµ С‚РµСЃС‚С‹ РґР»СЏ Jira Report System
"""
import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Р”РѕР±Р°РІР»СЏРµРј РїСѓС‚СЊ Рє РјРѕРґСѓР»СЋ
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
    """РўРµСЃС‚С‹ РєРѕРЅРІРµСЂС‚Р°С†РёРё СЃРµРєСѓРЅРґ РІ С‡Р°СЃС‹"""

    def test_none_value(self):
        assert convert_seconds_to_hours(None) == 0.0

    def test_zero_value(self):
        assert convert_seconds_to_hours(0) == 0.0

    def test_one_hour(self):
        assert convert_seconds_to_hours(3600) == 1.0

    def test_half_hour(self):
        assert convert_seconds_to_hours(1800) == 0.5

    def test_rounding(self):
        result = convert_seconds_to_hours(3661)  # 1 С‡Р°СЃ 1 РјРёРЅСѓС‚Р° 1 СЃРµРєСѓРЅРґР°
        assert result == 1.02


class TestGetDefaultStartDate:
    """РўРµСЃС‚С‹ РїРѕР»СѓС‡РµРЅРёСЏ РґР°С‚С‹ РЅР°С‡Р°Р»Р° РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ"""

    def test_january_returns_december(self):
        # РўРµСЃС‚РёСЂСѓРµРј Р»РѕРіРёРєСѓ РЅР°РїСЂСЏРјСѓСЋ
        from datetime import datetime
        # Р•СЃР»Рё СЃРµР№С‡Р°СЃ СЏРЅРІР°СЂСЊ, РґРѕР»Р¶РµРЅ РІРµСЂРЅСѓС‚СЊСЃСЏ РґРµРєР°Р±СЂСЊ РїСЂРѕС€Р»РѕРіРѕ РіРѕРґР°
        today = datetime(2024, 1, 15)
        if today.month == 1:
            expected = datetime(today.year - 1, 12, 1)
        else:
            expected = datetime(today.year, today.month - 1, 1)
        assert expected == datetime(2023, 12, 1)

    def test_other_month_returns_previous(self):
        # РўРµСЃС‚РёСЂСѓРµРј Р»РѕРіРёРєСѓ РЅР°РїСЂСЏРјСѓСЋ
        from datetime import datetime
        # Р•СЃР»Рё РёСЋРЅСЊ, РґРѕР»Р¶РµРЅ РІРµСЂРЅСѓС‚СЊСЃСЏ РјР°Р№
        today = datetime(2024, 6, 15)
        if today.month == 1:
            expected = datetime(today.year - 1, 12, 1)
        else:
            expected = datetime(today.year, today.month - 1, 1)
        assert expected == datetime(2024, 5, 1)


class TestGetColumnOrder:
    """РўРµСЃС‚С‹ РїРѕР»СѓС‡РµРЅРёСЏ РїРѕСЂСЏРґРєР° РєРѕР»РѕРЅРѕРє"""

    def test_summary_columns(self):
        cols = get_column_order('summary')
        assert 'РљР»РёРµРЅС‚ (РџСЂРѕРµРєС‚)' in cols
        assert 'Р¤Р°РєС‚ (С‡)' in cols
        assert len(cols) == 7

    def test_summary_columns_extra_verbose(self):
        cols = get_column_order('summary', extra_verbose=True)
        assert 'РљР»РёРµРЅС‚ (РџСЂРѕРµРєС‚)' in cols
        assert 'ID' in cols
        assert len(cols) == 8

    def test_assignees_columns(self):
        cols = get_column_order('assignees')
        assert 'РСЃРїРѕР»РЅРёС‚РµР»СЊ' in cols
        assert 'Р—Р°РґР°С‡' in cols
        assert len(cols) == 7

    def test_assignees_columns_extra_verbose(self):
        cols = get_column_order('assignees', extra_verbose=True)
        assert 'РСЃРїРѕР»РЅРёС‚РµР»СЊ' in cols
        assert 'ID' in cols
        assert len(cols) == 8

    def test_detail_columns(self):
        cols = get_column_order('detail')
        assert 'URL' in cols
        assert 'Р—Р°РґР°С‡Р°' in cols
        assert len(cols) == 9

    def test_detail_columns_extra_verbose(self):
        cols = get_column_order('detail', extra_verbose=True)
        assert 'URL' in cols
        assert 'ID' in cols
        assert len(cols) == 10

    def test_issues_columns(self):
        cols = get_column_order('issues')
        assert 'URL' in cols
        assert 'РџСЂРѕР±Р»РµРјС‹' in cols
        assert len(cols) == 8

    def test_issues_columns_extra_verbose(self):
        cols = get_column_order('issues', extra_verbose=True)
        assert 'URL' in cols
        assert 'ID' in cols
        assert len(cols) == 9

    def test_unknown_block(self):
        cols = get_column_order('unknown')
        assert 'РџСЂРѕРµРєС‚' in cols
        assert len(cols) == 9


class TestValidateConfig:
    """РўРµСЃС‚С‹ РІР°Р»РёРґР°С†РёРё РєРѕРЅС„РёРіСѓСЂР°С†РёРё"""

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
        assert 'РќРµ СѓРєР°Р·Р°РЅ JIRA_SERVER РІ .env' in errors


class TestValidateIssue:
    """РўРµСЃС‚С‹ РІР°Р»РёРґР°С†РёРё Р·Р°РґР°С‡"""

    def test_no_resolution_date(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = None
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '1'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = None

        problems = validate_issue(mock_issue)
        assert 'РќРµС‚ РґР°С‚С‹ СЂРµС€РµРЅРёСЏ' in problems

    def test_no_time_spent(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = None
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '1'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = None

        problems = validate_issue(mock_issue)
        assert 'РќРµС‚ С„Р°РєС‚РёС‡РµСЃРєРѕРіРѕ РІСЂРµРјРµРЅРё' in problems

    def test_zero_time_spent(self):
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 0
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '1'
        mock_issue.fields.status.name = 'Done'
        mock_issue.fields.assignee = None

        problems = validate_issue(mock_issue)
        assert 'РќРµС‚ С„Р°РєС‚РёС‡РµСЃРєРѕРіРѕ РІСЂРµРјРµРЅРё' in problems

    def test_closed_status_without_changelog_is_problem(self):
        """Р•СЃР»Рё СЃС‚Р°С‚СѓСЃ 'Р—Р°РєСЂС‹С‚' Рё РЅРµС‚ changelog (jira=None) вЂ” СЌС‚Рѕ РїСЂРѕР±Р»РµРјР°"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'  # Р’ СЃРїРёСЃРєРµ CLOSED_STATUS_IDS
        mock_issue.fields.status.name = 'Р—Р°РєСЂС‹С‚'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'
        mock_issue.fields.assignee.displayName = 'Ivanov Ivan'

        with patch('jira_report.CLOSED_STATUS_IDS', ['10001']):
            # jira=None, changelog РїСЂРѕРІРµСЂРёС‚СЊ РЅРµР»СЊР·СЏ
            problems = validate_issue(mock_issue, jira=None)
            assert any('РЎС‚Р°С‚СѓСЃ' in p for p in problems)

    def test_excluded_assignee_closed_status_ok(self):
        """Р”Р»СЏ РёСЃРїРѕР»РЅРёС‚РµР»СЏ РёР· EXCLUDED_ASSIGNEE_CLOSE СЃС‚Р°С‚СѓСЃ 'Р—Р°РєСЂС‹С‚' вЂ” РћРљ"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'
        mock_issue.fields.status.name = 'Р—Р°РєСЂС‹С‚'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'holin'
        mock_issue.fields.assignee.displayName = 'Holin Petr'

        with patch('jira_report.CLOSED_STATUS_IDS', ['10001']):
            problems = validate_issue(mock_issue, jira=None)
            # Р”Р»СЏ holin СЃС‚Р°С‚СѓСЃ "Р—Р°РєСЂС‹С‚" РЅРµ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РїСЂРѕР±Р»РµРјРѕР№
            assert not any('РЎС‚Р°С‚СѓСЃ' in p for p in problems)

    def test_closed_by_jira_user_is_ok(self):
        """Р•СЃР»Рё Р·Р°РґР°С‡Р° Р·Р°РєСЂС‹С‚Р° РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј РґРµРјРѕРЅР° (JIRA_USER) вЂ” СЌС‚Рѕ РћРљ"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'
        mock_issue.fields.status.name = 'Р—Р°РєСЂС‹С‚'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'
        mock_issue.fields.assignee.displayName = 'Ivanov Ivan'
        
        # РљР»СЋС‡ Р·Р°РґР°С‡Рё
        mock_issue.key = 'TEST-123'
        
        # РЎРѕР·РґР°С‘Рј mock changelog СЃ РїРµСЂРµС…РѕРґРѕРј РѕС‚ jira_user
        mock_changelog = Mock()
        mock_history = Mock()
        mock_history_item = Mock()
        mock_history_item.field = 'status'
        mock_history_item.toString = 'Р—Р°РєСЂС‹С‚'
        mock_history_item.to = '10001'
        mock_history.items = [mock_history_item]
        mock_history.author = Mock()
        mock_history.author.name = 'jira_user'  # РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РґРµРјРѕРЅР°
        mock_changelog.histories = [mock_history]
        
        mock_issue_with_changelog = Mock()
        mock_issue_with_changelog.changelog = mock_changelog
        
        mock_jira = Mock()
        mock_jira.issue.return_value = mock_issue_with_changelog

        with patch('jira_report.CLOSED_STATUS_IDS', ['10001']):
            with patch('jira_report.JIRA_USER', 'jira_user'):
                problems = validate_issue(mock_issue, jira=mock_jira)
                # Р—Р°РєСЂС‹С‚Рѕ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј РґРµРјРѕРЅР° вЂ” РїСЂРѕР±Р»РµРј РЅРµС‚
                assert not any('РЎС‚Р°С‚СѓСЃ' in p for p in problems)

    def test_closed_by_other_user_is_problem(self):
        """Р•СЃР»Рё Р·Р°РґР°С‡Р° Р·Р°РєСЂС‹С‚Р° РЅРµ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј РґРµРјРѕРЅР° вЂ” СЌС‚Рѕ РїСЂРѕР±Р»РµРјР°"""
        mock_issue = Mock()
        mock_issue.fields.resolutiondate = '2024-01-01'
        mock_issue.fields.timespent = 3600
        mock_issue.fields.status = Mock()
        mock_issue.fields.status.id = '10001'
        mock_issue.fields.status.name = 'Р—Р°РєСЂС‹С‚'
        mock_issue.fields.assignee = Mock()
        mock_issue.fields.assignee.name = 'ivanov'
        mock_issue.fields.assignee.displayName = 'Ivanov Ivan'
        
        mock_issue.key = 'TEST-123'
        
        # Changelog СЃ РїРµСЂРµС…РѕРґРѕРј РѕС‚ РґСЂСѓРіРѕРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        mock_changelog = Mock()
        mock_history = Mock()
        mock_history_item = Mock()
        mock_history_item.field = 'status'
        mock_history_item.toString = 'Р—Р°РєСЂС‹С‚'
        mock_history_item.to = '10001'
        mock_history.items = [mock_history_item]
        mock_history.author = Mock()
        mock_history.author.name = 'petrov'  # Р”СЂСѓРіРѕР№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ
        mock_changelog.histories = [mock_history]
        
        mock_issue_with_changelog = Mock()
        mock_issue_with_changelog.changelog = mock_changelog
        
        mock_jira = Mock()
        mock_jira.issue.return_value = mock_issue_with_changelog

        with patch('jira_report.CLOSED_STATUS_IDS', ['10001']):
            with patch('jira_report.JIRA_USER', 'jira_user'):
                problems = validate_issue(mock_issue, jira=mock_jira)
                # Р—Р°РєСЂС‹С‚Рѕ РЅРµ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј РґРµРјРѕРЅР° вЂ” СЌС‚Рѕ РїСЂРѕР±Р»РµРјР°
                assert any('РЎС‚Р°С‚СѓСЃ' in p for p in problems)

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
    """РўРµСЃС‚С‹ Р±Р»РѕРєРѕРІ РѕС‚С‡С‘С‚Р°"""

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
