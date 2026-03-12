# -*- coding: utf-8 -*-
"""
Сервис для управления историей отчётов.

Работа с базой данных: сохранение, загрузка, сравнение отчётов.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import json
import os

from sqlalchemy import desc, and_, or_
from sqlalchemy.orm import joinedload

from core.models import (
    get_session, ReportHistory, ReportComment, 
    ScheduledReport, TelegramSubscription, init_db
)

logger = logging.getLogger(__name__)


# =============================================
# Инициализация БД
# =============================================

def initialize_database() -> bool:
    """
    Инициализирует базу данных.
    
    Returns:
        bool: True если успешно
    """
    try:
        init_db()
        logger.info("✅ База данных инициализирована")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        return False


# =============================================
# ReportHistory — История отчётов
# =============================================

def save_report(
    period: str,
    start_date: str,
    end_date: str,
    total_projects: int,
    total_tasks: int,
    total_correct: int,
    total_issues: int,
    total_spent: float,
    total_estimated: float,
    chart_data: Optional[Dict] = None,
    projects: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None,
    issue_types: Optional[List[str]] = None,
    created_by: str = 'system',
    report_type: str = 'regular',
    excel_path: Optional[str] = None,
    pdf_path: Optional[str] = None,
) -> Optional[ReportHistory]:
    """
    Сохраняет отчёт в базу данных.
    
    Args:
        period: Строка периода ("2024-01-01 — 2024-01-31")
        start_date: Дата начала (YYYY-MM-DD)
        end_date: Дата окончания (YYYY-MM-DD)
        total_projects: Всего проектов
        total_tasks: Всего задач
        total_correct: Корректных задач
        total_issues: Проблемных задач
        total_spent: Фактически затрачено часов
        total_estimated: Оценено часов
        chart_data: Данные для графиков
        projects: Список проектов
        assignees: Список исполнителей
        issue_types: Список типов задач
        created_by: Кто создал отчёт
        report_type: Тип отчёта (regular, scheduled, manual)
        excel_path: Путь к Excel файлу
        pdf_path: Путь к PDF файлу
    
    Returns:
        ReportHistory: Сохранённый отчёт или None
    """
    session = get_session()
    try:
        report = ReportHistory(
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_projects=total_projects,
            total_tasks=total_tasks,
            total_correct=total_correct,
            total_issues=total_issues,
            total_spent=total_spent,
            total_estimated=total_estimated,
            chart_data=chart_data or {},
            projects=projects or [],
            assignees=assignees or [],
            issue_types=issue_types or [],
            created_by=created_by,
            report_type=report_type,
            excel_path=excel_path,
            pdf_path=pdf_path,
        )
        session.add(report)
        session.commit()
        session.refresh(report)
        logger.info(f"✅ Отчёт сохранён: ID={report.id}, period={period}")
        return report
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка сохранения отчёта: {e}")
        return None
    finally:
        session.close()


def get_report_by_id(report_id: int) -> Optional[ReportHistory]:
    """
    Получает отчёт по ID.
    
    Args:
        report_id: ID отчёта
    
    Returns:
        ReportHistory: Отчёт или None
    """
    session = get_session()
    try:
        report = session.query(ReportHistory).filter(
            ReportHistory.id == report_id
        ).options(joinedload(ReportHistory.comments)).first()
        return report
    finally:
        session.close()


def get_reports_list(
    limit: int = 50,
    offset: int = 0,
    report_type: Optional[str] = None,
    project_key: Optional[str] = None,
) -> List[ReportHistory]:
    """
    Получает список отчётов с фильтрацией.
    
    Args:
        limit: Максимум записей
        offset: Смещение
        report_type: Фильтр по типу отчёта
        project_key: Фильтр по проекту (входит в список проектов)
    
    Returns:
        List[ReportHistory]: Список отчётов
    """
    session = get_session()
    try:
        query = session.query(ReportHistory)
        
        if report_type:
            query = query.filter(ReportHistory.report_type == report_type)
        
        if project_key:
            # Ищем отчёты где проект содержится в JSON списке
            query = query.filter(
                or_(
                    ReportHistory.projects.contains([project_key]),
                    ReportHistory.projects == None,
                    ReportHistory.projects == []
                )
            )
        
        reports = query.order_by(
            desc(ReportHistory.created_at)
        ).limit(limit).offset(offset).all()
        
        return reports
    finally:
        session.close()


def get_previous_report(
    current_start_date: str,
    current_end_date: str,
    projects: Optional[List[str]] = None,
) -> Optional[ReportHistory]:
    """
    Получает предыдущий отчёт за такой же период.
    
    Args:
        current_start_date: Текущая дата начала
        current_end_date: Текущая дата окончания
        projects: Список проектов
    
    Returns:
        ReportHistory: Предыдущий отчёт или None
    """
    session = get_session()
    try:
        # Вычисляем предыдущий период
        start = datetime.strptime(current_start_date, '%Y-%m-%d')
        end = datetime.strptime(current_end_date, '%Y-%m-%d')
        delta = end - start
        
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - delta
        
        query = session.query(ReportHistory)
        query = query.filter(
            and_(
                ReportHistory.start_date <= prev_end.strftime('%Y-%m-%d'),
                ReportHistory.end_date >= prev_start.strftime('%Y-%m-%d'),
            )
        )
        
        if projects:
            # Фильтр по проектам
            query = query.filter(
                or_(
                    ReportHistory.projects.contains(projects),
                    ReportHistory.projects == None,
                    ReportHistory.projects == []
                )
            )
        
        report = query.order_by(desc(ReportHistory.created_at)).first()
        return report
    finally:
        session.close()


def compare_reports(
    report1_id: int,
    report2_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Сравнивает два отчёта.
    
    Args:
        report1_id: ID первого отчёта
        report2_id: ID второго отчёта
    
    Returns:
        Dict: Сравнение метрик или None
    """
    session = get_session()
    try:
        report1 = session.query(ReportHistory).filter(ReportHistory.id == report1_id).first()
        report2 = session.query(ReportHistory).filter(ReportHistory.id == report2_id).first()
        
        if not report1 or not report2:
            return None
        
        def calc_change(current, previous):
            if previous == 0:
                return 0 if current == 0 else 100
            return round(((current - previous) / previous) * 100, 1)
        
        comparison = {
            'report1': report1.to_dict(),
            'report2': report2.to_dict(),
            'changes': {
                'total_projects': {
                    'current': report1.total_projects,
                    'previous': report2.total_projects,
                    'change': calc_change(report1.total_projects, report2.total_projects),
                },
                'total_tasks': {
                    'current': report1.total_tasks,
                    'previous': report2.total_tasks,
                    'change': calc_change(report1.total_tasks, report2.total_tasks),
                },
                'total_correct': {
                    'current': report1.total_correct,
                    'previous': report2.total_correct,
                    'change': calc_change(report1.total_correct, report2.total_correct),
                },
                'total_issues': {
                    'current': report1.total_issues,
                    'previous': report2.total_issues,
                    'change': calc_change(report1.total_issues, report2.total_issues),
                },
                'total_spent': {
                    'current': round(report1.total_spent, 2),
                    'previous': round(report2.total_spent, 2),
                    'change': calc_change(report1.total_spent, report2.total_spent),
                },
                'total_estimated': {
                    'current': round(report1.total_estimated, 2),
                    'previous': round(report2.total_estimated, 2),
                    'change': calc_change(report1.total_estimated, report2.total_estimated),
                },
            }
        }
        
        return comparison
    finally:
        session.close()


def delete_report(report_id: int) -> bool:
    """
    Удаляет отчёт по ID.
    
    Args:
        report_id: ID отчёта
    
    Returns:
        bool: True если успешно
    """
    session = get_session()
    try:
        report = session.query(ReportHistory).filter(ReportHistory.id == report_id).first()
        if report:
            session.delete(report)
            session.commit()
            logger.info(f"✅ Отчёт удалён: ID={report_id}")
            return True
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка удаления отчёта: {e}")
        return False
    finally:
        session.close()


# =============================================
# ReportComment — Комментарии
# =============================================

def add_comment(
    report_id: int,
    text: str,
    created_by: str = 'system',
    is_pinned: bool = False,
) -> Optional[ReportComment]:
    """
    Добавляет комментарий к отчёту.
    
    Args:
        report_id: ID отчёта
        text: Текст комментария
        created_by: Автор комментария
        is_pinned: Закрепить комментарий
    
    Returns:
        ReportComment: Комментарий или None
    """
    session = get_session()
    try:
        comment = ReportComment(
            report_id=report_id,
            text=text,
            created_by=created_by,
            is_pinned=is_pinned,
        )
        session.add(comment)
        session.commit()
        session.refresh(comment)
        logger.info(f"✅ Комментарий добавлен: ID={comment.id}, report_id={report_id}")
        return comment
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка добавления комментария: {e}")
        return None
    finally:
        session.close()


def get_comments(report_id: int) -> List[ReportComment]:
    """
    Получает комментарии отчёта.
    
    Args:
        report_id: ID отчёта
    
    Returns:
        List[ReportComment]: Список комментариев
    """
    session = get_session()
    try:
        comments = session.query(ReportComment).filter(
            ReportComment.report_id == report_id
        ).order_by(ReportComment.is_pinned.desc(), ReportComment.created_at).all()
        return comments
    finally:
        session.close()


def delete_comment(comment_id: int) -> bool:
    """
    Удаляет комментарий.
    
    Args:
        comment_id: ID комментария
    
    Returns:
        bool: True если успешно
    """
    session = get_session()
    try:
        comment = session.query(ReportComment).filter(ReportComment.id == comment_id).first()
        if comment:
            session.delete(comment)
            session.commit()
            logger.info(f"✅ Комментарий удалён: ID={comment_id}")
            return True
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка удаления комментария: {e}")
        return False
    finally:
        session.close()


# =============================================
# ScheduledReport — Расписание отчётов
# =============================================

def create_scheduled_report(
    name: str,
    schedule_type: str = 'weekly',
    schedule_day: Optional[int] = None,
    schedule_hour: int = 9,
    projects: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None,
    issue_types: Optional[List[str]] = None,
    blocks: Optional[List[str]] = None,
    days: int = 30,
    email_recipients: Optional[List[str]] = None,
    telegram_chats: Optional[List[str]] = None,
    send_excel: bool = True,
    send_pdf: bool = False,
) -> Optional[ScheduledReport]:
    """
    Создаёт расписание для автоматического отчёта.
    
    Args:
        name: Название расписания
        schedule_type: Тип расписания (daily, weekly, monthly)
        schedule_day: День недели (0-6) или день месяца (1-31)
        schedule_hour: Час отправки
        projects: Проекты
        assignees: Исполнители
        issue_types: Типы задач
        blocks: Блоки отчёта
        days: Период в днях
        email_recipients: Email получатели
        telegram_chats: Telegram чаты
        send_excel: Отправлять Excel
        send_pdf: Отправлять PDF
    
    Returns:
        ScheduledReport: Расписание или None
    """
    session = get_session()
    try:
        scheduled = ScheduledReport(
            name=name,
            schedule_type=schedule_type,
            schedule_day=schedule_day,
            schedule_hour=schedule_hour,
            projects=projects or [],
            assignees=assignees or [],
            issue_types=issue_types or [],
            blocks=blocks or [],
            days=days,
            email_recipients=email_recipients or [],
            telegram_chats=telegram_chats or [],
            send_excel=send_excel,
            send_pdf=send_pdf,
        )
        session.add(scheduled)
        session.commit()
        session.refresh(scheduled)
        logger.info(f"✅ Расписание создано: ID={scheduled.id}, name={name}")
        return scheduled
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка создания расписания: {e}")
        return None
    finally:
        session.close()


def get_active_scheduled_reports() -> List[ScheduledReport]:
    """
    Получает активные расписания.
    
    Returns:
        List[ScheduledReport]: Список расписаний
    """
    session = get_session()
    try:
        reports = session.query(ScheduledReport).filter(
            ScheduledReport.is_active == True
        ).all()
        return reports
    finally:
        session.close()


def update_scheduled_report_last_run(
    report_id: int,
    next_run: Optional[datetime] = None,
) -> bool:
    """
    Обновляет время последнего запуска расписания.
    
    Args:
        report_id: ID расписания
        next_run: Время следующего запуска
    
    Returns:
        bool: True если успешно
    """
    session = get_session()
    try:
        report = session.query(ScheduledReport).filter(
            ScheduledReport.id == report_id
        ).first()
        if report:
            report.last_run = datetime.now()
            report.next_run = next_run
            session.commit()
            logger.info(f"✅ Расписание обновлено: ID={report_id}")
            return True
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка обновления расписания: {e}")
        return False
    finally:
        session.close()


def toggle_scheduled_report(report_id: int) -> Optional[bool]:
    """
    Переключает статус расписания.
    
    Args:
        report_id: ID расписания
    
    Returns:
        bool: Новый статус или None
    """
    session = get_session()
    try:
        report = session.query(ScheduledReport).filter(
            ScheduledReport.id == report_id
        ).first()
        if report:
            report.is_active = not report.is_active
            session.commit()
            logger.info(f"✅ Расписание переключено: ID={report_id}, active={report.is_active}")
            return report.is_active
        return None
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка переключения расписания: {e}")
        return None
    finally:
        session.close()


# =============================================
# TelegramSubscription — Telegram подписки
# =============================================

def subscribe_telegram(
    chat_id: str,
    username: Optional[str] = None,
    notify_risk_zone: bool = True,
    notify_scheduled: bool = True,
    threshold_days: int = 7,
) -> Optional[TelegramSubscription]:
    """
    Подписывает Telegram чат на уведомления.
    
    Args:
        chat_id: ID чата
        username: Имя пользователя
        notify_risk_zone: Уведомлять о Risk Zone
        notify_scheduled: Уведомлять о запланированных отчётах
        threshold_days: Порог для Risk Zone
    
    Returns:
        TelegramSubscription: Подписка или None
    """
    session = get_session()
    try:
        # Проверяем существующую подписку
        existing = session.query(TelegramSubscription).filter(
            TelegramSubscription.chat_id == chat_id
        ).first()
        
        if existing:
            existing.is_active = True
            existing.username = username or existing.username
            existing.notify_risk_zone = notify_risk_zone
            existing.notify_scheduled = notify_scheduled
            existing.threshold_days = threshold_days
            session.commit()
            logger.info(f"✅ Подписка обновлена: chat_id={chat_id}")
            return existing
        
        subscription = TelegramSubscription(
            chat_id=chat_id,
            username=username,
            notify_risk_zone=notify_risk_zone,
            notify_scheduled=notify_scheduled,
            threshold_days=threshold_days,
        )
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        logger.info(f"✅ Подписка создана: chat_id={chat_id}")
        return subscription
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка подписки Telegram: {e}")
        return None
    finally:
        session.close()


def unsubscribe_telegram(chat_id: str) -> bool:
    """
    Отписывает Telegram чат от уведомлений.
    
    Args:
        chat_id: ID чата
    
    Returns:
        bool: True если успешно
    """
    session = get_session()
    try:
        subscription = session.query(TelegramSubscription).filter(
            TelegramSubscription.chat_id == chat_id
        ).first()
        
        if subscription:
            subscription.is_active = False
            session.commit()
            logger.info(f"✅ Подписка отключена: chat_id={chat_id}")
            return True
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка отписки Telegram: {e}")
        return False
    finally:
        session.close()


def get_active_telegram_subscriptions() -> List[TelegramSubscription]:
    """
    Получает активные Telegram подписки.
    
    Returns:
        List[TelegramSubscription]: Список подписок
    """
    session = get_session()
    try:
        subscriptions = session.query(TelegramSubscription).filter(
            TelegramSubscription.is_active == True
        ).all()
        return subscriptions
    finally:
        session.close()


# =============================================
# Экспорт/Импорт данных
# =============================================

def export_report_to_json(report_id: int) -> Optional[str]:
    """
    Экспортирует отчёт в JSON формат.
    
    Args:
        report_id: ID отчёта
    
    Returns:
        str: JSON строка или None
    """
    report = get_report_by_id(report_id)
    if not report:
        return None
    
    data = report.to_dict()
    data['comments'] = [c.to_dict() for c in report.comments]
    
    return json.dumps(data, ensure_ascii=False, indent=2)
