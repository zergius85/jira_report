# -*- coding: utf-8 -*-
"""
РљРѕРЅС„РёРіСѓСЂР°С†РёСЏ Jira Report System

Р¦РµРЅС‚СЂР°Р»РёР·РѕРІР°РЅРЅРѕРµ СѓРїСЂР°РІР»РµРЅРёРµ РЅР°СЃС‚СЂРѕР№РєР°РјРё РґР»СЏ dev/prod РѕРєСЂСѓР¶РµРЅРёР№.
"""
import os
from dotenv import load_dotenv

# Р—Р°РіСЂСѓР¶Р°РµРј РїРµСЂРµРјРµРЅРЅС‹Рµ РёР· .env
load_dotenv()

# =============================================
# Р Р•Р–РРњ Р РђР‘РћРўР« (dev/prod)
# =============================================
# РЈСЃС‚Р°РЅРѕРІРёС‚Рµ FLASK_ENV=production РІ .env РґР»СЏ РїСЂРѕРґР°РєС€РµРЅР°
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
IS_PRODUCTION = FLASK_ENV.lower() == 'production'

# =============================================
# РЎР•РўР¬
# =============================================
# РџРѕСЂС‚ РґР»СЏ dev-СЂРµР¶РёРјР°
DEV_PORT = int(os.getenv('DEV_PORT', '5001'))

# РџРѕСЂС‚ РґР»СЏ prod-СЂРµР¶РёРјР°
PROD_PORT = int(os.getenv('PROD_PORT', '5000'))

# РҐРѕСЃС‚ (0.0.0.0 РґР»СЏ РґРѕСЃС‚СѓРїР° РёР·РІРЅРµ, 127.0.0.1 РґР»СЏ Р»РѕРєР°Р»СЊРЅРѕРіРѕ)
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')

# РђРєС‚РёРІРЅС‹Р№ РїРѕСЂС‚ РІ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё РѕС‚ РѕРєСЂСѓР¶РµРЅРёСЏ
ACTIVE_PORT = PROD_PORT if IS_PRODUCTION else DEV_PORT

# =============================================
# JIRA
# =============================================
JIRA_SERVER = os.getenv('JIRA_SERVER')
JIRA_USER = os.getenv('JIRA_USER')
JIRA_PASS = os.getenv('JIRA_PASS')

# РџСЂРѕРµРєС‚С‹ РґР»СЏ РёСЃРєР»СЋС‡РµРЅРёСЏ (СЃРїРёСЃРѕРє)
EXCLUDED_PROJECTS = [
    x.strip() for x in os.getenv('EXCLUDED_PROJECTS', '').split(',')
    if x.strip()
]

# Р’РЅСѓС‚СЂРµРЅРЅРёРµ РїСЂРѕРµРєС‚С‹ РґР»СЏ РІРєР»Р°РґРєРё "РќРµРїРѕРЅСЏС‚РЅРѕРµ" (СЃРїРёСЃРѕРє РєР»СЋС‡РµР№)
INTERNAL_PROJECTS = [
    x.strip() for x in os.getenv('INTERNAL_PROJECTS', 'NEW,local').split(',')
    if x.strip()
]

# ID СЃС‚Р°С‚СѓСЃРѕРІ "Р—Р°РєСЂС‹С‚"/"Closed" (Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РѕРїСЂРµРґРµР»СЏРµС‚СЃСЏ РёР»Рё РёР· .env)
CLOSED_STATUS_IDS = [
    x.strip() for x in os.getenv('CLOSED_STATUS_IDS', '').split(',')
    if x.strip()
]

# РСЃРїРѕР»РЅРёС‚РµР»Рё, РґР»СЏ РєРѕС‚РѕСЂС‹С… "Р—Р°РєСЂС‹С‚" РЅРµ СЃС‡РёС‚Р°РµС‚СЃСЏ РѕС€РёР±РєРѕР№
EXCLUDED_ASSIGNEE_CLOSE = [
    x.strip() for x in os.getenv('EXCLUDED_ASSIGNEE_CLOSE', 'holin').split(',')
    if x.strip()
]

# SSL РїСЂРѕРІРµСЂРєР°
SSL_VERIFY = os.getenv('SSL_VERIFY', 'true').lower() == 'true'

# =============================================
# РћРўР§РЃРўР«
# =============================================
REPORT_BLOCKS = {
    'summary': 'РЎРІРѕРґРєР° РїРѕ РїСЂРѕРµРєС‚Р°Рј',
    'assignees': 'РќР°РіСЂСѓР·РєР° РїРѕ РёСЃРїРѕР»РЅРёС‚РµР»СЏРј',
    'detail': 'Р”РµС‚Р°Р»РёР·Р°С†РёСЏ РїРѕ Р·Р°РґР°С‡Р°Рј',
    'issues': 'РџСЂРѕР±Р»РµРјРЅС‹Рµ Р·Р°РґР°С‡Рё'
}

# =============================================
# Р›РћР“РР РћР’РђРќРР•
# =============================================
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO' if IS_PRODUCTION else 'DEBUG')
LOG_FORMAT = '%(asctime)s вЂ” %(levelname)s вЂ” %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# =============================================
# РџРЈРўР
# =============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
TESTS_DIR = os.path.join(BASE_DIR, 'tests')
