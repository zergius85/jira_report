# -*- coding: utf-8 -*-
"""
Конфигурация Jira Report System

Централизованное управление настройками для dev/prod окружений.
"""
import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# =============================================
# РЕЖИМ РАБОТЫ (dev/prod)
# =============================================
# Установите FLASK_ENV=production в .env для продакшена
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
IS_PRODUCTION = FLASK_ENV.lower() == 'production'

# =============================================
# СЕТЬ
# =============================================
# Порт для dev-режима
DEV_PORT = int(os.getenv('DEV_PORT', '5001'))

# Порт для prod-режима
PROD_PORT = int(os.getenv('PROD_PORT', '5000'))

# Хост (0.0.0.0 для доступа извне, 127.0.0.1 для локального)
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')

# Активный порт в зависимости от окружения
ACTIVE_PORT = PROD_PORT if IS_PRODUCTION else DEV_PORT

# =============================================
# JIRA
# =============================================
JIRA_SERVER = os.getenv('JIRA_SERVER')
JIRA_USER = os.getenv('JIRA_USER')
JIRA_PASS = os.getenv('JIRA_PASS')

# Проекты для исключения (список)
EXCLUDED_PROJECTS = [
    x.strip() for x in os.getenv('EXCLUDED_PROJECTS', '').split(',')
    if x.strip()
]

# ID статусов "Закрыт"/"Closed" (автоматически определяется или из .env)
CLOSED_STATUS_IDS = [
    x.strip() for x in os.getenv('CLOSED_STATUS_IDS', '').split(',')
    if x.strip()
]

# Исполнители, для которых "Закрыт" не считается ошибкой
EXCLUDED_ASSIGNEE_CLOSE = [
    x.strip() for x in os.getenv('EXCLUDED_ASSIGNEE_CLOSE', 'holin').split(',')
    if x.strip()
]

# SSL проверка
SSL_VERIFY = os.getenv('SSL_VERIFY', 'true').lower() == 'true'

# =============================================
# ОТЧЁТЫ
# =============================================
REPORT_BLOCKS = {
    'summary': 'Сводка по проектам',
    'assignees': 'Нагрузка по исполнителям',
    'detail': 'Детализация по задачам',
    'issues': 'Проблемные задачи'
}

# =============================================
# ЛОГИРОВАНИЕ
# =============================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO' if IS_PRODUCTION else 'DEBUG')
LOG_FORMAT = '%(asctime)s — %(levelname)s — %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# =============================================
# ПУТИ
# =============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
TESTS_DIR = os.path.join(BASE_DIR, 'tests')
