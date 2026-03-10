# -*- coding: utf-8 -*-
"""
JQL Builder — безопасное построение JQL-запросов.

Модуль для конструирования JQL-запросов с валидацией параметров.
"""
from typing import Optional, List
from datetime import datetime

# Импортируем утилиты санитизации
from core.utils import sanitize_jql_identifier, sanitize_jql_string_literal


class JQLBuilder:
    """
    Конструктор JQL-запросов с валидацией и санитизацией параметров.
    
    Пример использования:
        jql = (JQLBuilder()
            .project('WEB')
            .status_not_in(['Closed', 'Done'])
            .duedate_between('2024-01-01', '2024-12-31')
            .assignee_in(['ivanov', 'petrov'])
            .order_by('duedate', asc=True)
            .build())
    """

    # Разрешённые поля для сортировки
    ALLOWED_ORDER_FIELDS = {
        'created', 'updated', 'duedate', 'resolved', 'priority',
        'status', 'assignee', 'reporter', 'key', 'summary'
    }

    def __init__(self):
        self.conditions: List[str] = []
        self.order_clause: Optional[str] = None

    def project(self, key: str) -> 'JQLBuilder':
        """
        Добавляет условие по проекту.

        Args:
            key: Ключ проекта (например, 'WEB')

        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        sanitized_key = sanitize_jql_identifier(key)
        self.conditions.append(f"project = {sanitized_key}")
        return self

    def projects_in(self, keys: List[str]) -> 'JQLBuilder':
        """
        Добавляет условие по нескольким проектам.

        Args:
            keys: Список ключей проектов

        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        sanitized_keys = [sanitize_jql_identifier(k) for k in keys]
        self.conditions.append(f"project IN ({','.join(sanitized_keys)})")
        return self
    
    def status_not_in(self, statuses: List[str]) -> 'JQLBuilder':
        """
        Добавляет условие исключения статусов.
        
        Args:
            statuses: Список статусов для исключения
            
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        sanitized = [sanitize_jql_string_literal(s) for s in statuses]
        status_list = ', '.join(f"'{s}'" for s in sanitized)
        self.conditions.append(f"status NOT IN ({status_list})")
        return self
    
    def status_in(self, statuses: List[str]) -> 'JQLBuilder':
        """
        Добавляет условие по статусам.
        
        Args:
            statuses: Список статусов
            
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        sanitized = [sanitize_jql_string_literal(s) for s in statuses]
        status_list = ', '.join(f"'{s}'" for s in sanitized)
        self.conditions.append(f"status IN ({status_list})")
        return self
    
    def duedate_between(self, start: str, end: str) -> 'JQLBuilder':
        """
        Добавляет условие по диапазону дат исполнения.
        
        Args:
            start: Начальная дата (YYYY-MM-DD)
            end: Конечная дата (YYYY-MM-DD)
            
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        # Валидация формата даты
        try:
            datetime.strptime(start, '%Y-%m-%d')
            datetime.strptime(end, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Дата должна быть в формате YYYY-MM-DD")
        
        self.conditions.append(f"duedate >= '{start}' AND duedate <= '{end}'")
        return self
    
    def created_between(self, start: str, end: str) -> 'JQLBuilder':
        """
        Добавляет условие по диапазону дат создания.
        
        Args:
            start: Начальная дата (YYYY-MM-DD)
            end: Конечная дата (YYYY-MM-DD)
            
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        try:
            datetime.strptime(start, '%Y-%m-%d')
            datetime.strptime(end, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Дата должна быть в формате YYYY-MM-DD")
        
        self.conditions.append(f"created >= '{start}' AND created <= '{end}'")
        return self
    
    def resolved_between(self, start: str, end: str) -> 'JQLBuilder':
        """
        Добавляет условие по диапазону дат решения.
        
        Args:
            start: Начальная дата (YYYY-MM-DD)
            end: Конечная дата (YYYY-MM-DD)
            
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        try:
            datetime.strptime(start, '%Y-%m-%d')
            datetime.strptime(end, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Дата должна быть в формате YYYY-MM-DD")
        
        self.conditions.append(f"resolved >= '{start}' AND resolved <= '{end}'")
        return self
    
    def assignee_in(self, assignees: List[str]) -> 'JQLBuilder':
        """
        Добавляет условие по исполнителям.
        
        Args:
            assignees: Список исполнителей (username или key)
            
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        if not assignees:
            return self
        
        sanitized = [sanitize_jql_identifier(a) for a in assignees]
        self.conditions.append(f"assignee IN ({','.join(sanitized)})")
        return self
    
    def assignee_is_empty(self) -> 'JQLBuilder':
        """
        Добавляет условие 'без исполнителя'.
        
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        self.conditions.append("assignee is EMPTY")
        return self
    
    def updated_before(self, days: int) -> 'JQLBuilder':
        """
        Добавляет условие 'не обновлялось более N дней'.
        
        Args:
            days: Количество дней
            
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        if days < 0:
            raise ValueError("Количество дней должно быть неотрицательным")
        
        self.conditions.append(f"updated < -{days}d")
        return self
    
    def issuetype_in(self, types: List[str]) -> 'JQLBuilder':
        """
        Добавляет условие по типам задач.
        
        Args:
            types: Список типов задач
            
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        sanitized = [sanitize_jql_string_literal(t) for t in types]
        type_list = ', '.join(f"'{t}'" for t in sanitized)
        self.conditions.append(f"issuetype IN ({type_list})")
        return self
    
    def order_by(self, field: str, asc: bool = True) -> 'JQLBuilder':
        """
        Добавляет сортировку.
        
        Args:
            field: Поле для сортировки
            asc: По возрастанию (True) или убыванию (False)
            
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        if field not in self.ALLOWED_ORDER_FIELDS:
            raise ValueError(
                f"Недопустимое поле для сортировки: {field}. "
                f"Разрешённые: {', '.join(self.ALLOWED_ORDER_FIELDS)}"
            )
        
        direction = 'ASC' if asc else 'DESC'
        self.order_clause = f"ORDER BY {field} {direction}"
        return self
    
    def build(self) -> str:
        """
        Строит итоговый JQL-запрос.

        Returns:
            str: Готовый JQL-запрос
        """
        if not self.conditions and not self.order_clause:
            return ''

        jql = ' AND '.join(self.conditions) if self.conditions else ''

        if self.order_clause:
            if jql:
                jql += f' {self.order_clause}'
            else:
                jql = self.order_clause

        return jql
    
    def reset(self) -> 'JQLBuilder':
        """
        Сбрасывает все условия.
        
        Returns:
            JQLBuilder: self для цепочки вызовов
        """
        self.conditions = []
        self.order_clause = None
        return self
