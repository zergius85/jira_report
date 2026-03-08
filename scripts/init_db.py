#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт инициализации базы данных Jira Report System.

Запускается автоматически при первом запуске приложения.
Также можно запустить вручную для создания таблиц.

Usage:
    python scripts/init_db.py
"""
import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import init_db
from core.report_service import initialize_database

def main():
    print("🔧 Инициализация базы данных Jira Report System...")
    
    try:
        # Инициализируем через report_service (с логированием)
        success = initialize_database()
        
        if success:
            print("✅ База данных успешно инициализирована!")
            print("📁 Файл базы данных: jira_report.db (в корне проекта)")
            print("\nСозданные таблицы:")
            print("  • report_history — История отчётов")
            print("  • report_comments — Комментарии к отчётам")
            print("  • scheduled_reports — Расписание отчётов")
            print("  • telegram_subscriptions — Telegram подписки")
            return 0
        else:
            print("❌ Ошибка инициализации базы данных")
            return 1
    
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
