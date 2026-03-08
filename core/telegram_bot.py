# -*- coding: utf-8 -*-
"""
Сервис уведомлений в Telegram.

Отправка алёртов о рисковых задачах и запланированных отчётах.

Совместимость: python-telegram-bot 13.x (Python 3.7+)
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.config import TELEGRAM_BOT_TOKEN
from core.models import get_session, TelegramSubscription

logger = logging.getLogger(__name__)

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("⚠️  python-telegram-bot не установлен. Уведомления в Telegram недоступны.")


async def send_telegram_message(
    chat_id: str,
    message: str,
    parse_mode: str = 'HTML',
) -> bool:
    """
    Отправляет сообщение в Telegram.
    
    Args:
        chat_id: ID чата или пользователя
        message: Текст сообщения
        parse_mode: Режим парсинга ('HTML', 'Markdown')
    
    Returns:
        bool: True если успешно
    """
    if not TELEGRAM_AVAILABLE:
        return False
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не настроен")
        return False
    
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=parse_mode,
        )
        logger.info(f"✅ Сообщение отправлено в Telegram: chat_id={chat_id}")
        return True
    except TelegramError as e:
        logger.error(f"❌ Ошибка отправки в Telegram: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка Telegram: {e}")
        return False


async def send_risk_zone_alert(
    risk_tasks: List[Dict[str, Any]],
    threshold_days: int = 7,
) -> int:
    """
    Отправляет алёрт о задачах в Risk Zone.
    
    Args:
        risk_tasks: Список рисковых задач
        threshold_days: Порог дней для алёрта
    
    Returns:
        int: Количество отправленных уведомлений
    """
    if not risk_tasks:
        return 0
    
    session = get_session()
    try:
        subscriptions = session.query(TelegramSubscription).filter(
            TelegramSubscription.is_active == True,
            TelegramSubscription.notify_risk_zone == True
        ).all()
        
        if not subscriptions:
            logger.info("ℹ️ Нет активных подписок на Risk Zone алёрты")
            return 0
        
        # Формируем сообщение
        message = _format_risk_zone_message(risk_tasks, threshold_days)
        
        # Отправляем всем подписчикам
        sent_count = 0
        for sub in subscriptions:
            if await send_telegram_message(sub.chat_id, message):
                sent_count += 1
        
        logger.info(f"✅ Отправлено {sent_count} Risk Zone алёртов")
        return sent_count
    
    finally:
        session.close()


def _format_risk_zone_message(
    risk_tasks: List[Dict[str, Any]],
    threshold_days: int,
) -> str:
    """
    Форматирует сообщение для Risk Zone алёрта.
    
    Args:
        risk_tasks: Список рисковых задач
        threshold_days: Порог дней
    
    Returns:
        str: Форматированное сообщение
    """
    message = [
        "🔴 <b>Risk Zone Alert</b>",
        f"Обнаружено задач с факторами риска: {len(risk_tasks)}",
        "",
    ]
    
    # Группируем по факторам риска
    no_assignee = [t for t in risk_tasks if 'Без исполнителя' in t.get('risk_factors', [])]
    overdue = [t for t in risk_tasks if 'Просрочена' in t.get('risk_factors', [])]
    inactive = [t for t in risk_tasks if 'Не двигается' in t.get('risk_factors', [])]
    
    if no_assignee:
        message.append(f"<b>⚠️ Без исполнителя:</b> {len(no_assignee)}")
        for task in no_assignee[:5]:  # Показываем первые 5
            message.append(f"  • {task.get('key', 'N/A')} | {task.get('summary', 'N/A')[:40]}")
        if len(no_assignee) > 5:
            message.append(f"  ... и ещё {len(no_assignee) - 5}")
        message.append("")
    
    if overdue:
        message.append(f"<b>⏰ Просрочены:</b> {len(overdue)}")
        for task in overdue[:5]:
            message.append(f"  • {task.get('key', 'N/A')} | {task.get('summary', 'N/A')[:40]}")
        if len(overdue) > 5:
            message.append(f"  ... и ещё {len(overdue) - 5}")
        message.append("")
    
    if inactive:
        message.append(f"<b>😴 Не двигаются > {threshold_days} дней:</b> {len(inactive)}")
        for task in inactive[:5]:
            message.append(f"  • {task.get('key', 'N/A')} | {task.get('summary', 'N/A')[:40]}")
        if len(inactive) > 5:
            message.append(f"  ... и ещё {len(inactive) - 5}")
        message.append("")
    
    message.append(f"<i>Время формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>")
    
    return '\n'.join(message)


async def send_scheduled_report_notification(
    report_url: str,
    period: str,
    totals: Dict[str, Any],
) -> int:
    """
    Отправляет уведомление о готовом запланированном отчёте.
    
    Args:
        report_url: URL отчёта
        period: Период отчёта
        totals: Статистика отчёта
    
    Returns:
        int: Количество отправленных уведомлений
    """
    session = get_session()
    try:
        subscriptions = session.query(TelegramSubscription).filter(
            TelegramSubscription.is_active == True,
            TelegramSubscription.notify_scheduled == True
        ).all()
        
        if not subscriptions:
            logger.info("ℹ️ Нет активных подписок на отчёты")
            return 0
        
        message = _format_scheduled_report_message(report_url, period, totals)
        
        sent_count = 0
        for sub in subscriptions:
            if await send_telegram_message(sub.chat_id, message):
                sent_count += 1
        
        logger.info(f"✅ Отправлено {sent_count} уведомлений о отчёте")
        return sent_count
    
    finally:
        session.close()


def _format_scheduled_report_message(
    report_url: str,
    period: str,
    totals: Dict[str, Any],
) -> str:
    """
    Форматирует сообщение о запланированном отчёте.
    
    Args:
        report_url: URL отчёта
        period: Период отчёта
        totals: Статистика
    
    Returns:
        str: Форматированное сообщение
    """
    message = [
        "📊 <b>Готов новый отчёт Jira</b>",
        "",
        f"📅 Период: {period}",
        "",
        "<b>Статистика:</b>",
        f"  • Проектов: {totals.get('projects', 0)}",
        f"  • Задач: {totals.get('tasks', 0)}",
        f"  • Корректных: {totals.get('correct', 0)}",
        f"  • Проблемных: {totals.get('issues', 0)}",
        f"  • Факт часов: {totals.get('spent', 0):.1f}",
        "",
        f"🔗 <a href='{report_url}'>Открыть отчёт</a>",
        "",
        f"<i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
    ]
    
    return '\n'.join(message)


async def send_welcome_message(chat_id: str, username: Optional[str] = None) -> bool:
    """
    Отправляет приветственное сообщение новому подписчику.
    
    Args:
        chat_id: ID чата
        username: Имя пользователя
    
    Returns:
        bool: True если успешно
    """
    name = username or "пользователь"
    
    message = f"""
👋 Привет, {name}!

Я — бот для уведомлений системы Jira Report.

<b>Что я умею:</b>
• 🔴 Присылать алёрты о рисковых задачах (Risk Zone)
• 📊 Уведомлять о готовых запланированных отчётах

<b>Команды:</b>
/start — Подписаться на уведомления
/stop — Отписаться от уведомлений
/help — Помощь
/status — Мой статус подписки

Настройте уведомления в веб-интерфейсе Jira Report.
    """.strip()
    
    return await send_telegram_message(chat_id, message)


async def send_help_message(chat_id: str) -> bool:
    """
    Отправляет сообщение с помощью.
    
    Args:
        chat_id: ID чата
    
    Returns:
        bool: True если успешно
    """
    message = """
📖 <b>Помощь — Jira Report Bot</b>

<b>Доступные команды:</b>

/start — Подписаться на уведомления
/stop — Отписаться от уведомлений
/status — Проверить статус подписки
/help — Эта справка

<b>Типы уведомлений:</b>
• 🔴 Risk Zone Alert — алёрты о рисковых задачах
• 📊 Scheduled Report — уведомления о готовых отчётах

<b>Настройки:</b>
Изменить настройки уведомлений можно в веб-интерфейсе Jira Report.

<b>Вопросы:</b>
Обратитесь к администратору системы.
    """.strip()
    
    return await send_telegram_message(chat_id, message)


async def send_status_message(chat_id: str) -> bool:
    """
    Отправляет сообщение со статусом подписки.
    
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
        
        if not subscription:
            message = "❌ Вы не подписаны на уведомления.\n\nОтправьте /start для подписки."
        else:
            status_text = "✅ Активна" if subscription.is_active else "❌ Отключена"
            message = f"""
<b>Ваш статус подписки:</b>

Статус: {status_text}
Имя: {subscription.username or 'Не указано'}
Подписан с: {subscription.created_at.strftime('%d.%m.%Y') if subscription.created_at else 'N/A'}

<b>Настройки:</b>
• Risk Zone алёрты: {'✅' if subscription.notify_risk_zone else '❌'}
• Запланированные отчёты: {'✅' if subscription.notify_scheduled else '❌'}
• Порог Risk Zone: {subscription.threshold_days} дн.

Изменить настройки можно в веб-интерфейсе.
            """.strip()
        
        return await send_telegram_message(chat_id, message)
    
    finally:
        session.close()


# Синхронная обёртка для использования в планировщике
def send_telegram_message_sync(
    chat_id: str,
    message: str,
    parse_mode: str = 'HTML',
) -> bool:
    """
    Синхронная обёртка для send_telegram_message.
    
    Используется в планировщике задач APScheduler.
    """
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        send_telegram_message(chat_id, message, parse_mode)
    )
