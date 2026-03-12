# -*- coding: utf-8 -*-
"""
Тесты для сервисов Jira Report System.

Тестируются:
- ClosedStatusService
- IssueValidator
- MetadataCache
- IssueFetcher (частично)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import time

from core.services.closed_status_service import (
    ClosedStatusService,
    is_status_closed,
    get_closed_status_service,
)
from core.services.cache_service import (
    MetadataCache,
    get_metadata_cache,
    cached,
)
from core.services.issue_validator import IssueValidator
from core.dtos import IssueDTO, StatusDTO, AssigneeDTO


# =============================================
# Тесты для ClosedStatusService
# =============================================

class TestClosedStatusService:
    """Тесты для сервиса проверки статусов."""

    def test_init_default(self):
        """Инициализация по умолчанию."""
        service = ClosedStatusService()
        assert service.CLOSED_STATUS_NAMES == {
            'закрыт', 'closed', 'закрыто', 'готово', 'done', 'ready'
        }

    def test_is_closed_by_name_closed(self):
        """Проверка статуса 'Закрыт'."""
        service = ClosedStatusService()
        assert service.is_closed_by_name('Закрыт') is True
        assert service.is_closed_by_name('закрыт') is True
        assert service.is_closed_by_name('CLOSED') is True

    def test_is_closed_by_name_ready(self):
        """Проверка статуса 'Готово'."""
        service = ClosedStatusService()
        assert service.is_closed_by_name('Готово') is True
        assert service.is_closed_by_name('готово') is True
        assert service.is_closed_by_name('Done') is True

    def test_is_closed_by_name_open(self):
        """Проверка открытых статусов."""
        service = ClosedStatusService()
        assert service.is_closed_by_name('В работе') is False
        assert service.is_closed_by_name('Open') is False
        assert service.is_closed_by_name('To Do') is False

    def test_is_closed_by_id(self):
        """Проверка по ID."""
        service = ClosedStatusService(additional_ids=['10001', '10002'])
        assert service.is_closed_by_id('10001') is True
        assert service.is_closed_by_id('10002') is True
        assert service.is_closed_by_id('99999') is False

    def test_is_closed_combined(self):
        """Комбинированная проверка."""
        service = ClosedStatusService(additional_ids=['10001'])
        
        # По названию
        assert service.is_closed(status_name='Закрыт') is True
        
        # По ID
        assert service.is_closed(status_id='10001') is True
        
        # Оба параметра
        assert service.is_closed(status_name='В работе', status_id='10001') is True
        
        # Ни то, ни другое
        assert service.is_closed(status_name='В работе', status_id='99999') is False

    def test_add_closed_status_id(self):
        """Добавление ID статуса."""
        service = ClosedStatusService()
        service.add_closed_status_id('12345')
        assert '12345' in service.get_closed_status_ids()


# =============================================
# Тесты для MetadataCache
# =============================================

class TestMetadataCache:
    """Тесты для кэша метаданных."""

    def test_init_default(self):
        """Инициализация по умолчанию."""
        cache = MetadataCache()
        assert cache.ttl > 0
        assert cache.max_size > 0

    def test_set_get(self):
        """Сохранение и получение значения."""
        cache = MetadataCache(ttl=60)
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'

    def test_get_missing_key(self):
        """Получение отсутствующего ключа."""
        cache = MetadataCache()
        assert cache.get('nonexistent') is None
        assert cache.get('nonexistent', 'default') == 'default'

    def test_delete(self):
        """Удаление ключа."""
        cache = MetadataCache()
        cache.set('key1', 'value1')
        cache.delete('key1')
        assert cache.get('key1') is None

    def test_clear(self):
        """Очистка кэша."""
        cache = MetadataCache()
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.clear()
        assert cache.stats()['size'] == 0

    def test_ttl_expiration(self):
        """Истечение TTL."""
        cache = MetadataCache(ttl=1)  # 1 секунда
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
        time.sleep(1.1)  # Ждём истечения TTL
        assert cache.get('key1') is None

    def test_lru_eviction(self):
        """LRU вытеснение."""
        cache = MetadataCache(max_size=3)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        # Обращаемся к key1, чтобы сделать его недавно использованным
        cache.get('key1')
        
        # Добавляем новый ключ, должен вытесниться key2 (LRU)
        cache.set('key4', 'value4')
        
        assert cache.get('key1') == 'value1'
        assert cache.get('key2') is None  # Вытеснен
        assert cache.get('key3') == 'value3'
        assert cache.get('key4') == 'value4'

    def test_stats(self):
        """Статистика кэша."""
        cache = MetadataCache(ttl=300, max_size=100)
        cache.set('key1', 'value1')
        stats = cache.stats()
        
        assert stats['size'] == 1
        assert stats['max_size'] == 100
        assert stats['ttl'] == 300


# =============================================
# Тесты для IssueValidator
# =============================================

class TestIssueValidator:
    """Тесты для валидатора задач."""

    @pytest.fixture
    def validator(self):
        """Создание валидатора."""
        return IssueValidator(closed_status_ids=['1', '10001'])

    def _create_mock_issue(self, **kwargs):
        """Создать mock задачу."""
        defaults = {
            'assignee': Mock(displayName='Test User'),
            'timespent': 3600,
            'timeoriginalestimate': 7200,
            'resolutiondate': '2026-03-10T10:00:00',
            'status': Mock(id='1', name='Закрыт', statusCategory=Mock(key='done')),
            'created': '2026-03-01T10:00:00',
            'duedate': '2026-03-10',
            'issuetype': Mock(name='Task'),
            'updated': '2026-03-10T10:00:00',
        }
        defaults.update(kwargs)
        
        mock_fields = Mock()
        for key, value in defaults.items():
            setattr(mock_fields, key, value)
        
        mock_issue = Mock()
        mock_issue.fields = mock_fields
        mock_issue.key = 'TEST-1'
        
        return mock_issue

    def test_validate_correct_issue(self, validator):
        """Валидация корректной задачи."""
        issue = self._create_mock_issue()
        problems = validator.validate(issue)
        assert len(problems) == 0

    def test_validate_no_assignee(self, validator):
        """Задача без исполнителя."""
        issue = self._create_mock_issue(assignee=None)
        problems = validator.validate(issue)
        assert 'Без исполнителя' in problems

    def test_validate_no_time_spent(self, validator):
        """Задача без фактического времени."""
        issue = self._create_mock_issue(timespent=None)
        problems = validator.validate(issue)
        assert 'Нет фактического' in problems

    def test_validate_no_resolution_date(self, validator):
        """Задача без даты решения."""
        issue = self._create_mock_issue(resolutiondate=None)
        problems = validator.validate(issue)
        assert 'Нет даты решения' in problems

    def test_validate_closed_status_correct(self, validator):
        """Задача со статусом 'Закрыт' — корректно."""
        issue = self._create_mock_issue(
            status=Mock(id='1', name='Закрыт', statusCategory=Mock(key='done'))
        )
        # Добавляем changelog
        history = Mock()
        history.author = Mock(displayName='bot')
        history.items = [Mock(field='status', toString='Закрыт', to='1')]
        issue.changelog = Mock(histories=[history])
        
        problems = validator.validate(issue)
        # Не должно быть проблемы INCORRECT_STATUS
        assert 'Некорректный статус' not in problems


# =============================================
# Тесты для IssueDTO
# =============================================

class TestIssueDTO:
    """Тесты для DTO задач."""

    def test_from_dict_full(self):
        """Создание DTO из полного словаря."""
        data = {
            'key': 'WEB-123',
            'fields': {
                'summary': 'Test issue',
                'assignee': {'displayName': 'John', 'accountId': 'user123'},
                'timespent': 3600,
                'timeoriginalestimate': 7200,
                'resolutiondate': '2026-03-10T10:00:00',
                'status': {'id': '1', 'name': 'Done', 'statusCategory': {'key': 'done'}},
                'created': '2026-03-01T10:00:00',
                'duedate': '2026-03-10',
                'issuetype': {'id': '3', 'name': 'Task'},
                'project': {'id': '10000', 'key': 'WEB', 'name': 'Web'},
                'priority': {'id': '2', 'name': 'High'},
                'updated': '2026-03-10T10:00:00',
            }
        }
        
        issue = IssueDTO.from_dict(data)
        
        assert issue.key == 'WEB-123'
        assert issue.summary == 'Test issue'
        assert issue.assignee.display_name == 'John'
        assert issue.timespent == 3600
        assert issue.status.name == 'Done'
        assert issue.project.key == 'WEB'

    def test_from_dict_empty(self):
        """Создание DTO из пустого словаря."""
        issue = IssueDTO.from_dict({})
        assert issue.key == ''
        assert issue.summary == ''

    def test_fields_wrapper(self):
        """Обёртка полей."""
        issue = IssueDTO(
            key='TEST-1',
            status=StatusDTO(id='1', name='Done'),
            assignee=AssigneeDTO(display_name='John')
        )
        
        assert issue.fields.status.id == '1'
        assert issue.fields.assignee.display_name == 'John'


# =============================================
# Интеграционные тесты
# =============================================

class TestIntegration:
    """Интеграционные тесты сервисов."""

    def test_cache_with_service(self):
        """Кэширование в сервисе."""
        cache = get_metadata_cache(ttl=60)
        cache.set('test_key', {'data': 'value'})
        
        assert cache.get('test_key') == {'data': 'value'}

    def test_is_status_closed_function(self):
        """Функция is_status_closed."""
        # Закрытый статус по названию
        assert is_status_closed(status_name='Закрыт') is True
        assert is_status_closed(status_name='Готово') is True
        
        # Открытый статус
        assert is_status_closed(status_name='В работе') is False
