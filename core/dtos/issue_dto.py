# -*- coding: utf-8 -*-
"""
DTO (Data Transfer Objects) для задач Jira.

Используется для явного представления структуры данных задачи
и упрощения тестирования (вместо хрупких MockIssue).
"""
from dataclasses import dataclass, field
from typing import Optional, Any, Dict


@dataclass
class StatusDTO:
    """DTO для статуса задачи."""
    id: str
    name: str
    status_category: str = ''  # statusCategory.key
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StatusDTO':
        """
        Создать DTO из словаря (REST API ответ).
        
        Args:
            data: Словарь с данными статуса
            
        Returns:
            StatusDTO: Экземпляр DTO
        """
        if not data:
            return cls(id='', name='', status_category='')
        
        status_category = data.get('statusCategory', {})
        if isinstance(status_category, dict):
            category_key = status_category.get('key', '')
        else:
            category_key = getattr(status_category, 'key', '')
        
        return cls(
            id=str(data.get('id', '')),
            name=str(data.get('name', '')),
            status_category=category_key
        )


@dataclass
class AssigneeDTO:
    """DTO для исполнителя задачи."""
    display_name: str = ''
    account_id: str = ''
    name: str = ''
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AssigneeDTO':
        """
        Создать DTO из словаря (REST API ответ).
        
        Args:
            data: Словарь с данными исполнителя
            
        Returns:
            AssigneeDTO: Экземпляр DTO
        """
        if not data:
            return cls(display_name='', account_id='', name='')
        
        return cls(
            display_name=str(data.get('displayName', '')),
            account_id=str(data.get('accountId', '')),
            name=str(data.get('name', ''))
        )
    
    @property
    def is_empty(self) -> bool:
        """Проверка: нет исполнителя."""
        return not self.display_name and not self.account_id and not self.name


@dataclass
class IssueTypeDTO:
    """DTO для типа задачи."""
    id: str = ''
    name: str = ''
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IssueTypeDTO':
        """
        Создать DTO из словаря (REST API ответ).
        
        Args:
            data: Словарь с данными типа задачи
            
        Returns:
            IssueTypeDTO: Экземпляр DTO
        """
        if not data:
            return cls(id='', name='')
        
        return cls(
            id=str(data.get('id', '')),
            name=str(data.get('name', ''))
        )


@dataclass
class ProjectDTO:
    """DTO для проекта."""
    id: str = ''
    key: str = ''
    name: str = ''
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectDTO':
        """
        Создать DTO из словаря (REST API ответ).
        
        Args:
            data: Словарь с данными проекта
            
        Returns:
            ProjectDTO: Экземпляр DTO
        """
        if not data:
            return cls(id='', key='', name='')
        
        return cls(
            id=str(data.get('id', '')),
            key=str(data.get('key', '')),
            name=str(data.get('name', ''))
        )


@dataclass
class PriorityDTO:
    """DTO для приоритета задачи."""
    id: str = ''
    name: str = ''
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PriorityDTO':
        """
        Создать DTO из словаря (REST API ответ).
        
        Args:
            data: Словарь с данными приоритета
            
        Returns:
            PriorityDTO: Экземпляр DTO
        """
        if not data:
            return cls(id='', name='')
        
        return cls(
            id=str(data.get('id', '')),
            name=str(data.get('name', ''))
        )


@dataclass
class IssueDTO:
    """
    DTO для задачи Jira.
    
    Используется для явного представления структуры данных задачи
    и упрощения тестирования (вместо хрупких MockIssue).
    
    Attributes:
        key: Ключ задачи (например, 'WEB-123')
        summary: Краткое описание задачи
        assignee: Исполнитель (AssigneeDTO)
        timespent: Фактическое время в секундах
        timeoriginalestimate: Оценка времени в секундах
        resolutiondate: Дата решения (ISO 8601)
        status: Статус (StatusDTO)
        created: Дата создания (ISO 8601)
        duedate: Дата исполнения (ISO 8601)
        issuetype: Тип задачи (IssueTypeDTO)
        project: Проект (ProjectDTO)
        priority: Приоритет (PriorityDTO)
        creator: Создатель (AssigneeDTO)
        updated: Дата обновления (ISO 8601)
    """
    key: str = ''
    summary: str = ''
    assignee: AssigneeDTO = field(default_factory=AssigneeDTO)
    timespent: Optional[int] = None
    timeoriginalestimate: Optional[int] = None
    resolutiondate: str = ''
    status: StatusDTO = field(default_factory=StatusDTO)
    created: str = ''
    duedate: str = ''
    issuetype: IssueTypeDTO = field(default_factory=IssueTypeDTO)
    project: ProjectDTO = field(default_factory=ProjectDTO)
    priority: PriorityDTO = field(default_factory=PriorityDTO)
    creator: AssigneeDTO = field(default_factory=AssigneeDTO)
    updated: str = ''
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IssueDTO':
        """
        Создать DTO из словаря (REST API ответ).
        
        Args:
            data: Словарь с данными задачи
            
        Returns:
            IssueDTO: Экземпляр DTO
            
        Пример:
            >>> issue_data = {'key': 'WEB-123', 'fields': {...}}
            >>> issue = IssueDTO.from_dict(issue_data)
        """
        if not data:
            return cls()
        
        fields = data.get('fields', {})
        if not fields:
            return cls(key=str(data.get('key', '')))
        
        return cls(
            key=str(data.get('key', '')),
            summary=str(fields.get('summary', '')),
            assignee=AssigneeDTO.from_dict(fields.get('assignee')),
            timespent=fields.get('timespent'),
            timeoriginalestimate=fields.get('timeoriginalestimate'),
            resolutiondate=str(fields.get('resolutiondate', '')),
            status=StatusDTO.from_dict(fields.get('status')),
            created=str(fields.get('created', '')),
            duedate=str(fields.get('duedate', '')),
            issuetype=IssueTypeDTO.from_dict(fields.get('issuetype')),
            project=ProjectDTO.from_dict(fields.get('project')),
            priority=PriorityDTO.from_dict(fields.get('priority')),
            creator=AssigneeDTO.from_dict(fields.get('creator')),
            updated=str(fields.get('updated', ''))
        )
    
    # Свойства для обратной совместимости с validate_issue()
    @property
    def fields(self) -> 'IssueFieldsWrapper':
        """
        Обёртка для полей задачи.
        
        Нужно для обратной совместимости с validate_issue(),
        которая ожидает issue.fields.xxx
        
        Returns:
            IssueFieldsWrapper: Обёртка полей
        """
        return IssueFieldsWrapper(self)


@dataclass
class IssueFieldsWrapper:
    """
    Обёртка для полей IssueDTO.
    
    Нужна для обратной совместимости с кодом, который использует
    issue.fields.assignee, issue.fields.status и т.д.
    """
    issue: IssueDTO
    
    @property
    def assignee(self) -> AssigneeDTO:
        return self.issue.assignee
    
    @property
    def timespent(self) -> Optional[int]:
        return self.issue.timespent
    
    @property
    def timeoriginalestimate(self) -> Optional[int]:
        return self.issue.timeoriginalestimate
    
    @property
    def resolutiondate(self) -> str:
        return self.issue.resolutiondate
    
    @property
    def status(self) -> StatusDTO:
        return self.issue.status
    
    @property
    def created(self) -> str:
        return self.issue.created
    
    @property
    def duedate(self) -> str:
        return self.issue.duedate
    
    @property
    def issuetype(self) -> IssueTypeDTO:
        return self.issue.issuetype
    
    @property
    def project(self) -> ProjectDTO:
        return self.issue.project
    
    @property
    def priority(self) -> PriorityDTO:
        return self.issue.priority
    
    @property
    def creator(self) -> AssigneeDTO:
        return self.issue.creator
    
    @property
    def updated(self) -> str:
        return self.issue.updated
