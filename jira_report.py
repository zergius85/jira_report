# -*- coding: utf-8 -*-
"""
Jira Report System вЂ” РЇРґСЂРѕ РѕС‚С‡С‘С‚РѕРІ

РњРѕРґСѓР»СЊ РґР»СЏ СЃР±РѕСЂР°, РѕР±СЂР°Р±РѕС‚РєРё Рё РІС‹РіСЂСѓР·РєРё РґР°РЅРЅС‹С… РёР· Jira.
РџРѕРґРґРµСЂР¶РёРІР°РµС‚ РєРѕРЅСЃРѕР»СЊРЅС‹Р№ СЂРµР¶РёРј Рё СЂР°Р±РѕС‚Сѓ С‡РµСЂРµР· Web-РёРЅС‚РµСЂС„РµР№СЃ.
"""
from typing import Optional, List, Dict, Any, Tuple, Union
from jira import JIRA, JIRAError
import pandas as pd
import warnings
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime, timedelta
import argparse
import os
import sys
import logging
import io
from dateutil.relativedelta import relativedelta

# РРјРїРѕСЂС‚РёСЂСѓРµРј РЅР°СЃС‚СЂРѕР№РєРё РёР· config.py
from config import (
    JIRA_SERVER,
    JIRA_USER,
    JIRA_PASS,
    EXCLUDED_PROJECTS,
    CLOSED_STATUS_IDS,
    EXCLUDED_ASSIGNEE_CLOSE,
    SSL_VERIFY,
    REPORT_BLOCKS,
    LOG_LEVEL,
    LOG_FORMAT,
    LOG_DATE_FORMAT
)

# --- РќРђРЎРўР РћР™РљРђ Р›РћР“РР РћР’РђРќРРЇ ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT
)
logger = logging.getLogger(__name__)

# --- РќРђРЎРўР РћР™РљРђ SSL ---
if not SSL_VERIFY:
    logger.warning("вљ пёЏ  РџСЂРѕРІРµСЂРєР° SSL РѕС‚РєР»СЋС‡РµРЅР° (SSL_VERIFY=false)")
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    os.environ['CURL_CA_BUNDLE'] = ''
    warnings.simplefilter('ignore', InsecureRequestWarning)
else:
    logger.info("вњ… РџСЂРѕРІРµСЂРєР° SSL РІРєР»СЋС‡РµРЅР°")

def validate_config() -> Tuple[bool, List[str]]:
    """
    РџСЂРѕРІРµСЂСЏРµС‚ РєРѕСЂСЂРµРєС‚РЅРѕСЃС‚СЊ РєРѕРЅС„РёРіСѓСЂР°С†РёРё.
    
    Returns:
        Tuple[bool, List[str]]: (СѓСЃРїРµС…, СЃРїРёСЃРѕРє РѕС€РёР±РѕРє)
    """
    errors = []
    
    if not JIRA_SERVER:
        errors.append("РќРµ СѓРєР°Р·Р°РЅ JIRA_SERVER РІ .env")
    if not JIRA_USER:
        errors.append("РќРµ СѓРєР°Р·Р°РЅ JIRA_USER РІ .env")
    if not JIRA_PASS:
        errors.append("РќРµ СѓРєР°Р·Р°РЅ JIRA_PASS РІ .env")
    
    return (len(errors) == 0, errors)


def get_jira_connection() -> JIRA:
    """
    РЈСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ СЃРѕРµРґРёРЅРµРЅРёРµ СЃ Jira.
    
    Returns:
        JIRA: РћР±СЉРµРєС‚ РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє Jira
        
    Raises:
        ConnectionError: РџСЂРё РѕС€РёР±РєРµ РїРѕРґРєР»СЋС‡РµРЅРёСЏ
    """
    try:
        logger.info(f"рџ”Њ РџРѕРґРєР»СЋС‡РµРЅРёРµ Рє Jira: {JIRA_SERVER}")
        
        if not SSL_VERIFY:
            jira = JIRA(
                server=JIRA_SERVER,
                basic_auth=(JIRA_USER, JIRA_PASS),
                options={'verify': False}
            )
        else:
            jira = JIRA(
                server=JIRA_SERVER,
                basic_auth=(JIRA_USER, JIRA_PASS)
            )
        
        # РџСЂРѕРІРµСЂРєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ
        jira.myself()
        logger.info("вњ… РЈСЃРїРµС€РЅРѕРµ РїРѕРґРєР»СЋС‡РµРЅРёРµ Рє Jira")
        return jira
        
    except JIRAError as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє Jira: {e.text}")
        raise ConnectionError(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Jira: {e.text}")
    except Exception as e:
        logger.error(f"вќЊ РќРµРёР·РІРµСЃС‚РЅР°СЏ РѕС€РёР±РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ: {e}")
        raise ConnectionError(f"РћС€РёР±РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ: {e}")

def get_default_start_date() -> datetime:
    """
    Р’РѕР·РІСЂР°С‰Р°РµС‚ РґР°С‚Сѓ РЅР°С‡Р°Р»Р° РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ (1 С‡РёСЃР»Рѕ РїСЂРѕС€Р»РѕРіРѕ РјРµСЃСЏС†Р°).
    
    Returns:
        datetime: Р”Р°С‚Р° РЅР°С‡Р°Р»Р°
    """
    today = datetime.now()
    if today.month == 1:
        return datetime(today.year - 1, 12, 1)
    else:
        return datetime(today.year, today.month - 1, 1)


def convert_seconds_to_hours(seconds: Optional[int]) -> float:
    """
    РљРѕРЅРІРµСЂС‚РёСЂСѓРµС‚ СЃРµРєСѓРЅРґС‹ РІ С‡Р°СЃС‹.
    
    Args:
        seconds: Р’СЂРµРјСЏ РІ СЃРµРєСѓРЅРґР°С…
        
    Returns:
        float: Р’СЂРµРјСЏ РІ С‡Р°СЃР°С…
    """
    if seconds is None:
        return 0.0
    return round(seconds / 3600, 2)


def get_closed_status_ids() -> List[str]:
    """
    РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРё РѕРїСЂРµРґРµР»СЏРµС‚ ID СЃС‚Р°С‚СѓСЃР° "Р—Р°РєСЂС‹С‚" РІ Jira.
    РљСЌС€РёСЂСѓРµС‚ СЂРµР·СѓР»СЊС‚Р°С‚ РІ .env РґР»СЏ РїРѕСЃР»РµРґСѓСЋС‰РёС… Р·Р°РїСѓСЃРєРѕРІ.
    
    Returns:
        List[str]: РЎРїРёСЃРѕРє ID СЃС‚Р°С‚СѓСЃРѕРІ
    """
    if CLOSED_STATUS_IDS and CLOSED_STATUS_IDS[0] != '':
        logger.info(f"вњ… ID СЃС‚Р°С‚СѓСЃР° 'Р—Р°РєСЂС‹С‚' Р·Р°РіСЂСѓР¶РµРЅ РёР· .env: {CLOSED_STATUS_IDS}")
        return CLOSED_STATUS_IDS

    logger.info("рџ”Ќ РћРїСЂРµРґРµР»РµРЅРёРµ ID СЃС‚Р°С‚СѓСЃР° 'Р—Р°РєСЂС‹С‚' РІ Jira...")

    try:
        jira = get_jira_connection()
        statuses = jira.statuses()

        closed_ids = []
        for status in statuses:
            if status.name.lower() in ['Р·Р°РєСЂС‹С‚', 'closed', 'Р·Р°РєСЂС‹С‚Рѕ']:
                closed_ids.append(status.id)
                logger.info(f"   рџ“Њ РќР°Р№РґРµРЅ СЃС‚Р°С‚СѓСЃ: {status.name} (ID: {status.id})")

        if closed_ids:
            save_closed_status_ids(closed_ids)
            logger.info(f"вњ… ID СЃРѕС…СЂР°РЅРµРЅС‹ РІ .env: {closed_ids}")
            return closed_ids
        else:
            logger.warning("вљ пёЏ  РЎС‚Р°С‚СѓСЃ 'Р—Р°РєСЂС‹С‚' РЅРµ РЅР°Р№РґРµРЅ.")
            return []

    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РѕРїСЂРµРґРµР»РµРЅРёСЏ СЃС‚Р°С‚СѓСЃР°: {e}")
        return []


def save_closed_status_ids(status_ids: List[str]) -> None:
    """
    РЎРѕС…СЂР°РЅСЏРµС‚ ID СЃС‚Р°С‚СѓСЃРѕРІ РІ С„Р°Р№Р» .env.

    Args:
        status_ids: РЎРїРёСЃРѕРє ID РґР»СЏ СЃРѕС…СЂР°РЅРµРЅРёСЏ
    """
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

    env_content = ''
    if os.path.exists(env_path):
        # Р§РёС‚Р°РµРј РІ UTF-8, РµСЃР»Рё РЅРµ РїРѕР»СѓС‡Р°РµС‚СЃСЏ вЂ” РїСЂРѕР±СѓРµРј cp1251 (Windows)
        for encoding in ['utf-8', 'cp1251']:
            try:
                with open(env_path, 'r', encoding=encoding) as f:
                    env_content = f.read()
                break
            except UnicodeDecodeError:
                continue

    if 'CLOSED_STATUS_IDS=' in env_content:
        env_content = env_content.replace(
            env_content.split('CLOSED_STATUS_IDS=')[1].split('\n')[0],
            ','.join(status_ids)
        )
    else:
        env_content += f"\nCLOSED_STATUS_IDS={','.join(status_ids)}"

    # РџРёС€РµРј РІ UTF-8 (СЃС‚Р°РЅРґР°СЂС‚ РґР»СЏ python-dotenv)
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)

def validate_issue(issue: Any, jira: Optional[JIRA] = None) -> List[str]:
    """
    РџСЂРѕРІРµСЂСЏРµС‚ Р·Р°РґР°С‡Сѓ РЅР° РєРѕСЂСЂРµРєС‚РЅРѕСЃС‚СЊ Р·Р°РїРѕР»РЅРµРЅРёСЏ.

    Args:
        issue: РћР±СЉРµРєС‚ Р·Р°РґР°С‡Рё Jira
        jira: РћР±СЉРµРєС‚ РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє Jira (РЅСѓР¶РµРЅ РґР»СЏ РїСЂРѕРІРµСЂРєРё changelog)

    Returns:
        List[str]: РЎРїРёСЃРѕРє РїСЂРѕР±Р»РµРј
    """
    problems = []

    # РџСЂРѕРІРµСЂРєР° РґР°С‚С‹ СЂРµС€РµРЅРёСЏ
    if not issue.fields.resolutiondate:
        problems.append('РќРµС‚ РґР°С‚С‹ СЂРµС€РµРЅРёСЏ')

    # РџСЂРѕРІРµСЂРєР° С„Р°РєС‚РёС‡РµСЃРєРѕРіРѕ РІСЂРµРјРµРЅРё
    if issue.fields.timespent is None or issue.fields.timespent == 0:
        problems.append('РќРµС‚ С„Р°РєС‚РёС‡РµСЃРєРѕРіРѕ РІСЂРµРјРµРЅРё')

    # РџСЂРѕРІРµСЂРєР° СЃС‚Р°С‚СѓСЃР° "Р—Р°РєСЂС‹С‚" РїРѕ ID
    if issue.fields.status:
        status_id = issue.fields.status.id
        status_name = issue.fields.status.name

        # РџСЂРѕРІРµСЂСЏРµРј changelog РўРћР›Р¬РљРћ РµСЃР»Рё СЃС‚Р°С‚СѓСЃ "Р—Р°РєСЂС‹С‚"
        if status_id in CLOSED_STATUS_IDS:
            is_correct_close = False
            
            # РџСЂРѕРІРµСЂСЏРµРј, РЅРµ СЏРІР»СЏРµС‚СЃСЏ Р»Рё РёСЃРїРѕР»РЅРёС‚РµР»СЊ РёСЃРєР»СЋС‡РµРЅРёРµРј (holin Рё С‚.Рї.)
            assignee_name = ''
            if issue.fields.assignee:
                assignee_name = issue.fields.assignee.name if hasattr(issue.fields.assignee, 'name') else issue.fields.assignee.displayName

            for exc in EXCLUDED_ASSIGNEE_CLOSE:
                if exc.lower() in assignee_name.lower():
                    is_correct_close = True
                    break
            
            # Р•СЃР»Рё РЅРµ РёСЃРєР»СЋС‡РµРЅРёРµ, РїСЂРѕРІРµСЂСЏРµРј changelog (РєС‚Рѕ РїРµСЂРµРІС‘Р» РІ "Р—Р°РєСЂС‹С‚")
            if not is_correct_close and jira:
                try:
                    # РџРѕР»СѓС‡Р°РµРј РёСЃС‚РѕСЂРёСЋ РїРµСЂРµС…РѕРґРѕРІ Р·Р°РґР°С‡Рё
                    issue_with_changelog = jira.issue(issue.key, expand='changelog')
                    if hasattr(issue_with_changelog, 'changelog') and issue_with_changelog.changelog:
                        # РС‰РµРј РїРѕСЃР»РµРґРЅРёР№ РїРµСЂРµС…РѕРґ РІ СЃС‚Р°С‚СѓСЃ "Р—Р°РєСЂС‹С‚"
                        for history in reversed(issue_with_changelog.changelog.histories):
                            for item in history.items:
                                if item.field == 'status' and item.toString:
                                    # РџСЂРѕРІРµСЂСЏРµРј, Р±С‹Р» Р»Рё СЌС‚Рѕ РїРµСЂРµС…РѕРґ РІ Р·Р°РєСЂС‹С‚С‹Р№ СЃС‚Р°С‚СѓСЃ
                                    if hasattr(item, 'to') and item.to in CLOSED_STATUS_IDS:
                                        # РџСЂРѕРІРµСЂСЏРµРј, РєС‚Рѕ СЃРґРµР»Р°Р» РїРµСЂРµС…РѕРґ
                                        author_name = ''
                                        if hasattr(history, 'author') and history.author:
                                            author_name = history.author.name if hasattr(history.author, 'name') else history.author.displayName
                                        
                                        # Р•СЃР»Рё РїРµСЂРµС…РѕРґ СЃРґРµР»Р°Р» РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РґРµРјРѕРЅР° вЂ” СЌС‚Рѕ РєРѕСЂСЂРµРєС‚РЅРѕ
                                        if JIRA_USER and JIRA_USER.lower() in author_name.lower():
                                            is_correct_close = True
                                        break
                            if is_correct_close or (hasattr(item, 'to') and item.to in CLOSED_STATUS_IDS):
                                break
                except Exception as e:
                    # Р•СЃР»Рё РЅРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ changelog, СЃС‡РёС‚Р°РµРј СЌС‚Рѕ РїСЂРѕР±Р»РµРјРѕР№
                    logger.warning(f"вљ пёЏ  РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ changelog РґР»СЏ {issue.key}: {e}")
                    problems.append('РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ РёСЃС‚РѕСЂРёСЋ РїРµСЂРµС…РѕРґРѕРІ')

            # Р•СЃР»Рё СЃС‚Р°С‚СѓСЃ "Р—Р°РєСЂС‹С‚" Рё РЅРµ РєРѕСЂСЂРµРєС‚РЅРѕ Р·Р°РєСЂС‹С‚ вЂ” СЌС‚Рѕ РїСЂРѕР±Р»РµРјР°
            if not is_correct_close:
                problems.append(f"РЎС‚Р°С‚СѓСЃ '{status_name}' (ID: {status_id})")

    return problems


def get_column_order(block: str, extra_verbose: bool = False) -> List[str]:
    """
    Р’РѕР·РІСЂР°С‰Р°РµС‚ РїРѕСЂСЏРґРѕРє РєРѕР»РѕРЅРѕРє РґР»СЏ РєР°Р¶РґРѕРіРѕ Р±Р»РѕРєР°.

    Args:
        block: РќР°Р·РІР°РЅРёРµ Р±Р»РѕРєР° РѕС‚С‡С‘С‚Р°
        extra_verbose: РџРѕРєР°Р·С‹РІР°С‚СЊ Р»Рё ID РѕР±СЉРµРєС‚РѕРІ

    Returns:
        List[str]: РЎРїРёСЃРѕРє РЅР°Р·РІР°РЅРёР№ РєРѕР»РѕРЅРѕРє
    """
    if block == 'summary':
        if extra_verbose:
            return ['РљР»РёРµРЅС‚ (РџСЂРѕРµРєС‚)', 'ID', 'Р—Р°РґР°С‡ Р·Р°РєСЂС‹С‚Рѕ', 'РљРѕСЂСЂРµРєС‚РЅС‹С…', 'РЎ РѕС€РёР±РєР°РјРё', 'РћС†РµРЅРєР° (С‡)', 'Р¤Р°РєС‚ (С‡)', 'РћС‚РєР»РѕРЅРµРЅРёРµ']
        return ['РљР»РёРµРЅС‚ (РџСЂРѕРµРєС‚)', 'Р—Р°РґР°С‡ Р·Р°РєСЂС‹С‚Рѕ', 'РљРѕСЂСЂРµРєС‚РЅС‹С…', 'РЎ РѕС€РёР±РєР°РјРё', 'РћС†РµРЅРєР° (С‡)', 'Р¤Р°РєС‚ (С‡)', 'РћС‚РєР»РѕРЅРµРЅРёРµ']
    elif block == 'assignees':
        if extra_verbose:
            return ['РСЃРїРѕР»РЅРёС‚РµР»СЊ', 'ID', 'Р—Р°РґР°С‡', 'РљРѕСЂСЂРµРєС‚РЅС‹С…', 'РЎ РѕС€РёР±РєР°РјРё', 'РћС†РµРЅРєР° (С‡)', 'Р¤Р°РєС‚ (С‡)', 'РћС‚РєР»РѕРЅРµРЅРёРµ']
        return ['РСЃРїРѕР»РЅРёС‚РµР»СЊ', 'Р—Р°РґР°С‡', 'РљРѕСЂСЂРµРєС‚РЅС‹С…', 'РЎ РѕС€РёР±РєР°РјРё', 'РћС†РµРЅРєР° (С‡)', 'Р¤Р°РєС‚ (С‡)', 'РћС‚РєР»РѕРЅРµРЅРёРµ']
    elif block == 'detail':
        if extra_verbose:
            return ['URL', 'ID', 'Р”Р°С‚Р° РёСЃРїРѕР»РЅРµРЅРёСЏ', 'Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ', 'РџСЂРѕРµРєС‚', 'РЎС‚Р°С‚СѓСЃ', 'Р—Р°РґР°С‡Р°', 'РСЃРїРѕР»РЅРёС‚РµР»СЊ', 'Р¤Р°РєС‚ (С‡)', 'РўРёРї']
        return ['URL', 'Р”Р°С‚Р° РёСЃРїРѕР»РЅРµРЅРёСЏ', 'Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ', 'РџСЂРѕРµРєС‚', 'РЎС‚Р°С‚СѓСЃ', 'Р—Р°РґР°С‡Р°', 'РСЃРїРѕР»РЅРёС‚РµР»СЊ', 'Р¤Р°РєС‚ (С‡)', 'РўРёРї']
    elif block == 'issues':
        if extra_verbose:
            return ['URL', 'ID', 'Р”Р°С‚Р° РёСЃРїРѕР»РЅРµРЅРёСЏ', 'Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ', 'РџСЂРѕРµРєС‚', 'Р—Р°РґР°С‡Р°', 'РСЃРїРѕР»РЅРёС‚РµР»СЊ', 'РђРІС‚РѕСЂ', 'РџСЂРѕР±Р»РµРјС‹']
        return ['URL', 'Р”Р°С‚Р° РёСЃРїРѕР»РЅРµРЅРёСЏ', 'Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ', 'РџСЂРѕРµРєС‚', 'Р—Р°РґР°С‡Р°', 'РСЃРїРѕР»РЅРёС‚РµР»СЊ', 'РђРІС‚РѕСЂ', 'РџСЂРѕР±Р»РµРјС‹']
    else:
        return ['РџСЂРѕРµРєС‚', 'РљР»СЋС‡', 'Р—Р°РґР°С‡Р°', 'РСЃРїРѕР»РЅРёС‚РµР»СЊ', 'РЎС‚Р°С‚СѓСЃ', 'Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ', 'Р”Р°С‚Р° РёСЃРїРѕР»РЅРµРЅРёСЏ', 'Р¤Р°РєС‚ (С‡)', 'РћС†РµРЅРєР° (С‡)']
        
def generate_report(
    project_key: Optional[str] = None,
    start_date: Optional[str] = None,
    days: int = 30,
    assignee_filter: Optional[str] = None,
    blocks: Optional[List[str]] = None,
    verbose: bool = False,
    extra_verbose: bool = False
) -> Dict[str, Any]:
    """
    Р“РµРЅРµСЂРёСЂСѓРµС‚ РѕС‚С‡С‘С‚ РїРѕ Р·Р°РґР°С‡Р°Рј Jira.
    
    Args:
        project_key: РљР»СЋС‡ РїСЂРѕРµРєС‚Р° (None = РІСЃРµ РїСЂРѕРµРєС‚С‹)
        start_date: Р”Р°С‚Р° РЅР°С‡Р°Р»Р° РІ С„РѕСЂРјР°С‚Рµ Р“Р“Р“Р“-РњРњ-Р”Р” (None = РїСЂРѕС€Р»С‹Р№ РјРµСЃСЏС†)
        days: РљРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№ РґР»СЏ РѕС‚С‡С‘С‚Р°
        assignee_filter: Р¤РёР»СЊС‚СЂ РїРѕ РёСЃРїРѕР»РЅРёС‚РµР»СЋ
        blocks: РЎРїРёСЃРѕРє Р±Р»РѕРєРѕРІ РѕС‚С‡С‘С‚Р° (None = РІСЃРµ)
        verbose: Р РµР¶РёРј РѕС‚Р»Р°РґРєРё
        extra_verbose: РџРѕРєР°Р·С‹РІР°С‚СЊ ID РѕР±СЉРµРєС‚РѕРІ
        
    Returns:
        Dict[str, Any]: РЎР»РѕРІР°СЂСЊ СЃ РґР°РЅРЅС‹РјРё РѕС‚С‡С‘С‚Р°
    """
    # РђРІС‚Рѕ-РѕРїСЂРµРґРµР»РµРЅРёРµ ID СЃС‚Р°С‚СѓСЃР° "Р—Р°РєСЂС‹С‚"
    global CLOSED_STATUS_IDS
    if not CLOSED_STATUS_IDS or CLOSED_STATUS_IDS[0] == '':
        CLOSED_STATUS_IDS = get_closed_status_ids()

    # РћР±СЂР°Р±РѕС‚РєР° РґР°С‚
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date_obj = get_default_start_date()

    start_date_str = start_date_obj.strftime('%Y-%m-%d')
    end_date_obj = start_date_obj + timedelta(days=days - 1)
    end_date_str = end_date_obj.strftime('%Y-%m-%d')

    # Р”Р»СЏ РїСЂРѕР±Р»РµРјРЅС‹С… Р·Р°РґР°С‡: +2 РјРµСЃСЏС†Р° Рє РєРѕРЅС†Сѓ РїРµСЂРёРѕРґР°
    issues_end_obj = start_date_obj + timedelta(days=days) + relativedelta(months=2)
    issues_end_str = issues_end_obj.strftime('%Y-%m-%d')

    jira = get_jira_connection()
    
    # РЎРїРёСЃРѕРє РїСЂРѕРµРєС‚РѕРІ
    if project_key:
        projects_keys = [project_key.upper()]
        projects_map = {}
        proj = jira.project(projects_keys[0])
        projects_map[proj.key] = proj.name
    else:
        all_projects = jira.projects()
        projects_map = {}
        for proj in all_projects:
            if proj.key in EXCLUDED_PROJECTS:
                continue
            if hasattr(proj, 'archived') and proj.archived:
                continue
            projects_map[proj.key] = proj.name
        projects_keys = list(projects_map.keys())
    
    all_issues_data = []
    summary_data = []
    issues_with_problems = []
    
    for proj_key in projects_keys:
        proj_name = projects_map.get(proj_key, proj_key)
        
        # РћР±С‹С‡РЅС‹Рµ РѕС‚С‡С‘С‚С‹ - С„РёР»СЊС‚СЂ РїРѕ resolved (РґР°С‚Р° Р·Р°РєСЂС‹С‚РёСЏ)
        jql_normal = (f"project = {proj_key} "
                      f"AND resolved >= '{start_date_str}' "
                      f"AND resolved <= '{end_date_str}' "
                      f"ORDER BY resolved ASC")
        
        # РџСЂРѕР±Р»РµРјРЅС‹Рµ Р·Р°РґР°С‡Рё - С„РёР»СЊС‚СЂ РїРѕ created + 2 РјРµСЃСЏС†Р°
        jql_issues = (f"project = {proj_key} "
                      f"AND created >= '{start_date_str}' "
                      f"AND created <= '{issues_end_str}' "
                      f"ORDER BY created ASC")
        
        # РџРѕР»СѓС‡Р°РµРј РІСЃРµ Р·Р°РґР°С‡Рё РґР»СЏ РїСЂРѕР±Р»РµРјРЅС‹С… (Р±РѕР»СЊС€РёР№ РїРµСЂРёРѕРґ)
        issues_all = jira.search_issues(jql_issues, maxResults=False, 
                                        fields='summary, assignee, timespent, timeoriginalestimate, resolutiondate, issuetype, duedate, status, created, creator')
        
        # РџРѕР»СѓС‡Р°РµРј Р·Р°РґР°С‡Рё РґР»СЏ РѕР±С‹С‡РЅС‹С… РѕС‚С‡С‘С‚РѕРІ (РјРµРЅСЊС€РёР№ РїРµСЂРёРѕРґ)
        issues_normal = jira.search_issues(jql_normal, maxResults=False, 
                                           fields='summary, assignee, timespent, timeoriginalestimate, resolutiondate, issuetype, duedate, status, created')
        
        # РћР±СЂР°Р±РѕС‚РєР° РґР»СЏ РѕР±С‹С‡РЅС‹С… РѕС‚С‡С‘С‚РѕРІ
        proj_spent = 0.0
        proj_estimated = 0.0
        proj_correct = 0
        proj_issues = 0
        
        for issue in issues_normal:
            spent = convert_seconds_to_hours(issue.fields.timespent)
            estimated = convert_seconds_to_hours(issue.fields.timeoriginalestimate)
            
            issue_type = issue.fields.issuetype.name if issue.fields.issuetype else 'Р—Р°РґР°С‡Р°'
            assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Р‘РµР· РёСЃРїРѕР»РЅРёС‚РµР»СЏ'
            duedate = issue.fields.duedate[:10] if issue.fields.duedate else '-'
            resolved = issue.fields.resolutiondate[:10] if issue.fields.resolutiondate else '-'
            created = issue.fields.created[:10] if issue.fields.created else '-'
            
            status_name = issue.fields.status.name if issue.fields.status else '-'
            status_category = issue.fields.status.statusCategory.key if issue.fields.status and issue.fields.status.statusCategory else '-'
            status_full = f"{status_name} ({status_category})"
            
            issue_url = f"{JIRA_SERVER}/browse/{issue.key}"
            issue_id = issue.id if extra_verbose else None
            
            problems = validate_issue(issue, jira)
            
            if assignee_filter and assignee_filter.lower() not in assignee.lower():
                continue
            
            # Формируем отображаемые значения с ID если нужно
            project_id = getattr(getattr(issue.fields, 'project', None), 'id', None)
            project_display = f"{proj_name} [{project_id}]" if extra_verbose and project_id else proj_name
            status_display = f"{status_full} [{issue.fields.status.id}]" if extra_verbose and issue.fields.status and hasattr(issue.fields.status, 'id') else status_full
            issue_type_display = f"{issue_type} [{issue.fields.issuetype.id}]" if extra_verbose and issue.fields.issuetype and hasattr(issue.fields.issuetype, 'id') else issue_type
            assignee_display = f"{assignee} [{issue.fields.assignee.id}]" if extra_verbose and issue.fields.assignee and hasattr(issue.fields.assignee, 'id') else assignee
            
            issue_data = {
                'URL': issue_url,
                'ID': issue_id,
                'РџСЂРѕРµРєС‚': project_display,
                'РљР»СЋС‡': issue.key,
                'РўРёРї': issue_type_display,
                'Р—Р°РґР°С‡Р°': issue.fields.summary,
                'РСЃРїРѕР»РЅРёС‚РµР»СЊ': assignee_display,
                'РЎС‚Р°С‚СѓСЃ': status_display,
                'Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ': created,
                'Р”Р°С‚Р° РёСЃРїРѕР»РЅРµРЅРёСЏ': duedate,
                'Р”Р°С‚Р° СЂРµС€РµРЅРёСЏ': resolved,
                'Р¤Р°РєС‚ (С‡)': spent,
                'РћС†РµРЅРєР° (С‡)': estimated,
                'РџСЂРѕР±Р»РµРјС‹': ', '.join(problems) if problems else ''
            }
            
            all_issues_data.append(issue_data)
            
            if not problems:
                proj_spent += spent
                proj_estimated += estimated
                proj_correct += 1
            else:
                proj_issues += 1
            
            if problems:
                # Р”Р»СЏ РїСЂРѕР±Р»РµРјРЅС‹С… Р·Р°РґР°С‡ Р±РµСЂС‘Рј РЎРћР—Р”РђРўР•Р›РЇ Р·Р°РґР°С‡Рё (creator)
                author = 'N/A'
                author_id = ''
                if hasattr(issue.fields, 'creator') and issue.fields.creator:
                    author = issue.fields.creator.displayName if hasattr(issue.fields.creator, 'displayName') else str(issue.fields.creator)
                    author_id = issue.fields.creator.id if hasattr(issue.fields.creator, 'id') else ''
                elif hasattr(issue.fields, 'author') and issue.fields.author:
                    author = issue.fields.author.displayName if hasattr(issue.fields.author, 'displayName') else str(issue.fields.author)
                    author_id = issue.fields.author.id if hasattr(issue.fields.author, 'id') else ''

                # Р¤РѕСЂРјРёСЂСѓРµРј РёРјСЏ Р°РІС‚РѕСЂР° СЃ ID РµСЃР»Рё РЅСѓР¶РЅРѕ
                author_display = f"{author} [{author_id}]" if extra_verbose and author_id else author

                issue_data = {
                    'URL': issue_url,
                    'РџСЂРѕРµРєС‚': proj_name,
                    'Р—Р°РґР°С‡Р°': issue.fields.summary,
                    'РСЃРїРѕР»РЅРёС‚РµР»СЊ': assignee,
                    'РђРІС‚РѕСЂ': author_display,
                    'Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ': created,
                    'Р”Р°С‚Р° РёСЃРїРѕР»РЅРµРЅРёСЏ': duedate,
                    'РџСЂРѕР±Р»РµРјС‹': ', '.join(problems)
                }
                # Р”РѕР±Р°РІР»СЏРµРј ID Р·Р°РґР°С‡Рё РґР»СЏ extra_verbose
                if extra_verbose:
                    issue_data.insert(1, 'ID', issue.id)
                issues_with_problems.append(issue_data)
        
        if proj_correct > 0 or proj_issues > 0:
            summary_row = {
                'РљР»РёРµРЅС‚ (РџСЂРѕРµРєС‚)': proj_name,
                'Р—Р°РґР°С‡ Р·Р°РєСЂС‹С‚Рѕ': proj_correct + proj_issues,
                'РљРѕСЂСЂРµРєС‚РЅС‹С…': proj_correct,
                'РЎ РѕС€РёР±РєР°РјРё': proj_issues,
                'РћС†РµРЅРєР° (С‡)': round(proj_estimated, 2),
                'Р¤Р°РєС‚ (С‡)': round(proj_spent, 2),
                'РћС‚РєР»РѕРЅРµРЅРёРµ': round(proj_estimated - proj_spent, 2)
            }
            # Добавляем ID проекта для extra_verbose
            if extra_verbose:
                # Берём ID проекта из первой задачи
                proj_id = getattr(getattr(issues_normal[0].fields, 'project', None), 'id', '') if issues_normal else ''
                summary_row.insert(1, 'ID', proj_id)
            summary_data.append(summary_row)
    
    df_detail = pd.DataFrame(all_issues_data)
    df_summary = pd.DataFrame(summary_data)
    df_issues = pd.DataFrame(issues_with_problems)
    
    # РЎРѕСЂС‚РёСЂРѕРІРєР° Рё РіСЂСѓРїРїРёСЂРѕРІРєР°
    if not df_detail.empty:
        df_detail = df_detail.sort_values(by=['РўРёРї', 'РџСЂРѕРµРєС‚', 'Р”Р°С‚Р° СЂРµС€РµРЅРёСЏ'], ascending=[True, True, True])

        # Р“СЂСѓРїРїРёСЂРѕРІРєР° РїРѕ РёСЃРїРѕР»РЅРёС‚РµР»СЏРј - РЎР§РРўРђР•Рњ Р’РЎР• Р—РђР”РђР§Р (СЂР°Р·РґРµР»СЏРµРј РЅР° РєРѕСЂСЂРµРєС‚РЅС‹Рµ Рё СЃ РѕС€РёР±РєР°РјРё)
        if not df_detail.empty:
            df_assignees = df_detail.groupby('РСЃРїРѕР»РЅРёС‚РµР»СЊ').agg(
                Р—Р°РґР°С‡=('РљР»СЋС‡', 'count'),
                РљРѕСЂСЂРµРєС‚РЅС‹С…=('РџСЂРѕР±Р»РµРјС‹', lambda x: (x == '').sum()),
                РЎ_РѕС€РёР±РєР°РјРё=('РџСЂРѕР±Р»РµРјС‹', lambda x: (x != '').sum()),
                **{'Р¤Р°РєС‚ (С‡)': ('Р¤Р°РєС‚ (С‡)', 'sum'), 'РћС†РµРЅРєР° (С‡)': ('РћС†РµРЅРєР° (С‡)', 'sum')}
            ).reset_index()
            df_assignees['РћС‚РєР»РѕРЅРµРЅРёРµ'] = df_assignees['РћС†РµРЅРєР° (С‡)'] - df_assignees['Р¤Р°РєС‚ (С‡)']
            df_assignees = df_assignees.round(2)
            df_assignees = df_assignees.sort_values(by='Р¤Р°РєС‚ (С‡)', ascending=False)
            
            # Р”РѕР±Р°РІР»СЏРµРј РєРѕР»РѕРЅРєСѓ ID РґР»СЏ extra_verbose (РёР·РІР»РµРєР°РµРј РёР· "РСЃРїРѕР»РЅРёС‚РµР»СЊ [ID]")
            if extra_verbose:
                def extract_id(name):
                    if '[' in name and ']' in name:
                        return name.split('[')[-1].split(']')[0]
                    return ''
                df_assignees.insert(1, 'ID', df_assignees['РСЃРїРѕР»РЅРёС‚РµР»СЊ'].apply(extract_id))
        else:
            df_assignees = pd.DataFrame()
    else:
        df_assignees = pd.DataFrame()
    
    result = {
        'period': f"{start_date_str} вЂ” {end_date_str}",
        'blocks': blocks or list(REPORT_BLOCKS.keys()),
        'total_projects': len(df_summary),
        'total_tasks': len(df_detail),
        'total_correct': len(df_detail[df_detail['РџСЂРѕР±Р»РµРјС‹'] == '']) if not df_detail.empty else 0,
        'total_issues': len(df_issues),
        'total_spent': df_summary['Р¤Р°РєС‚ (С‡)'].sum() if not df_summary.empty else 0,
        'total_estimated': df_summary['РћС†РµРЅРєР° (С‡)'].sum() if not df_summary.empty else 0,
    }
    
    if 'summary' in result['blocks']:
        result['summary'] = df_summary
    if 'assignees' in result['blocks']:
        result['assignees'] = df_assignees
    if 'detail' in result['blocks']:
        result['detail'] = df_detail
    if 'issues' in result['blocks']:
        result['issues'] = df_issues
    
    # Р¤РёР»СЊС‚СЂР°С†РёСЏ РєРѕР»РѕРЅРѕРє РґР»СЏ РєР°Р¶РґРѕРіРѕ Р±Р»РѕРєР°
    if 'detail' in result['blocks'] and not result['detail'].empty:
        cols = get_column_order('detail', extra_verbose)
        available_cols = [c for c in cols if c in result['detail'].columns]
        result['detail'] = result['detail'][available_cols]
    
    if 'issues' in result['blocks'] and not result['issues'].empty:
        cols = get_column_order('issues', extra_verbose)
        available_cols = [c for c in cols if c in result['issues'].columns]
        result['issues'] = result['issues'][available_cols]
    
    return result

def generate_excel(report_data: Dict[str, Any], output: Optional[Union[str, io.BytesIO]] = None) -> Union[str, io.BytesIO]:
    """
    Р’С‹РіСЂСѓР¶Р°РµС‚ РѕС‚С‡С‘С‚ РІ Excel.
    
    Args:
        report_data: Р”Р°РЅРЅС‹Рµ РѕС‚С‡С‘С‚Р°
        output: РџСѓС‚СЊ Рє С„Р°Р№Р»Сѓ РёР»Рё BytesIO РѕР±СЉРµРєС‚
        
    Returns:
        Union[str, io.BytesIO]: РРјСЏ С„Р°Р№Р»Р° РёР»Рё BytesIO РѕР±СЉРµРєС‚
    """
    if output is None:
        output = f"jira_report_{report_data['period'].replace(' вЂ” ', '_to_').replace(' ', '')}.xlsx"

    writer = pd.ExcelWriter(output, engine='openpyxl')
    
    try:
        if 'summary' in report_data and not report_data['summary'].empty:
            report_data['summary'].to_excel(writer, sheet_name='РЎРІРѕРґРєР°', index=False)
        if 'assignees' in report_data and not report_data['assignees'].empty:
            report_data['assignees'].to_excel(writer, sheet_name='РСЃРїРѕР»РЅРёС‚РµР»Рё', index=False)
        if 'detail' in report_data and not report_data['detail'].empty:
            report_data['detail'].to_excel(writer, sheet_name='Р”РµС‚Р°Р»Рё', index=False)
        if 'issues' in report_data and not report_data['issues'].empty:
            report_data['issues'].to_excel(writer, sheet_name='РџСЂРѕР±Р»РµРјС‹', index=False)
    finally:
        writer.close()
    
    return output

# =============================================
# РљРћРќРЎРћР›Р¬РќР«Р™ Р—РђРџРЈРЎРљ
# =============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Р“РµРЅРµСЂР°С†РёСЏ РѕС‚С‡С‘С‚Р° РїРѕ Р·Р°РєСЂС‹С‚С‹Рј Р·Р°РґР°С‡Р°Рј РёР· Jira',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Р‘Р›РћРљР РћРўР§РЃРўРђ:
  summary   - РЎРІРѕРґРєР° РїРѕ РїСЂРѕРµРєС‚Р°Рј
  assignees - РќР°РіСЂСѓР·РєР° РїРѕ РёСЃРїРѕР»РЅРёС‚РµР»СЏРј
  detail    - Р”РµС‚Р°Р»РёР·Р°С†РёСЏ РїРѕ Р·Р°РґР°С‡Р°Рј
  issues    - РџСЂРѕР±Р»РµРјРЅС‹Рµ Р·Р°РґР°С‡Рё

РџР РРњР•Р Р«:
  python3 jira_report.py -e
  python3 jira_report.py -b summary,assignees -e
  python3 jira_report.py -p WEB -a "РРІР°РЅРѕРІ" -b detail -e
  python3 jira_report.py -b issues -vv
        '''
    )
    parser.add_argument('-p', '--project', type=str, help='РљР»СЋС‡ РїСЂРѕРµРєС‚Р°')
    parser.add_argument('-s', '--start-date', type=str, help='Р”Р°С‚Р° РЅР°С‡Р°Р»Р° (Р“Р“Р“Р“-РњРњ-Р”Р”)')
    parser.add_argument('-d', '--days', type=int, default=30, help='РџРµСЂРёРѕРґ РІ РґРЅСЏС…')
    parser.add_argument('-a', '--assignee', type=str, help='Р¤РёР»СЊС‚СЂ РїРѕ РёСЃРїРѕР»РЅРёС‚РµР»СЋ')
    parser.add_argument('-b', '--blocks', type=str, help='Р‘Р»РѕРєРё РѕС‚С‡С‘С‚Р° (С‡РµСЂРµР· Р·Р°РїСЏС‚СѓСЋ)')
    parser.add_argument('-e', '--excel', action='store_true', help='Р’С‹РіСЂСѓР·РєР° РІ Excel')
    parser.add_argument('-v', '--verbose', action='store_true', help='Р РµР¶РёРј РѕС‚Р»Р°РґРєРё')
    parser.add_argument('-vv', '--extra-verbose', action='store_true', help='РџРѕРєР°Р·С‹РІР°С‚СЊ ID Р·Р°РґР°С‡ РІРѕ РІСЃРµС… РѕС‚С‡С‘С‚Р°С…')
    args = parser.parse_args()
    
    blocks = None
    if args.blocks:
        blocks = [b.strip() for b in args.blocks.split(',')]
        invalid = [b for b in blocks if b not in REPORT_BLOCKS]
        if invalid:
            print(f"вќЊ РќРµРІРµСЂРЅС‹Рµ Р±Р»РѕРєРё: {invalid}")
            print(f"Р”РѕСЃС‚СѓРїРЅС‹Рµ: {list(REPORT_BLOCKS.keys())}")
            sys.exit(1)
    
    # РђРІС‚Рѕ-РѕРїСЂРµРґРµР»РµРЅРёРµ СЃС‚Р°С‚СѓСЃР° РїРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј
    if not CLOSED_STATUS_IDS or CLOSED_STATUS_IDS[0] == '':
        CLOSED_STATUS_IDS = get_closed_status_ids()
    
    print(f"рџ”Њ Р“РµРЅРµСЂР°С†РёСЏ РѕС‚С‡С‘С‚Р°...")
    if args.blocks:
        print(f"рџ“¦ Р‘Р»РѕРєРё: {', '.join(blocks)}")
    
    report = generate_report(
        project_key=args.project,
        start_date=args.start_date,
        days=args.days,
        assignee_filter=args.assignee,
        blocks=blocks,
        verbose=args.verbose,
        extra_verbose=args.extra_verbose
    )
    
    print("\n" + "="*100)
    print(f"рџ“‹ РћРўР§РЃРў Р—Рђ {report['period']}")
    print("="*100)
    
    if 'summary' in report:
        print("\nрџ“Љ РЎР’РћР”РљРђ РџРћ РџР РћР•РљРўРђРњ:")
        print("="*100)
        print(report['summary'].to_string(index=False))
    
    if 'assignees' in report and not report['assignees'].empty:
        print("\nрџ‘¤ РќРђР“Р РЈР—РљРђ РџРћ РРЎРџРћР›РќРРўР•Р›РЇРњ:")
        print("="*100)
        print(report['assignees'].to_string(index=False))
    
    if 'detail' in report and not report['detail'].empty:
        if args.verbose:
            print("\nрџ“ќ Р”Р•РўРђР›РР—РђР¦РРЇ РџРћ Р—РђР”РђР§РђРњ:")
            print("="*100)
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            print(report['detail'].to_string(index=False))
    
    if 'issues' in report and not report['issues'].empty:
        print("\nвљ пёЏ РџР РћР‘Р›Р•РњРќР«Р• Р—РђР”РђР§Р:")
        print("="*100)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(report['issues'].to_string(index=False))
    
    print("\n" + "="*100)
    print(f"рџ’° Р’РЎР•Р“Рћ РџР РћР•РљРўРћР’: {report['total_projects']}")
    print(f"рџ“¦ Р’РЎР•Р“Рћ Р—РђР”РђР§:    {report['total_tasks']}")
    print(f"вњ… РљРћР Р•РљРўРќР«РҐ:      {report['total_correct']}")
    print(f"вљ пёЏ  РџР РћР‘Р›Р•РњРќР«РҐ:     {report['total_issues']}")
    print(f"вЏ±пёЏ  Р’РЎР•Р“Рћ Р¤РђРљРў:     {report['total_spent']:.2f} С‡.")
    print(f"рџ“Џ Р’РЎР•Р“Рћ РћР¦Р•РќРљРђ:    {report['total_estimated']:.2f} С‡.")
    print("="*100)
    
    if args.excel:
        filename = generate_excel(report)
        print(f"\nвњ… РћС‚С‡С‘С‚ СЃРѕС…СЂР°РЅС‘РЅ: {filename}")