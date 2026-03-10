# -*- coding: utf-8 -*-
"""
Тесты для конфигурации планировщика задач
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import (
    SCHEDULER_TIMEZONE,
    SCHEDULER_DEFAULT_HOUR,
    SCHEDULER_MISFIRE_GRACE_TIME,
    SCHEDULER_MAX_INSTANCES,
    SCHEDULER_JOBSTORE_RELOAD_INTERVAL
)


class TestSchedulerConfig:
    """Тесты конфигурации планировщика"""

    def test_scheduler_timezone_exists(self):
        """Тест существования часового пояса"""
        assert SCHEDULER_TIMEZONE is not None
        assert isinstance(SCHEDULER_TIMEZONE, str)
        assert len(SCHEDULER_TIMEZONE) > 0

    def test_scheduler_timezone_valid(self):
        """Тест валидности часового пояса"""
        # Europe/Moscow - стандартный формат
        assert '/' in SCHEDULER_TIMEZONE or SCHEDULER_TIMEZONE == 'UTC'

    def test_scheduler_default_hour_exists(self):
        """Тест существования часа по умолчанию"""
        assert SCHEDULER_DEFAULT_HOUR is not None
        assert isinstance(SCHEDULER_DEFAULT_HOUR, int)

    def test_scheduler_default_hour_valid(self):
        """Тест валидности часа по умолчанию (0-23)"""
        assert 0 <= SCHEDULER_DEFAULT_HOUR <= 23
        assert SCHEDULER_DEFAULT_HOUR == 9  # Значение по умолчанию

    def test_scheduler_misfire_grace_time_exists(self):
        """Тест существования misfire grace time"""
        assert SCHEDULER_MISFIRE_GRACE_TIME is not None
        assert isinstance(SCHEDULER_MISFIRE_GRACE_TIME, int)

    def test_scheduler_misfire_grace_time_valid(self):
        """Тест валидности misfire grace time"""
        assert SCHEDULER_MISFIRE_GRACE_TIME > 0
        assert SCHEDULER_MISFIRE_GRACE_TIME == 3600  # 1 час по умолчанию

    def test_scheduler_max_instances_exists(self):
        """Тест существования максимального количества задач"""
        assert SCHEDULER_MAX_INSTANCES is not None
        assert isinstance(SCHEDULER_MAX_INSTANCES, int)

    def test_scheduler_max_instances_valid(self):
        """Тест валидности максимального количества задач"""
        assert SCHEDULER_MAX_INSTANCES > 0
        assert SCHEDULER_MAX_INSTANCES == 3  # Значение по умолчанию

    def test_scheduler_reload_interval_exists(self):
        """Тест существования интервала перезагрузки"""
        assert SCHEDULER_JOBSTORE_RELOAD_INTERVAL is not None
        assert isinstance(SCHEDULER_JOBSTORE_RELOAD_INTERVAL, int)

    def test_scheduler_reload_interval_valid(self):
        """Тест валидности интервала перезагрузки"""
        assert SCHEDULER_JOBSTORE_RELOAD_INTERVAL > 0
        assert SCHEDULER_JOBSTORE_RELOAD_INTERVAL == 60  # 1 минута по умолчанию


class TestSchedulerConfigIntegration:
    """Интеграционные тесты конфигурации"""

    def test_all_scheduler_configs_are_positive(self):
        """Все числовые конфигурации положительны"""
        assert SCHEDULER_DEFAULT_HOUR >= 0
        assert SCHEDULER_MISFIRE_GRACE_TIME > 0
        assert SCHEDULER_MAX_INSTANCES > 0
        assert SCHEDULER_JOBSTORE_RELOAD_INTERVAL > 0

    def test_scheduler_configs_types(self):
        """Проверка типов конфигураций"""
        assert isinstance(SCHEDULER_TIMEZONE, str)
        assert isinstance(SCHEDULER_DEFAULT_HOUR, int)
        assert isinstance(SCHEDULER_MISFIRE_GRACE_TIME, int)
        assert isinstance(SCHEDULER_MAX_INSTANCES, int)
        assert isinstance(SCHEDULER_JOBSTORE_RELOAD_INTERVAL, int)
