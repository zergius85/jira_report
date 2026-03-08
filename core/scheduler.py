# -*- coding: utf-8 -*-
"""
Планировщик задач для автоматической генерации отчётов.

Использует APScheduler для cron-подобного расписания.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import asyncio
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.config import (
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM,
    TELEGRAM_BOT_TOKEN, IS_PRODUCTION
)
from core.models import get_session, ScheduledReport
from core.report_service import (
    save_report, get_active_scheduled_reports,
    update_scheduled_report_last_run, subscribe_telegram
)
from core.jira_report import generate_report, generate_excel
from core.pdf_export import generate_pdf_report
from core.telegram_bot import send_scheduled_report_notification, send_telegram_message_sync

logger = logging.getLogger(__name__)

# Глобальный планировщик
_scheduler: Optional[BackgroundScheduler] = None


def init_scheduler() -> bool:
    """
    Инициализирует планировщик задач.
    
    Returns:
        bool: True если успешно
    """
    global _scheduler
    
    try:
        _scheduler = BackgroundScheduler(
            timezone='Europe/Moscow',  # Настройте под ваш часовой пояс
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 3600,  # 1 час
            }
        )
        
        # Загружаем расписания из БД
        _load_scheduled_jobs()
        
        _scheduler.start()
        logger.info("✅ Планировщик задач запущен")
        return True
    
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации планировщика: {e}", exc_info=True)
        return False


def shutdown_scheduler() -> bool:
    """
    Останавливает планировщик задач.
    
    Returns:
        bool: True если успешно
    """
    global _scheduler
    
    if _scheduler:
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("✅ Планировщик задач остановлен")
        return True
    
    return False


def _load_scheduled_jobs() -> None:
    """
    Загружает задачи из базы данных в планировщик.
    """
    if not _scheduler:
        return
    
    session = get_session()
    try:
        reports = session.query(ScheduledReport).filter(
            ScheduledReport.is_active == True
        ).all()
        
        for report in reports:
            _schedule_job(report)
        
        logger.info(f"📅 Загружено {len(reports)} расписаний")
    
    finally:
        session.close()


def _schedule_job(report: ScheduledReport) -> None:
    """
    Добавляет задачу в планировщик.
    
    Args:
        report: Расписание из БД
    """
    if not _scheduler:
        return
    
    # Определяем триггер в зависимости от типа расписания
    if report.schedule_type == 'daily':
        trigger = CronTrigger(hour=report.schedule_hour, minute=0)
    elif report.schedule_type == 'weekly':
        trigger = CronTrigger(
            day_of_week=report.schedule_day if report.schedule_day is not None else 0,
            hour=report.schedule_hour,
            minute=0
        )
    elif report.schedule_type == 'monthly':
        trigger = CronTrigger(
            day=report.schedule_day if report.schedule_day is not None else 1,
            hour=report.schedule_hour,
            minute=0
        )
    else:
        logger.warning(f"⚠️  Неизвестный тип расписания: {report.schedule_type}")
        return
    
    # Добавляем задачу
    _scheduler.add_job(
        _execute_scheduled_report,
        trigger=trigger,
        id=f'scheduled_report_{report.id}',
        name=report.name,
        args=[report.id],
        replace_existing=True,
    )
    
    logger.info(f"📅 Добавлено расписание: {report.name} (ID={report.id})")


def add_scheduled_job(report_id: int) -> bool:
    """
    Добавляет новое расписание в планировщик.
    
    Args:
        report_id: ID расписания в БД
    
    Returns:
        bool: True если успешно
    """
    if not _scheduler:
        logger.error("❌ Планировщик не инициализирован")
        return False
    
    session = get_session()
    try:
        report = session.query(ScheduledReport).filter(
            ScheduledReport.id == report_id
        ).first()
        
        if report and report.is_active:
            _schedule_job(report)
            return True
        
        return False
    
    finally:
        session.close()


def remove_scheduled_job(report_id: int) -> bool:
    """
    Удаляет расписание из планировщика.
    
    Args:
        report_id: ID расписания в БД
    
    Returns:
        bool: True если успешно
    """
    if not _scheduler:
        return False
    
    try:
        job_id = f'scheduled_report_{report_id}'
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)
            logger.info(f"🗑️ Удалено расписание: ID={report_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка удаления расписания: {e}")
        return False


def _execute_scheduled_report(report_id: int) -> None:
    """
    Выполняет сгенерированный отчёт по расписанию.
    
    Args:
        report_id: ID расписания в БД
    """
    logger.info(f"🚀 Запуск отчёта по расписанию: ID={report_id}")
    
    session = get_session()
    try:
        report = session.query(ScheduledReport).filter(
            ScheduledReport.id == report_id
        ).first()
        
        if not report:
            logger.error(f"❌ Расписание не найдено: ID={report_id}")
            return
        
        # Генерируем отчёт
        report_data = generate_report(
            project_keys=report.projects,
            assignees=report.assignees,
            issue_types=report.issue_types,
            blocks=report.blocks,
            days=report.days,
            verbose=False,
        )
        
        # Сохраняем в БД
        period = report_data.get('period', '')
        start_date, end_date = period.split(' — ') if ' — ' in period else (None, None)
        
        totals = {
            'projects': report_data.get('total_projects', 0),
            'tasks': report_data.get('total_tasks', 0),
            'correct': report_data.get('total_correct', 0),
            'issues': report_data.get('total_issues', 0),
            'spent': report_data.get('total_spent', 0),
            'estimated': report_data.get('total_estimated', 0),
        }
        
        # Сохраняем Excel
        excel_filename = f"scheduled_{report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_path = os.path.join('reports', excel_filename)
        generate_excel(report_data, excel_path)
        
        # Сохраняем PDF если нужно
        pdf_path = None
        if report.send_pdf:
            pdf_filename = f"scheduled_{report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_bytes = generate_pdf_report(report_data, pdf_filename)
            if pdf_bytes:
                pdf_path = os.path.join('reports', pdf_filename)
        
        # Сохраняем историю
        saved_report = save_report(
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_projects=totals['projects'],
            total_tasks=totals['tasks'],
            total_correct=totals['correct'],
            total_issues=totals['issues'],
            total_spent=totals['spent'],
            total_estimated=totals['estimated'],
            projects=report.projects,
            assignees=report.assignees,
            issue_types=report.issue_types,
            created_by='scheduler',
            report_type='scheduled',
            excel_path=excel_path,
            pdf_path=pdf_path,
        )
        
        # Отправляем по email
        if report.email_recipients and report.send_excel:
            _send_email_report(
                report.email_recipients,
                period,
                totals,
                excel_path,
                pdf_path if report.send_pdf else None,
            )
        
        # Отправляем в Telegram
        if report.telegram_chats:
            asyncio.run(
                send_scheduled_report_notification(
                    report_url=f"/report/{saved_report.id}" if saved_report else "",
                    period=period,
                    totals=totals,
                )
            )
        
        # Обновляем время последнего запуска
        next_run = _calculate_next_run(report)
        update_scheduled_report_last_run(report_id, next_run)
        
        logger.info(f"✅ Отчёт по расписанию выполнен: ID={report_id}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения отчёта по расписанию: {e}", exc_info=True)
    
    finally:
        session.close()


def _calculate_next_run(report: ScheduledReport) -> Optional[datetime]:
    """
    Вычисляет время следующего запуска.
    
    Args:
        report: Расписание
    
    Returns:
        datetime: Время следующего запуска
    """
    now = datetime.now()
    
    if report.schedule_type == 'daily':
        return now + timedelta(days=1)
    elif report.schedule_type == 'weekly':
        return now + timedelta(weeks=1)
    elif report.schedule_type == 'monthly':
        return now + timedelta(days=30)
    
    return None


def _send_email_report(
    recipients: list,
    period: str,
    totals: Dict[str, Any],
    excel_path: str,
    pdf_path: Optional[str] = None,
) -> bool:
    """
    Отправляет отчёт по email.
    
    Args:
        recipients: Список email получателей
        period: Период отчёта
        totals: Статистика отчёта
        excel_path: Путь к Excel файлу
        pdf_path: Путь к PDF файлу
    
    Returns:
        bool: True если успешно
    """
    if not SMTP_USER or not SMTP_PASS:
        logger.error("❌ SMTP не настроен")
        return False
    
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        
        # Создаём письмо
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f'Jira Report — {period}'
        
        # Тело письма
        body = f"""
<html>
<body>
    <h2>📊 Jira Report</h2>
    <p>Период: <b>{period}</b></p>
    
    <h3>Статистика:</h3>
    <ul>
        <li>Проектов: {totals.get('projects', 0)}</li>
        <li>Задач: {totals.get('tasks', 0)}</li>
        <li>Корректных: {totals.get('correct', 0)}</li>
        <li>Проблемных: {totals.get('issues', 0)}</li>
        <li>Факт часов: {totals.get('spent', 0):.1f}</li>
    </ul>
    
    <p>Отчёт сформирован автоматически системой Jira Report.</p>
</body>
</html>
        """.strip()
        
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        # Прикрепляем Excel
        if excel_path and os.path.exists(excel_path):
            with open(excel_path, 'rb') as f:
                part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{os.path.basename(excel_path)}"',
                )
                msg.attach(part)
        
        # Прикрепляем PDF
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                part = MIMEBase('application', 'pdf')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{os.path.basename(pdf_path)}"',
                )
                msg.attach(part)
        
        # Отправляем
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"✅ Отчёт отправлен по email: {len(recipients)} получателей")
        return True
    
    except Exception as e:
        logger.error(f"❌ Ошибка отправки email: {e}", exc_info=True)
        return False


def send_risk_zone_alert(risk_tasks: list, threshold_days: int = 7) -> int:
    """
    Отправляет алёрт о Risk Zone подписчикам.
    
    Args:
        risk_tasks: Список рисковых задач
        threshold_days: Порог дней
    
    Returns:
        int: Количество отправленных уведомлений
    """
    if not risk_tasks:
        return 0
    
    from core.telegram_bot import send_risk_zone_alert
    
    # Запускаем асинхронную функцию
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        send_risk_zone_alert(risk_tasks, threshold_days)
    )


def get_scheduler_status() -> Dict[str, Any]:
    """
    Возвращает статус планировщика.
    
    Returns:
        Dict: Статус планировщика
    """
    if not _scheduler:
        return {'running': False, 'jobs': []}
    
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
        })
    
    return {
        'running': True,
        'jobs': jobs,
    }
