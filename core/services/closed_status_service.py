# -*- coding: utf-8 -*-
"""
Сервис проверки закрытых статусов.

Инкапсулирует логику определения закрытых статусов задач.
Используется вместо дублирования кода в problems_dict.py, report_generator.py, jira_report.py.
"""
from typing import List, Set, Optional, Any
from functools import lru_cache
import logging

from core.config import CLOSED_STATUS_IDS, JIRA_SERVER, JIRA_USER, JIRA_PASS

logger = logging.getLogger(__name__)


class ClosedStatusService:
    """
    Сервис для проверки закрытых статусов.
    
    Использует statusCategory.key из API Jira как основной критерий,
    а также проверяет по названию статуса и ID.
    """
    
    # Названия закрытых статусов (нижний регистр)
    CLOSED_STATUS_NAMES: Set[str] = {
        'закрыт', 'closed', 'закрыто', 'готово', 'done', 'ready'
    }
    
    # Явные ID закрытых статусов (добавляются вручную при необходимости)
    CLOSED_STATUS_IDS_MANUAL: Set[str] = set()  # Заполняется при инициализации
    
    def __init__(self, additional_ids: Optional[List[str]] = None):
        """
        Инициализация сервиса.
        
        Args:
            additional_ids: Дополнительные ID статусов для ручного добавления
        """
        self._closed_status_ids: Set[str] = set(CLOSED_STATUS_IDS) if CLOSED_STATUS_IDS else set()
        self._closed_status_ids.update(self.CLOSED_STATUS_IDS_MANUAL)
        if additional_ids:
            self._closed_status_ids.update(additional_ids)
        
        logger.debug(f"ClosedStatusService инициализирован. Закрытые статусы: {self._closed_status_ids}")
    
    def is_closed_by_name(self, status_name: str) -> bool:
        """
        Проверка статуса по названию.
        
        Args:
            status_name: Название статуса (например, 'Закрыт', 'Готово')
            
        Returns:
            bool: True если статус закрытый
        """
        if not status_name:
            return False
        return status_name.lower() in self.CLOSED_STATUS_NAMES
    
    def is_closed_by_id(self, status_id: str) -> bool:
        """
        Проверка статуса по ID.
        
        Args:
            status_id: ID статуса (например, '10001')
            
        Returns:
            bool: True если статус закрытый
        """
        if not status_id:
            return False
        return status_id in self._closed_status_ids
    
    def is_closed(self, status_name: Optional[str] = None, status_id: Optional[str] = None) -> bool:
        """
        Универсальная проверка статуса.
        
        Проверяет и по названию, и по ID. Если хотя бы одно совпадение — статус закрытый.
        
        Args:
            status_name: Название статуса (опционально)
            status_id: ID статуса (опционально)
            
        Returns:
            bool: True если статус закрытый
        """
        # Проверяем по названию
        if status_name and self.is_closed_by_name(status_name):
            return True
        
        # Проверяем по ID
        if status_id and self.is_closed_by_id(status_id):
            return True
        
        return False
    
    def is_closed_from_issue(self, issue: Any) -> bool:
        """
        Проверка статуса из объекта задачи Jira.
        
        Args:
            issue: Объект задачи Jira (должен иметь fields.status)
            
        Returns:
            bool: True если статус закрытый
        """
        if not hasattr(issue, 'fields') or not issue.fields:
            return False
        
        if not hasattr(issue.fields, 'status') or not issue.fields.status:
            return False
        
        status = issue.fields.status
        status_name = getattr(status, 'name', '')
        status_id = getattr(status, 'id', '')
        
        return self.is_closed(status_name=status_name, status_id=status_id)
    
    def is_closed_from_dict(self, issue_data: dict) -> bool:
        """
        Проверка статуса из словаря (REST API ответ).
        
        Args:
            issue_data: Словарь с данными задачи (должен содержать fields.status)
            
        Returns:
            bool: True если статус закрытый
        """
        if not issue_data or not isinstance(issue_data, dict):
            return False
        
        fields = issue_data.get('fields', {})
        if not fields:
            return False
        
        status = fields.get('status', {})
        if not status:
            return False
        
        status_name = status.get('name', '')
        status_id = status.get('id', '')
        
        return self.is_closed(status_name=status_name, status_id=status_id)
    
    def add_closed_status_id(self, status_id: str) -> None:
        """
        Добавить ID закрытого статуса вручную.
        
        Args:
            status_id: ID статуса для добавления
        """
        self._closed_status_ids.add(status_id)
        logger.debug(f"Добавлен закрытый статус ID: {status_id}")
    
    def get_closed_status_ids(self) -> Set[str]:
        """
        Получить все известные ID закрытых статусов.
        
        Returns:
            Set[str]: Множество ID закрытых статусов
        """
        return self._closed_status_ids.copy()


# Глобальный экземпляр сервиса (ленивая инициализация)
_service_instance: Optional[ClosedStatusService] = None


def get_closed_status_service(additional_ids: Optional[List[str]] = None) -> ClosedStatusService:
    """
    Получить глобальный экземпляр сервиса.
    
    Args:
        additional_ids: Дополнительные ID статусов для ручного добавления
        
    Returns:
        ClosedStatusService: Экземпляр сервиса
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = ClosedStatusService(additional_ids=additional_ids)
    return _service_instance


def is_status_closed(
    status_name: Optional[str] = None,
    status_id: Optional[str] = None
) -> bool:
    """
    Удобная функция для быстрой проверки статуса.
    
    Args:
        status_name: Название статуса (опционально)
        status_id: ID статуса (опционально)
        
    Returns:
        bool: True если статус закрытый
        
    Примеры:
        >>> is_status_closed(status_name='Закрыт')
        True
        >>> is_status_closed(status_id='10001')  # Готово
        True
        >>> is_status_closed(status_name='В работе')
        False
    """
    service = get_closed_status_service()
    return service.is_closed(status_name=status_name, status_id=status_id)
