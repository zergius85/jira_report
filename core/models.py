# -*- coding: utf-8 -*-
"""
Модели базы данных для системы отчётов Jira.

Хранение истории отчётов, комментариев и метрик.
"""
from datetime import datetime
from typing import Optional, Dict, Any
import json
import os

from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, 
    Float, Boolean, Text, ForeignKey, JSON, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

Base = declarative_base()


class ReportHistory(Base):
    """
    История сгенерированных отчётов.
    
    Позволяет сравнивать периоды, отслеживать динамику.
    """
    __tablename__ = 'report_history'
    
    id = Column(Integer, primary_key=True)
    
    # Параметры отчёта
    period = Column(String(100), nullable=False)  # "2024-01-01 — 2024-01-31"
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=False)
    
    # Фильтры
    projects = Column(JSON, default=list)  # Список ключей проектов
    assignees = Column(JSON, default=list)  # Список исполнителей
    issue_types = Column(JSON, default=list)  # Список типов задач
    
    # Статистика
    total_projects = Column(Integer, default=0)
    total_tasks = Column(Integer, default=0)
    total_correct = Column(Integer, default=0)
    total_issues = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    total_estimated = Column(Float, default=0.0)
    
    # Данные для графиков (агрегированные)
    chart_data = Column(JSON, default=dict)  # Сериализованные данные графиков
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.now, index=True)
    created_by = Column(String(100), default='system')  # Пользователь или 'system'
    report_type = Column(String(50), default='regular')  # regular, scheduled, manual
    
    # Ссылки на файлы
    excel_path = Column(String(500))  # Путь к Excel файлу
    pdf_path = Column(String(500))    # Путь к PDF файлу
    
    # Комментарии
    comments = relationship('ReportComment', back_populates='report', cascade='all, delete-orphan')
    
    # Индексы для быстрого поиска
    __table_args__ = (
        Index('idx_period', 'period'),
        Index('idx_created_at', 'created_at'),
        Index('idx_report_type', 'report_type'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return {
            'id': self.id,
            'period': self.period,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'projects': self.projects or [],
            'assignees': self.assignees or [],
            'issue_types': self.issue_types or [],
            'total_projects': self.total_projects,
            'total_tasks': self.total_tasks,
            'total_correct': self.total_correct,
            'total_issues': self.total_issues,
            'total_spent': round(self.total_spent, 2),
            'total_estimated': round(self.total_estimated, 2),
            'chart_data': self.chart_data or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by,
            'report_type': self.report_type,
            'has_excel': bool(self.excel_path),
            'has_pdf': bool(self.pdf_path),
            'comments_count': len(self.comments),
        }
    
    def __repr__(self):
        return f"<ReportHistory(id={self.id}, period='{self.period}', created_at={self.created_at})>"


class ReportComment(Base):
    """
    Комментарии к отчётам.
    
    Позволяют добавлять заметки к конкретным отчётам.
    """
    __tablename__ = 'report_comments'
    
    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey('report_history.id'), nullable=False)
    
    # Текст комментария
    text = Column(Text, nullable=False)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(String(100), default='system')
    is_pinned = Column(Boolean, default=False)  # Закреплённый комментарий
    
    # Связи
    report = relationship('ReportHistory', back_populates='comments')
    
    __table_args__ = (
        Index('idx_report_id', 'report_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return {
            'id': self.id,
            'report_id': self.report_id,
            'text': self.text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by,
            'is_pinned': self.is_pinned,
        }
    
    def __repr__(self):
        return f"<ReportComment(id={self.id}, report_id={self.report_id})>"


class ScheduledReport(Base):
    """
    Расписание автоматических отчётов.
    
    Хранит настройки для периодической генерации отчётов.
    """
    __tablename__ = 'scheduled_reports'
    
    id = Column(Integer, primary_key=True)
    
    # Название расписания
    name = Column(String(100), nullable=False)
    
    # Параметры отчёта
    projects = Column(JSON, default=list)
    assignees = Column(JSON, default=list)
    issue_types = Column(JSON, default=list)
    blocks = Column(JSON, default=list)
    days = Column(Integer, default=30)  # Период в днях
    
    # Расписание (cron-like)
    schedule_type = Column(String(20), default='weekly')  # daily, weekly, monthly
    schedule_day = Column(Integer)  # День недели (0-6) или день месяца (1-31)
    schedule_hour = Column(Integer, default=9)  # Час отправки (0-23)
    
    # Получатели
    email_recipients = Column(JSON, default=list)  # Список email
    telegram_chats = Column(JSON, default=list)    # Список chat_id
    
    # Настройки
    is_active = Column(Boolean, default=True)
    send_excel = Column(Boolean, default=True)
    send_pdf = Column(Boolean, default=False)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.now)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    
    __table_args__ = (
        Index('idx_schedule_active', 'is_active'),
        Index('idx_schedule_next_run', 'next_run'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return {
            'id': self.id,
            'name': self.name,
            'projects': self.projects or [],
            'assignees': self.assignees or [],
            'issue_types': self.issue_types or [],
            'blocks': self.blocks or [],
            'days': self.days,
            'schedule_type': self.schedule_type,
            'schedule_day': self.schedule_day,
            'schedule_hour': self.schedule_hour,
            'email_recipients': self.email_recipients or [],
            'telegram_chats': self.telegram_chats or [],
            'is_active': self.is_active,
            'send_excel': self.send_excel,
            'send_pdf': self.send_pdf,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
        }
    
    def __repr__(self):
        return f"<ScheduledReport(id={self.id}, name='{self.name}', active={self.is_active})>"


class TelegramSubscription(Base):
    """
    Подписки на Telegram-уведомления.
    
    Хранит информацию о пользователях, подписанных на алёрты.
    """
    __tablename__ = 'telegram_subscriptions'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(String(50), nullable=False, unique=True)
    username = Column(String(100))
    
    # Настройки уведомлений
    notify_risk_zone = Column(Boolean, default=True)  # Risk Zone алёрты
    notify_scheduled = Column(Boolean, default=True)  # Запланированные отчёты
    threshold_days = Column(Integer, default=7)  # Порог для Risk Zone (дни)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_telegram_active', 'is_active'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'username': self.username,
            'notify_risk_zone': self.notify_risk_zone,
            'notify_scheduled': self.notify_scheduled,
            'threshold_days': self.threshold_days,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
        }
    
    def __repr__(self):
        return f"<TelegramSubscription(chat_id='{self.chat_id}', active={self.is_active})>"


# =============================================
# Управление базой данных
# =============================================

def get_database_url() -> str:
    """
    Возвращает URL базы данных из переменных окружения.
    
    По умолчанию используется SQLite в корне проекта.
    """
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url
    
    # SQLite по умолчанию
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'jira_report.db')
    return f'sqlite:///{db_path}'


def init_db() -> None:
    """
    Инициализирует базу данных, создаёт все таблицы.
    """
    engine = create_engine(get_database_url(), echo=False)
    Base.metadata.create_all(engine)


def get_session():
    """
    Возвращает сессию базы данных.
    
    Usage:
        session = get_session()
        try:
            # работа с БД
            session.commit()
        finally:
            session.close()
    """
    engine = create_engine(get_database_url(), echo=False)
    Session = sessionmaker(bind=engine)
    return Session()


# Для удобства импорта
__all__ = [
    'Base',
    'ReportHistory',
    'ReportComment', 
    'ScheduledReport',
    'TelegramSubscription',
    'get_database_url',
    'init_db',
    'get_session',
]
