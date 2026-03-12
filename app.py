# -*- coding: utf-8 -*-
"""
Точка входа для запуска веб-приложения.

Этот файл импортирует приложение из web/app.py
и запускает его.
"""
import sys
import os

# Добавляем корень проекта в path для корректных импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app

if __name__ == '__main__':
    from core.config import ACTIVE_PORT, FLASK_HOST, IS_PRODUCTION, REPORT_BLOCKS
    
    mode = "prod" if IS_PRODUCTION else "dev"
    print("🚀 Запуск веб-интерфейса...")
    print(f"📍 Откройте в браузере: http://localhost:{ACTIVE_PORT}")
    print(f"📦 Доступные блоки: {', '.join(REPORT_BLOCKS.keys())}")
    print(f"🔧 Режим: {mode}, Хост: {FLASK_HOST}, Порт: {ACTIVE_PORT}")
    app.run(host=FLASK_HOST, port=ACTIVE_PORT, debug=not IS_PRODUCTION)
