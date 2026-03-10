# -*- coding: utf-8 -*-
"""
Конфигурация Jira Report System

Централизованное управление настройками для dev/prod окружений.
"""
import os
from dotenv import load_dotenv

# Базовая директория (на уровень выше, так как файл в core/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Загружаем переменные из .env.local (приоритет), затем из .env
# .env.local НЕ tracked в git, используется для локальных настроек
load_dotenv(os.path.join(BASE_DIR, '.env.local'))
load_dotenv(os.path.join(BASE_DIR, '.env'), override=False)

# =============================================
# ПРОВЕРКА ВЕРСИИ КОНФИГУРАЦИИ
# =============================================
REQUIRED_CONFIG_VERSION = '2.3'
CONFIG_VERSION = os.getenv('CONFIG_VERSION', '1.0')

if CONFIG_VERSION != REQUIRED_CONFIG_VERSION:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(
        f"⚠️  Версия конфигурации устарела: {CONFIG_VERSION} (требуется {REQUIRED_CONFIG_VERSION}). "
        f"Скопируйте .env.example в .env и перенесите ваши настройки."
    )

# =============================================
# РЕЖИМ РАБОТЫ (dev/prod)
# =============================================
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
IS_PRODUCTION = FLASK_ENV.lower() == 'production'

# =============================================
# СЕТЬ
# =============================================
DEV_PORT = int(os.getenv('DEV_PORT', '5001'))
PROD_PORT = int(os.getenv('PROD_PORT', '5000'))
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
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

# Внутренние проекты для вкладки "Непонятное" (список ключей)
INTERNAL_PROJECTS = [
    x.strip() for x in os.getenv('INTERNAL_PROJECTS', 'NEW,local').split(',')
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
    'issues': 'Проблемные задачи',
    'internal': 'Непонятное (NEW, local)',
    'risk_zone': 'Зависшие задачи (Risk Zone)'
}

# =============================================
# КОНСТАНТЫ ДЛЯ ОТЧЁТОВ
# =============================================
# Максимальное количество дней для отчёта
MAX_REPORT_DAYS = 365
# Порог неактивности задач для Risk Zone (дни)
RISK_ZONE_INACTIVITY_THRESHOLD = 5
# Максимум результатов при поиске пользователей/задач
MAX_SEARCH_RESULTS = 1000
# Максимум строк в Excel (ограничение производительности)
MAX_EXCEL_ROWS = 10000

# =============================================
# RATE LIMITER (API)
# =============================================
# Максимум запросов от одного клиента в окно времени
API_RATE_LIMIT_MAX_REQUESTS = int(os.getenv('API_RATE_LIMIT_MAX_REQUESTS', '50'))
# Окно времени для rate limiting (секунды)
API_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('API_RATE_LIMIT_WINDOW_SECONDS', '60'))
# Максимум клиентов в памяти (LRU-кэш)
API_RATE_LIMIT_MAX_CLIENTS = int(os.getenv('API_RATE_LIMIT_MAX_CLIENTS', '10000'))

# =============================================
# ПЛАНИРОВЩИК (SCHEDULER)
# =============================================
# Часовой пояс планировщика
SCHEDULER_TIMEZONE = os.getenv('SCHEDULER_TIMEZONE', 'Europe/Moscow')
# Время отправки отчётов по умолчанию (час)
SCHEDULER_DEFAULT_HOUR = int(os.getenv('SCHEDULER_DEFAULT_HOUR', '9'))
# Misfire grace time (секунды) — время, в течение которого задача может быть выполнена после пропуска
SCHEDULER_MISFIRE_GRACE_TIME = int(os.getenv('SCHEDULER_MISFIRE_GRACE_TIME', '3600'))
# Максимум задач в пуле
SCHEDULER_MAX_INSTANCES = int(os.getenv('SCHEDULER_MAX_INSTANCES', '3'))
# Интервал запуска джобы (секунды)
SCHEDULER_JOBSTORE_RELOAD_INTERVAL = int(os.getenv('SCHEDULER_JOBSTORE_RELOAD_INTERVAL', '60'))

# =============================================
# ЛОГИРОВАНИЕ
# =============================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO' if IS_PRODUCTION else 'DEBUG')
LOG_FORMAT = '%(asctime)s — %(levelname)s — %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# =============================================
# TELEGRAM
# =============================================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_WEBHOOK_URL = os.getenv('TELEGRAM_WEBHOOK_URL')

# =============================================
# EMAIL (SMTP)
# =============================================
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
EMAIL_FROM = os.getenv('EMAIL_FROM', 'Jira Report <noreply@jira-report.local>')

# =============================================
# ПУТИ
# =============================================
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(CORE_DIR, 'templates')
TESTS_DIR = os.path.join(CORE_DIR, 'tests')
REPORTS_DIR = os.path.join(CORE_DIR, '..', 'reports')  # Папка для сохранённых отчётов

# Создаём директорию для отчётов если не существует
if not os.path.exists(REPORTS_DIR):
    os.makedirs(REPORTS_DIR, exist_ok=True)
