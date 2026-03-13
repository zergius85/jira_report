# -*- coding: utf-8 -*-
"""
Форматтеры для Jira Report System.

Используется для форматирования данных с ID в режиме extra_verbose.
"""
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class VerboseFormatter:
    """
    Форматтер для режима extra_verbose.
    
    Добавляет ID объектов к отображаемым значениям в формате "name [id]".
    
    Attributes:
        extra_verbose: Включить режим подробного вывода с ID
    """
    extra_verbose: bool = False
    
    def format_with_id(self, name: str, obj_id: Optional[str]) -> str:
        """
        Добавить ID к значению.
        
        Args:
            name: Отображаемое имя
            obj_id: ID объекта (может быть None)
            
        Returns:
            Строка формата "name [id]" или "name"
            
        Примеры:
            >>> formatter = VerboseFormatter(extra_verbose=True)
            >>> formatter.format_with_id('WEB', '10001')
            'WEB [10001]'
            >>> formatter.format_with_id('WEB', None)
            'WEB'
        """
        if self.extra_verbose and obj_id:
            return f"{name} [{obj_id}]"
        return name
    
    def format_date(self, display_value: str, field_name: str, is_empty: bool = False) -> str:
        """
        Добавить название поля даты к значению.
        
        Args:
            display_value: Отображаемое значение даты
            field_name: Название поля (created, duedate, resolutiondate)
            is_empty: Пустое ли значение
            
        Returns:
            Строка формата "date [field_name]" или "date"
            
        Примеры:
            >>> formatter = VerboseFormatter(extra_verbose=True)
            >>> formatter.format_date('2026-03-11', 'created')
            '2026-03-11 [created]'
        """
        if self.extra_verbose and not is_empty and display_value and display_value != '-':
            return f"{display_value} [{field_name}]"
        return display_value
    
    def format_number(self, display_value: Any, field_name: str) -> str:
        """
        Добавить название поля числа к значению.
        
        Args:
            display_value: Отображаемое значение числа
            field_name: Название поля (timespent, timeoriginalestimate)
            
        Returns:
            Строка формата "number [field_name]" или "number"
            
        Примеры:
            >>> formatter = VerboseFormatter(extra_verbose=True)
            >>> formatter.format_number(1.5, 'timespent')
            '1.5 [timespent]'
        """
        if self.extra_verbose:
            return f"{display_value} [{field_name}]"
        return str(display_value)
    
    def format_url(self, base_url: str) -> str:
        """
        Добавить иконку 🔍 к URL.
        
        Args:
            base_url: Базовый URL
            
        Returns:
            URL с иконкой или без
            
        Примеры:
            >>> formatter = VerboseFormatter(extra_verbose=True)
            >>> formatter.format_url('https://jira/browse/WEB-123')
            'https://jira/browse/WEB-123 🔍'
        """
        if self.extra_verbose:
            return f"{base_url} 🔍"
        return base_url
    
    def format_issue_data(
        self,
        issue_data: Dict[str, Any],
        extra_data: Dict[str, Optional[str]]
    ) -> Dict[str, str]:
        """
        Отформатировать данные задачи с ID.
        
        Args:
            issue_data: Основные данные задачи
            extra_data: Дополнительные данные (ID полей)
            
        Returns:
            Отформатированные данные
            
        Пример:
            extra_data = {
                'project_id': '10001',
                'status_id': '10002',
                'type_id': '3',
                'assignee_id': 'user123',
                'created': '2026-03-11',
                'duedate': '2026-03-15',
                'resolutiondate': '2026-03-14'
            }
        """
        if not self.extra_verbose:
            return issue_data
        
        formatted = issue_data.copy()
        
        # Проект с ID
        if extra_data.get('project_id'):
            formatted['Проект'] = self.format_with_id(
                issue_data.get('Проект', ''),
                extra_data['project_id']
            )
        
        # Статус с ID
        if extra_data.get('status_id'):
            formatted['Статус'] = self.format_with_id(
                issue_data.get('Статус', ''),
                extra_data['status_id']
            )
        
        # Тип с ID
        if extra_data.get('type_id'):
            formatted['Тип'] = self.format_with_id(
                issue_data.get('Тип', ''),
                extra_data['type_id']
            )
        
        # Исполнитель с ID
        if extra_data.get('assignee_id'):
            formatted['Исполнитель'] = self.format_with_id(
                issue_data.get('Исполнитель', ''),
                extra_data['assignee_id']
            )
        
        # Даты с [field_name]
        formatted['Дата создания'] = self.format_date(
            issue_data.get('Дата создания', '-'),
            'created',
            is_empty=(issue_data.get('Дата создания') in [None, '-', ''])
        )
        formatted['Дата исполнения'] = self.format_date(
            issue_data.get('Дата исполнения', '-'),
            'duedate',
            is_empty=(issue_data.get('Дата исполнения') in [None, '-', ''])
        )
        formatted['Дата решения'] = self.format_date(
            issue_data.get('Дата решения', '-'),
            'resolutiondate',
            is_empty=(issue_data.get('Дата решения') in [None, '-', ''])
        )
        
        # Числа с [field_name]
        formatted['Факт (ч)'] = self.format_number(
            issue_data.get('Факт (ч)', 0.0),
            'timespent'
        )
        formatted['Оценка (ч)'] = self.format_number(
            issue_data.get('Оценка (ч)', 0.0),
            'timeoriginalestimate'
        )
        
        return formatted
