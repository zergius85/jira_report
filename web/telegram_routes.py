# -*- coding: utf-8 -*-
"""
Telegram Bot Webhook Handler.

Обработчик webhook для Telegram бота.

Совместимость: python-telegram-bot 13.x (Python 3.7+)
"""
import logging
from flask import Blueprint, request, jsonify

from core.config import TELEGRAM_BOT_TOKEN
from core.report_service import subscribe_telegram, unsubscribe_telegram
from core.telegram_bot import (
    send_welcome_message,
    send_help_message,
    send_status_message,
)

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram', __name__)

try:
    from telegram import Bot, Update
    from telegram.ext import Updater, CommandHandler
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("⚠️  python-telegram-bot не установлен. Webhook недоступен.")


# Хранилище для Updater (для webhook режима)
_updater = None


def cmd_start(update, context):
    """Обработчик команды /start (синхронная версия для PTB 13.x)."""
    chat_id = str(update.effective_chat.id)
    username = update.effective_chat.username
    
    # Подписываем пользователя
    subscribe_telegram(
        chat_id=chat_id,
        username=username,
        notify_risk_zone=True,
        notify_scheduled=True,
    )
    
    # Отправляем приветствие (синхронная версия)
    try:
        loop = None
        try:
            import asyncio
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop:
            loop.run_until_complete(send_welcome_message(chat_id, username))
    except Exception as e:
        logger.warning(f"Не удалось отправить welcome сообщение: {e}")


def cmd_stop(update, context):
    """Обработчик команды /stop."""
    chat_id = str(update.effective_chat.id)
    
    # Отписываем пользователя
    unsubscribe_telegram(chat_id)
    
    context.bot.send_message(
        chat_id=chat_id,
        text="❌ Вы отписаны от уведомлений Jira Report.\n\nОтправьте /start для повторной подписки.",
    )


def cmd_help(update, context):
    """Обработчик команды /help."""
    chat_id = str(update.effective_chat.id)
    
    try:
        loop = None
        try:
            import asyncio
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop:
            loop.run_until_complete(send_help_message(chat_id))
    except Exception as e:
        logger.error(f"Ошибка отправки help: {e}")


def cmd_status(update, context):
    """Обработчик команды /status."""
    chat_id = str(update.effective_chat.id)
    
    try:
        loop = None
        try:
            import asyncio
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop:
            loop.run_until_complete(send_status_message(chat_id))
    except Exception as e:
        logger.error(f"Ошибка отправки status: {e}")


def cmd_unknown(update, context):
    """Обработчик неизвестных команд."""
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="❓ Неизвестная команда. Отправьте /help для справки.",
    )


def get_updater() -> Updater:
    """
    Создаёт или возвращает существующий Updater для Telegram бота.
    
    Для PTB 13.x используем Updater вместо Application.builder()
    """
    global _updater
    
    if _updater is not None:
        return _updater
    
    if not TELEGRAM_AVAILABLE:
        raise RuntimeError("python-telegram-bot не установлен")
    
    # Создаём Updater
    _updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    
    # Добавляем обработчики
    dp = _updater.dispatcher
    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(CommandHandler("stop", cmd_stop))
    dp.add_handler(CommandHandler("help", cmd_help))
    dp.add_handler(CommandHandler("status", cmd_status))
    dp.add_handler(CommandHandler("set_notifications", cmd_help))
    dp.add_handler(CommandHandler("unsubscribe", cmd_stop))
    dp.add_handler(CommandHandler("unknown", cmd_unknown))
    
    return _updater


@telegram_bp.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """
    Webhook endpoint для Telegram бота.
    
    Обрабатывает входящие сообщения от Telegram.
    Для PTB 13.x используем process_update вместо process_update
    """
    if not TELEGRAM_AVAILABLE:
        return jsonify({'error': 'Telegram bot not available'}), 503
    
    try:
        update_data = request.get_json()
        if not update_data:
            return jsonify({'error': 'No data'}), 400
        
        # Создаём Updater и обрабатываем
        updater = get_updater()
        update = Update.de_json(update_data, updater.bot)
        
        # Обрабатываем update
        updater.dispatcher.process_update(update)
        
        return jsonify({'ok': True})
    
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/telegram/setup-webhook', methods=['POST'])
def setup_webhook():
    """
    Устанавливает webhook в Telegram.
    
    Вызывается однократно при настройке бота.
    """
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({'error': 'TELEGRAM_BOT_TOKEN not configured'}), 500
    
    try:
        webhook_url = request.json.get('webhook_url') if request.is_json else None
        
        if not webhook_url:
            # Пытаемся определить автоматически
            host = request.host_url.rstrip('/')
            webhook_url = f"{host}/telegram/webhook"
        
        # Для PTB 13.x используем Updater
        updater = get_updater()
        updater.bot.set_webhook(url=webhook_url)
        
        # Проверяем
        info = updater.bot.get_webhook_info()
        
        return jsonify({
            'success': True,
            'webhook_url': info.url,
            'pending_updates': info.pending_update_count,
        })
    
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@telegram_bp.route('/telegram/remove-webhook', methods=['POST'])
def remove_webhook():
    """
    Удаляет webhook из Telegram.
    """
    try:
        updater = get_updater()
        updater.bot.delete_webhook()
        
        return jsonify({'success': True})
    
    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@telegram_bp.route('/telegram/bot-info', methods=['GET'])
def bot_info():
    """
    Возвращает информацию о боте.
    """
    try:
        updater = get_updater()
        me = updater.bot.get_me()
        
        return jsonify({
            'success': True,
            'bot': {
                'id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'can_join_groups': me.can_join_groups,
                'can_read_all_group_messages': me.can_read_all_group_messages,
                'supports_inline_queries': me.supports_inline_queries,
            }
        })
    
    except Exception as e:
        logger.error(f"Ошибка получения информации о боте: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
