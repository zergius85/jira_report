п»ї# -*- coding: utf-8 -*-
"""
Jira Report System РІР‚вЂќ Р Р‡Р Т‘РЎР‚Р С• Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР С•Р Р†

Р СљР С•Р Т‘РЎС“Р В»РЎРЉ Р Т‘Р В»РЎРЏ РЎРѓР В±Р С•РЎР‚Р В°, Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р С‘ Р С‘ Р Р†РЎвЂ№Р С–РЎР‚РЎС“Р В·Р С”Р С‘ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ Р С‘Р В· Jira.
Р СџР С•Р Т‘Р Т‘Р ВµРЎР‚Р В¶Р С‘Р Р†Р В°Р ВµРЎвЂљ Р С”Р С•Р Р…РЎРѓР С•Р В»РЎРЉР Р…РЎвЂ№Р в„– РЎР‚Р ВµР В¶Р С‘Р С Р С‘ РЎР‚Р В°Р В±Р С•РЎвЂљРЎС“ РЎвЂЎР ВµРЎР‚Р ВµР В· Web-Р С‘Р Р…РЎвЂљР ВµРЎР‚РЎвЂћР ВµР в„–РЎРѓ.
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

# Р ВР СР С—Р С•РЎР‚РЎвЂљР С‘РЎР‚РЎС“Р ВµР С Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р в„–Р С”Р С‘ Р С‘Р В· config.py
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

# --- Р СњР С’Р РЋР СћР В Р С›Р в„ўР С™Р С’ Р вЂєР С›Р вЂњР ВР В Р С›Р вЂ™Р С’Р СњР ВР Р‡ ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT
)
logger = logging.getLogger(__name__)

# --- Р СњР С’Р РЋР СћР В Р С›Р в„ўР С™Р С’ SSL ---
if not SSL_VERIFY:
    logger.warning("РІС™В РїС‘РЏ  Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° SSL Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р В° (SSL_VERIFY=false)")
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    os.environ['CURL_CA_BUNDLE'] = ''
    warnings.simplefilter('ignore', InsecureRequestWarning)
else:
    logger.info("РІСљвЂ¦ Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° SSL Р Р†Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р В°")

def validate_config() -> Tuple[bool, List[str]]:
    """
    Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµРЎвЂљ Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…Р С•РЎРѓРЎвЂљРЎРЉ Р С”Р С•Р Р…РЎвЂћР С‘Р С–РЎС“РЎР‚Р В°РЎвЂ Р С‘Р С‘.
    
    Returns:
        Tuple[bool, List[str]]: (РЎС“РЎРѓР С—Р ВµРЎвЂ¦, РЎРѓР С—Р С‘РЎРѓР С•Р С” Р С•РЎв‚¬Р С‘Р В±Р С•Р С”)
    """
    errors = []
    
    if not JIRA_SERVER:
        errors.append("Р СњР Вµ РЎС“Р С”Р В°Р В·Р В°Р Р… JIRA_SERVER Р Р† .env")
    if not JIRA_USER:
        errors.append("Р СњР Вµ РЎС“Р С”Р В°Р В·Р В°Р Р… JIRA_USER Р Р† .env")
    if not JIRA_PASS:
        errors.append("Р СњР Вµ РЎС“Р С”Р В°Р В·Р В°Р Р… JIRA_PASS Р Р† .env")
    
    return (len(errors) == 0, errors)


def get_jira_connection() -> JIRA:
    """
    Р Р€РЎРѓРЎвЂљР В°Р Р…Р В°Р Р†Р В»Р С‘Р Р†Р В°Р ВµРЎвЂљ РЎРѓР С•Р ВµР Т‘Р С‘Р Р…Р ВµР Р…Р С‘Р Вµ РЎРѓ Jira.
    
    Returns:
        JIRA: Р С›Р В±РЎР‰Р ВµР С”РЎвЂљ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ Р С” Jira
        
    Raises:
        ConnectionError: Р СџРЎР‚Р С‘ Р С•РЎв‚¬Р С‘Р В±Р С”Р Вµ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ
    """
    try:
        logger.info(f"СЂСџвЂќРЉ Р СџР С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘Р Вµ Р С” Jira: {JIRA_SERVER}")
        
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
        
        # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ
        jira.myself()
        logger.info("РІСљвЂ¦ Р Р€РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С•Р Вµ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘Р Вµ Р С” Jira")
        return jira
        
    except JIRAError as e:
        logger.error(f"РІСњРЉ Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ Р С” Jira: {e.text}")
        raise ConnectionError(f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР С‘РЎвЂљРЎРЉРЎРѓРЎРЏ Р С” Jira: {e.text}")
    except Exception as e:
        logger.error(f"РІСњРЉ Р СњР ВµР С‘Р В·Р Р†Р ВµРЎРѓРЎвЂљР Р…Р В°РЎРЏ Р С•РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ: {e}")
        raise ConnectionError(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ: {e}")

def get_default_start_date() -> datetime:
    """
    Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ Р Т‘Р В°РЎвЂљРЎС“ Р Р…Р В°РЎвЂЎР В°Р В»Р В° Р С—Р С• РЎС“Р СР С•Р В»РЎвЂЎР В°Р Р…Р С‘РЎР‹ (1 РЎвЂЎР С‘РЎРѓР В»Р С• Р С—РЎР‚Р С•РЎв‚¬Р В»Р С•Р С–Р С• Р СР ВµРЎРѓРЎРЏРЎвЂ Р В°).
    
    Returns:
        datetime: Р вЂќР В°РЎвЂљР В° Р Р…Р В°РЎвЂЎР В°Р В»Р В°
    """
    today = datetime.now()
    if today.month == 1:
        return datetime(today.year - 1, 12, 1)
    else:
        return datetime(today.year, today.month - 1, 1)


def convert_seconds_to_hours(seconds: Optional[int]) -> float:
    """
    Р С™Р С•Р Р…Р Р†Р ВµРЎР‚РЎвЂљР С‘РЎР‚РЎС“Р ВµРЎвЂљ РЎРѓР ВµР С”РЎС“Р Р…Р Т‘РЎвЂ№ Р Р† РЎвЂЎР В°РЎРѓРЎвЂ№.
    
    Args:
        seconds: Р вЂ™РЎР‚Р ВµР СРЎРЏ Р Р† РЎРѓР ВµР С”РЎС“Р Р…Р Т‘Р В°РЎвЂ¦
        
    Returns:
        float: Р вЂ™РЎР‚Р ВµР СРЎРЏ Р Р† РЎвЂЎР В°РЎРѓР В°РЎвЂ¦
    """
    if seconds is None:
        return 0.0
    return round(seconds / 3600, 2)


def get_closed_status_ids() -> List[str]:
    """
    Р С’Р Р†РЎвЂљР С•Р СР В°РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С‘ Р С•Р С—РЎР‚Р ВµР Т‘Р ВµР В»РЎРЏР ВµРЎвЂљ ID РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР В° "Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ" Р Р† Jira.
    Р С™РЎРЊРЎв‚¬Р С‘РЎР‚РЎС“Р ВµРЎвЂљ РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ Р Р† .env Р Т‘Р В»РЎРЏ Р С—Р С•РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂ°Р С‘РЎвЂ¦ Р В·Р В°Р С—РЎС“РЎРѓР С”Р С•Р Р†.
    
    Returns:
        List[str]: Р РЋР С—Р С‘РЎРѓР С•Р С” ID РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР С•Р Р†
    """
    if CLOSED_STATUS_IDS and CLOSED_STATUS_IDS[0] != '':
        logger.info(f"РІСљвЂ¦ ID РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР В° 'Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ' Р В·Р В°Р С–РЎР‚РЎС“Р В¶Р ВµР Р… Р С‘Р В· .env: {CLOSED_STATUS_IDS}")
        return CLOSED_STATUS_IDS

    logger.info("СЂСџвЂќРЊ Р С›Р С—РЎР‚Р ВµР Т‘Р ВµР В»Р ВµР Р…Р С‘Р Вµ ID РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР В° 'Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ' Р Р† Jira...")

    try:
        jira = get_jira_connection()
        statuses = jira.statuses()

        closed_ids = []
        for status in statuses:
            if status.name.lower() in ['Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ', 'closed', 'Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљР С•']:
                closed_ids.append(status.id)
                logger.info(f"   СЂСџвЂњРЉ Р СњР В°Р в„–Р Т‘Р ВµР Р… РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ: {status.name} (ID: {status.id})")

        if closed_ids:
            save_closed_status_ids(closed_ids)
            logger.info(f"РІСљвЂ¦ ID РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р ВµР Р…РЎвЂ№ Р Р† .env: {closed_ids}")
            return closed_ids
        else:
            logger.warning("РІС™В РїС‘РЏ  Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ 'Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ' Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р….")
            return []

    except Exception as e:
        logger.error(f"РІСњРЉ Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С•Р С—РЎР‚Р ВµР Т‘Р ВµР В»Р ВµР Р…Р С‘РЎРЏ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР В°: {e}")
        return []


def save_closed_status_ids(status_ids: List[str]) -> None:
    """
    Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµРЎвЂљ ID РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР С•Р Р† Р Р† РЎвЂћР В°Р в„–Р В» .env.

    Args:
        status_ids: Р РЋР С—Р С‘РЎРѓР С•Р С” ID Р Т‘Р В»РЎРЏ РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р ВµР Р…Р С‘РЎРЏ
    """
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

    env_content = ''
    if os.path.exists(env_path):
        # Р В§Р С‘РЎвЂљР В°Р ВµР С Р Р† UTF-8, Р ВµРЎРѓР В»Р С‘ Р Р…Р Вµ Р С—Р С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљРЎРѓРЎРЏ РІР‚вЂќ Р С—РЎР‚Р С•Р В±РЎС“Р ВµР С cp1251 (Windows)
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

    # Р СџР С‘РЎв‚¬Р ВµР С Р Р† UTF-8 (РЎРѓРЎвЂљР В°Р Р…Р Т‘Р В°РЎР‚РЎвЂљ Р Т‘Р В»РЎРЏ python-dotenv)
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)

def validate_issue(issue: Any, jira: Optional[JIRA] = None) -> List[str]:
    """
    Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµРЎвЂљ Р В·Р В°Р Т‘Р В°РЎвЂЎРЎС“ Р Р…Р В° Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…Р С•РЎРѓРЎвЂљРЎРЉ Р В·Р В°Р С—Р С•Р В»Р Р…Р ВµР Р…Р С‘РЎРЏ.

    Args:
        issue: Р С›Р В±РЎР‰Р ВµР С”РЎвЂљ Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘ Jira
        jira: Р С›Р В±РЎР‰Р ВµР С”РЎвЂљ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ Р С” Jira (Р Р…РЎС“Р В¶Р ВµР Р… Р Т‘Р В»РЎРЏ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р С‘ changelog)

    Returns:
        List[str]: Р РЋР С—Р С‘РЎРѓР С•Р С” Р С—РЎР‚Р С•Р В±Р В»Р ВµР С
    """
    problems = []

    # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° Р Т‘Р В°РЎвЂљРЎвЂ№ РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р С‘РЎРЏ
    if not issue.fields.resolutiondate:
        problems.append('Р СњР ВµРЎвЂљ Р Т‘Р В°РЎвЂљРЎвЂ№ РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р С‘РЎРЏ')

    # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° РЎвЂћР В°Р С”РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р С–Р С• Р Р†РЎР‚Р ВµР СР ВµР Р…Р С‘
    if issue.fields.timespent is None or issue.fields.timespent == 0:
        problems.append('Р СњР ВµРЎвЂљ РЎвЂћР В°Р С”РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р С–Р С• Р Р†РЎР‚Р ВµР СР ВµР Р…Р С‘')

    # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР В° "Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ" Р С—Р С• ID
    if issue.fields.status:
        status_id = issue.fields.status.id
        status_name = issue.fields.status.name

        # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С changelog Р СћР С›Р вЂєР В¬Р С™Р С› Р ВµРЎРѓР В»Р С‘ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ "Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ"
        if status_id in CLOSED_STATUS_IDS:
            is_correct_close = False
            
            # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С, Р Р…Р Вµ РЎРЏР Р†Р В»РЎРЏР ВµРЎвЂљРЎРѓРЎРЏ Р В»Р С‘ Р С‘РЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ Р С‘РЎРѓР С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘Р ВµР С (holin Р С‘ РЎвЂљ.Р С—.)
            assignee_name = ''
            if issue.fields.assignee:
                assignee_name = issue.fields.assignee.name if hasattr(issue.fields.assignee, 'name') else issue.fields.assignee.displayName

            for exc in EXCLUDED_ASSIGNEE_CLOSE:
                if exc.lower() in assignee_name.lower():
                    is_correct_close = True
                    break
            
            # Р вЂўРЎРѓР В»Р С‘ Р Р…Р Вµ Р С‘РЎРѓР С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘Р Вµ, Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С changelog (Р С”РЎвЂљР С• Р С—Р ВµРЎР‚Р ВµР Р†РЎвЂР В» Р Р† "Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ")
            if not is_correct_close and jira:
                try:
                    # Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµР С Р С‘РЎРѓРЎвЂљР С•РЎР‚Р С‘РЎР‹ Р С—Р ВµРЎР‚Р ВµРЎвЂ¦Р С•Р Т‘Р С•Р Р† Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘
                    issue_with_changelog = jira.issue(issue.key, expand='changelog')
                    if hasattr(issue_with_changelog, 'changelog') and issue_with_changelog.changelog:
                        # Р ВРЎвЂ°Р ВµР С Р С—Р С•РЎРѓР В»Р ВµР Т‘Р Р…Р С‘Р в„– Р С—Р ВµРЎР‚Р ВµРЎвЂ¦Р С•Р Т‘ Р Р† РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ "Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ"
                        for history in reversed(issue_with_changelog.changelog.histories):
                            for item in history.items:
                                if item.field == 'status' and item.toString:
                                    # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С, Р В±РЎвЂ№Р В» Р В»Р С‘ РЎРЊРЎвЂљР С• Р С—Р ВµРЎР‚Р ВµРЎвЂ¦Р С•Р Т‘ Р Р† Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљРЎвЂ№Р в„– РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ
                                    if hasattr(item, 'to') and item.to in CLOSED_STATUS_IDS:
                                        # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С, Р С”РЎвЂљР С• РЎРѓР Т‘Р ВµР В»Р В°Р В» Р С—Р ВµРЎР‚Р ВµРЎвЂ¦Р С•Р Т‘
                                        author_name = ''
                                        if hasattr(history, 'author') and history.author:
                                            author_name = history.author.name if hasattr(history.author, 'name') else history.author.displayName
                                        
                                        # Р вЂўРЎРѓР В»Р С‘ Р С—Р ВµРЎР‚Р ВµРЎвЂ¦Р С•Р Т‘ РЎРѓР Т‘Р ВµР В»Р В°Р В» Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЉ Р Т‘Р ВµР СР С•Р Р…Р В° РІР‚вЂќ РЎРЊРЎвЂљР С• Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…Р С•
                                        if JIRA_USER and JIRA_USER.lower() in author_name.lower():
                                            is_correct_close = True
                                        break
                            if is_correct_close or (hasattr(item, 'to') and item.to in CLOSED_STATUS_IDS):
                                break
                except Exception as e:
                    # Р вЂўРЎРѓР В»Р С‘ Р Р…Р Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С—Р С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљРЎРЉ changelog, РЎРѓРЎвЂЎР С‘РЎвЂљР В°Р ВµР С РЎРЊРЎвЂљР С• Р С—РЎР‚Р С•Р В±Р В»Р ВµР СР С•Р в„–
                    logger.warning(f"РІС™В РїС‘РЏ  Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С—Р С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљРЎРЉ changelog Р Т‘Р В»РЎРЏ {issue.key}: {e}")
                    problems.append('Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С‘РЎвЂљРЎРЉ Р С‘РЎРѓРЎвЂљР С•РЎР‚Р С‘РЎР‹ Р С—Р ВµРЎР‚Р ВµРЎвЂ¦Р С•Р Т‘Р С•Р Р†')

            # Р вЂўРЎРѓР В»Р С‘ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ "Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ" Р С‘ Р Р…Р Вµ Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…Р С• Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ РІР‚вЂќ РЎРЊРЎвЂљР С• Р С—РЎР‚Р С•Р В±Р В»Р ВµР СР В°
            if not is_correct_close:
                problems.append(f"Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ '{status_name}' (ID: {status_id})")

    return problems


def get_column_order(block: str, extra_verbose: bool = False) -> List[str]:
    """
    Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ Р С—Р С•РЎР‚РЎРЏР Т‘Р С•Р С” Р С”Р С•Р В»Р С•Р Р…Р С•Р С” Р Т‘Р В»РЎРЏ Р С”Р В°Р В¶Р Т‘Р С•Р С–Р С• Р В±Р В»Р С•Р С”Р В°.

    Args:
        block: Р СњР В°Р В·Р Р†Р В°Р Р…Р С‘Р Вµ Р В±Р В»Р С•Р С”Р В° Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР В°
        extra_verbose: Р СџР С•Р С”Р В°Р В·РЎвЂ№Р Р†Р В°РЎвЂљРЎРЉ Р В»Р С‘ ID Р С•Р В±РЎР‰Р ВµР С”РЎвЂљР С•Р Р†

    Returns:
        List[str]: Р РЋР С—Р С‘РЎРѓР С•Р С” Р Р…Р В°Р В·Р Р†Р В°Р Р…Р С‘Р в„– Р С”Р С•Р В»Р С•Р Р…Р С•Р С”
    """
    if block == 'summary':
        if extra_verbose:
            return ['Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ (Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ)', 'ID', 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎ Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљР С•', 'Р С™Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№РЎвЂ¦', 'Р РЋ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°Р СР С‘', 'Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)', 'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)', 'Р С›РЎвЂљР С”Р В»Р С•Р Р…Р ВµР Р…Р С‘Р Вµ']
        return ['Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ (Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ)', 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎ Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљР С•', 'Р С™Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№РЎвЂ¦', 'Р РЋ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°Р СР С‘', 'Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)', 'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)', 'Р С›РЎвЂљР С”Р В»Р С•Р Р…Р ВµР Р…Р С‘Р Вµ']
    elif block == 'assignees':
        if extra_verbose:
            return ['Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ', 'ID', 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎ', 'Р С™Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№РЎвЂ¦', 'Р РЋ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°Р СР С‘', 'Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)', 'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)', 'Р С›РЎвЂљР С”Р В»Р С•Р Р…Р ВµР Р…Р С‘Р Вµ']
        return ['Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ', 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎ', 'Р С™Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№РЎвЂ¦', 'Р РЋ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°Р СР С‘', 'Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)', 'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)', 'Р С›РЎвЂљР С”Р В»Р С•Р Р…Р ВµР Р…Р С‘Р Вµ']
    elif block == 'detail':
        if extra_verbose:
            return ['URL', 'ID', 'Р вЂќР В°РЎвЂљР В° Р С‘РЎРѓР С—Р С•Р В»Р Р…Р ВµР Р…Р С‘РЎРЏ', 'Р вЂќР В°РЎвЂљР В° РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ', 'Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ', 'Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ', 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎР В°', 'Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ', 'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)', 'Р СћР С‘Р С—']
        return ['URL', 'Р вЂќР В°РЎвЂљР В° Р С‘РЎРѓР С—Р С•Р В»Р Р…Р ВµР Р…Р С‘РЎРЏ', 'Р вЂќР В°РЎвЂљР В° РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ', 'Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ', 'Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ', 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎР В°', 'Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ', 'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)', 'Р СћР С‘Р С—']
    elif block == 'issues':
        if extra_verbose:
            return ['URL', 'ID', 'Р вЂќР В°РЎвЂљР В° Р С‘РЎРѓР С—Р С•Р В»Р Р…Р ВµР Р…Р С‘РЎРЏ', 'Р вЂќР В°РЎвЂљР В° РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ', 'Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ', 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎР В°', 'Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ', 'Р С’Р Р†РЎвЂљР С•РЎР‚', 'Р СџРЎР‚Р С•Р В±Р В»Р ВµР СРЎвЂ№']
        return ['URL', 'Р вЂќР В°РЎвЂљР В° Р С‘РЎРѓР С—Р С•Р В»Р Р…Р ВµР Р…Р С‘РЎРЏ', 'Р вЂќР В°РЎвЂљР В° РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ', 'Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ', 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎР В°', 'Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ', 'Р С’Р Р†РЎвЂљР С•РЎР‚', 'Р СџРЎР‚Р С•Р В±Р В»Р ВµР СРЎвЂ№']
    else:
        return ['Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ', 'Р С™Р В»РЎР‹РЎвЂЎ', 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎР В°', 'Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ', 'Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ', 'Р вЂќР В°РЎвЂљР В° РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ', 'Р вЂќР В°РЎвЂљР В° Р С‘РЎРѓР С—Р С•Р В»Р Р…Р ВµР Р…Р С‘РЎРЏ', 'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)', 'Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)']
        
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
    Р вЂњР ВµР Р…Р ВµРЎР‚Р С‘РЎР‚РЎС“Р ВµРЎвЂљ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљ Р С—Р С• Р В·Р В°Р Т‘Р В°РЎвЂЎР В°Р С Jira.
    
    Args:
        project_key: Р С™Р В»РЎР‹РЎвЂЎ Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В° (None = Р Р†РЎРѓР Вµ Р С—РЎР‚Р С•Р ВµР С”РЎвЂљРЎвЂ№)
        start_date: Р вЂќР В°РЎвЂљР В° Р Р…Р В°РЎвЂЎР В°Р В»Р В° Р Р† РЎвЂћР С•РЎР‚Р СР В°РЎвЂљР Вµ Р вЂњР вЂњР вЂњР вЂњ-Р СљР Сљ-Р вЂќР вЂќ (None = Р С—РЎР‚Р С•РЎв‚¬Р В»РЎвЂ№Р в„– Р СР ВµРЎРѓРЎРЏРЎвЂ )
        days: Р С™Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р Т‘Р Р…Р ВµР в„– Р Т‘Р В»РЎРЏ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР В°
        assignee_filter: Р В¤Р С‘Р В»РЎРЉРЎвЂљРЎР‚ Р С—Р С• Р С‘РЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎР‹
        blocks: Р РЋР С—Р С‘РЎРѓР С•Р С” Р В±Р В»Р С•Р С”Р С•Р Р† Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР В° (None = Р Р†РЎРѓР Вµ)
        verbose: Р В Р ВµР В¶Р С‘Р С Р С•РЎвЂљР В»Р В°Р Т‘Р С”Р С‘
        extra_verbose: Р СџР С•Р С”Р В°Р В·РЎвЂ№Р Р†Р В°РЎвЂљРЎРЉ ID Р С•Р В±РЎР‰Р ВµР С”РЎвЂљР С•Р Р†
        
    Returns:
        Dict[str, Any]: Р РЋР В»Р С•Р Р†Р В°РЎР‚РЎРЉ РЎРѓ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р СР С‘ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР В°
    """
    # Р С’Р Р†РЎвЂљР С•-Р С•Р С—РЎР‚Р ВµР Т‘Р ВµР В»Р ВµР Р…Р С‘Р Вµ ID РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР В° "Р вЂ”Р В°Р С”РЎР‚РЎвЂ№РЎвЂљ"
    global CLOSED_STATUS_IDS
    if not CLOSED_STATUS_IDS or CLOSED_STATUS_IDS[0] == '':
        CLOSED_STATUS_IDS = get_closed_status_ids()

    # Р С›Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р В° Р Т‘Р В°РЎвЂљ
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date_obj = get_default_start_date()

    start_date_str = start_date_obj.strftime('%Y-%m-%d')
    end_date_obj = start_date_obj + timedelta(days=days - 1)
    end_date_str = end_date_obj.strftime('%Y-%m-%d')

    # Р вЂќР В»РЎРЏ Р С—РЎР‚Р С•Р В±Р В»Р ВµР СР Р…РЎвЂ№РЎвЂ¦ Р В·Р В°Р Т‘Р В°РЎвЂЎ: +2 Р СР ВµРЎРѓРЎРЏРЎвЂ Р В° Р С” Р С”Р С•Р Р…РЎвЂ РЎС“ Р С—Р ВµРЎР‚Р С‘Р С•Р Т‘Р В°
    issues_end_obj = start_date_obj + timedelta(days=days) + relativedelta(months=2)
    issues_end_str = issues_end_obj.strftime('%Y-%m-%d')

    jira = get_jira_connection()
    
    # Р РЋР С—Р С‘РЎРѓР С•Р С” Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР С•Р Р†
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
        
        # Р С›Р В±РЎвЂ№РЎвЂЎР Р…РЎвЂ№Р Вµ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљРЎвЂ№ - РЎвЂћР С‘Р В»РЎРЉРЎвЂљРЎР‚ Р С—Р С• resolved (Р Т‘Р В°РЎвЂљР В° Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљР С‘РЎРЏ)
        jql_normal = (f"project = {proj_key} "
                      f"AND resolved >= '{start_date_str}' "
                      f"AND resolved <= '{end_date_str}' "
                      f"ORDER BY resolved ASC")
        
        # Р СџРЎР‚Р С•Р В±Р В»Р ВµР СР Р…РЎвЂ№Р Вµ Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘ - РЎвЂћР С‘Р В»РЎРЉРЎвЂљРЎР‚ Р С—Р С• created + 2 Р СР ВµРЎРѓРЎРЏРЎвЂ Р В°
        jql_issues = (f"project = {proj_key} "
                      f"AND created >= '{start_date_str}' "
                      f"AND created <= '{issues_end_str}' "
                      f"ORDER BY created ASC")
        
        # Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµР С Р Р†РЎРѓР Вµ Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘ Р Т‘Р В»РЎРЏ Р С—РЎР‚Р С•Р В±Р В»Р ВµР СР Р…РЎвЂ№РЎвЂ¦ (Р В±Р С•Р В»РЎРЉРЎв‚¬Р С‘Р в„– Р С—Р ВµРЎР‚Р С‘Р С•Р Т‘)
        issues_all = jira.search_issues(jql_issues, maxResults=False, 
                                        fields='summary, assignee, timespent, timeoriginalestimate, resolutiondate, issuetype, duedate, status, created, creator')
        
        # Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµР С Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘ Р Т‘Р В»РЎРЏ Р С•Р В±РЎвЂ№РЎвЂЎР Р…РЎвЂ№РЎвЂ¦ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР С•Р Р† (Р СР ВµР Р…РЎРЉРЎв‚¬Р С‘Р в„– Р С—Р ВµРЎР‚Р С‘Р С•Р Т‘)
        issues_normal = jira.search_issues(jql_normal, maxResults=False, 
                                           fields='summary, assignee, timespent, timeoriginalestimate, resolutiondate, issuetype, duedate, status, created')
        
        # Р С›Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р В° Р Т‘Р В»РЎРЏ Р С•Р В±РЎвЂ№РЎвЂЎР Р…РЎвЂ№РЎвЂ¦ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР С•Р Р†
        proj_spent = 0.0
        proj_estimated = 0.0
        proj_correct = 0
        proj_issues = 0
        
        for issue in issues_normal:
            spent = convert_seconds_to_hours(issue.fields.timespent)
            estimated = convert_seconds_to_hours(issue.fields.timeoriginalestimate)
            
            issue_type = issue.fields.issuetype.name if issue.fields.issuetype else 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎР В°'
            assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Р вЂР ВµР В· Р С‘РЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЏ'
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
            
            # Р В¤Р С•РЎР‚Р СР С‘РЎР‚РЎС“Р ВµР С Р С•РЎвЂљР С•Р В±РЎР‚Р В°Р В¶Р В°Р ВµР СРЎвЂ№Р Вµ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘РЎРЏ РЎРѓ ID Р ВµРЎРѓР В»Р С‘ Р Р…РЎС“Р В¶Р Р…Р С•
            project_display = f"{proj_name} [{issue.fields.project.id}]" if extra_verbose and hasattr(issue.fields, 'project') and hasattr(issue.fields.project, 'id') else proj_name
            status_display = f"{status_full} [{issue.fields.status.id}]" if extra_verbose and issue.fields.status and hasattr(issue.fields.status, 'id') else status_full
            issue_type_display = f"{issue_type} [{issue.fields.issuetype.id}]" if extra_verbose and issue.fields.issuetype and hasattr(issue.fields.issuetype, 'id') else issue_type
            assignee_display = f"{assignee} [{issue.fields.assignee.id}]" if extra_verbose and issue.fields.assignee and hasattr(issue.fields.assignee, 'id') else assignee
            
            issue_data = {
                'URL': issue_url,
                'ID': issue_id,
                'Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ': project_display,
                'Р С™Р В»РЎР‹РЎвЂЎ': issue.key,
                'Р СћР С‘Р С—': issue_type_display,
                'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎР В°': issue.fields.summary,
                'Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ': assignee_display,
                'Р РЋРЎвЂљР В°РЎвЂљРЎС“РЎРѓ': status_display,
                'Р вЂќР В°РЎвЂљР В° РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ': created,
                'Р вЂќР В°РЎвЂљР В° Р С‘РЎРѓР С—Р С•Р В»Р Р…Р ВµР Р…Р С‘РЎРЏ': duedate,
                'Р вЂќР В°РЎвЂљР В° РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р С‘РЎРЏ': resolved,
                'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)': spent,
                'Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)': estimated,
                'Р СџРЎР‚Р С•Р В±Р В»Р ВµР СРЎвЂ№': ', '.join(problems) if problems else ''
            }
            
            all_issues_data.append(issue_data)
            
            if not problems:
                proj_spent += spent
                proj_estimated += estimated
                proj_correct += 1
            else:
                proj_issues += 1
            
            if problems:
                # Р вЂќР В»РЎРЏ Р С—РЎР‚Р С•Р В±Р В»Р ВµР СР Р…РЎвЂ№РЎвЂ¦ Р В·Р В°Р Т‘Р В°РЎвЂЎ Р В±Р ВµРЎР‚РЎвЂР С Р РЋР С›Р вЂ”Р вЂќР С’Р СћР вЂўР вЂєР Р‡ Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘ (creator)
                author = 'N/A'
                author_id = ''
                if hasattr(issue.fields, 'creator') and issue.fields.creator:
                    author = issue.fields.creator.displayName if hasattr(issue.fields.creator, 'displayName') else str(issue.fields.creator)
                    author_id = issue.fields.creator.id if hasattr(issue.fields.creator, 'id') else ''
                elif hasattr(issue.fields, 'author') and issue.fields.author:
                    author = issue.fields.author.displayName if hasattr(issue.fields.author, 'displayName') else str(issue.fields.author)
                    author_id = issue.fields.author.id if hasattr(issue.fields.author, 'id') else ''

                # Р В¤Р С•РЎР‚Р СР С‘РЎР‚РЎС“Р ВµР С Р С‘Р СРЎРЏ Р В°Р Р†РЎвЂљР С•РЎР‚Р В° РЎРѓ ID Р ВµРЎРѓР В»Р С‘ Р Р…РЎС“Р В¶Р Р…Р С•
                author_display = f"{author} [{author_id}]" if extra_verbose and author_id else author

                issue_data = {
                    'URL': issue_url,
                    'Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ': proj_name,
                    'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎР В°': issue.fields.summary,
                    'Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ': assignee,
                    'Р С’Р Р†РЎвЂљР С•РЎР‚': author_display,
                    'Р вЂќР В°РЎвЂљР В° РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ': created,
                    'Р вЂќР В°РЎвЂљР В° Р С‘РЎРѓР С—Р С•Р В»Р Р…Р ВµР Р…Р С‘РЎРЏ': duedate,
                    'Р СџРЎР‚Р С•Р В±Р В»Р ВµР СРЎвЂ№': ', '.join(problems)
                }
                # Р вЂќР С•Р В±Р В°Р Р†Р В»РЎРЏР ВµР С ID Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘ Р Т‘Р В»РЎРЏ extra_verbose
                if extra_verbose:
                    issue_data.insert(1, 'ID', issue.id)
                issues_with_problems.append(issue_data)
        
        if proj_correct > 0 or proj_issues > 0:
            summary_row = {
                'Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ (Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ)': proj_name,
                'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎ Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљР С•': proj_correct + proj_issues,
                'Р С™Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№РЎвЂ¦': proj_correct,
                'Р РЋ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°Р СР С‘': proj_issues,
                'Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)': round(proj_estimated, 2),
                'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)': round(proj_spent, 2),
                'Р С›РЎвЂљР С”Р В»Р С•Р Р…Р ВµР Р…Р С‘Р Вµ': round(proj_estimated - proj_spent, 2)
            }
            # Р вЂќР С•Р В±Р В°Р Р†Р В»РЎРЏР ВµР С ID Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В° Р Т‘Р В»РЎРЏ extra_verbose
            if extra_verbose:
                # Р вЂР ВµРЎР‚РЎвЂР С ID Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В° Р С‘Р В· Р С—Р ВµРЎР‚Р Р†Р С•Р в„– Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘
                proj_id = issues_normal[0].fields.project.id if issues_normal else ''
                summary_row.insert(1, 'ID', proj_id)
            summary_data.append(summary_row)
    
    df_detail = pd.DataFrame(all_issues_data)
    df_summary = pd.DataFrame(summary_data)
    df_issues = pd.DataFrame(issues_with_problems)
    
    # Р РЋР С•РЎР‚РЎвЂљР С‘РЎР‚Р С•Р Р†Р С”Р В° Р С‘ Р С–РЎР‚РЎС“Р С—Р С—Р С‘РЎР‚Р С•Р Р†Р С”Р В°
    if not df_detail.empty:
        df_detail = df_detail.sort_values(by=['Р СћР С‘Р С—', 'Р СџРЎР‚Р С•Р ВµР С”РЎвЂљ', 'Р вЂќР В°РЎвЂљР В° РЎР‚Р ВµРЎв‚¬Р ВµР Р…Р С‘РЎРЏ'], ascending=[True, True, True])

        # Р вЂњРЎР‚РЎС“Р С—Р С—Р С‘РЎР‚Р С•Р Р†Р С”Р В° Р С—Р С• Р С‘РЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЏР С - Р РЋР В§Р ВР СћР С’Р вЂўР Сљ Р вЂ™Р РЋР вЂў Р вЂ”Р С’Р вЂќР С’Р В§Р В (РЎР‚Р В°Р В·Р Т‘Р ВµР В»РЎРЏР ВµР С Р Р…Р В° Р С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№Р Вµ Р С‘ РЎРѓ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°Р СР С‘)
        if not df_detail.empty:
            df_assignees = df_detail.groupby('Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ').agg(
                tasks_count=('Р С™Р В»РЎР‹РЎвЂЎ', 'count'),
                correct_count=('Р СџРЎР‚Р С•Р В±Р В»Р ВµР СРЎвЂ№', lambda x: (x == '').sum()),
                issues_count=('Р СџРЎР‚Р С•Р В±Р В»Р ВµР СРЎвЂ№', lambda x: (x != '').sum()),
                fact_sum=('Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)', 'sum'),
                estimate_sum=('Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)', 'sum')
            ).reset_index()
            # Р СџР ВµРЎР‚Р ВµР С‘Р СР ВµР Р…Р С•Р Р†РЎвЂ№Р Р†Р В°Р ВµР С Р С”Р С•Р В»Р С•Р Р…Р С”Р С‘ Р С•Р В±РЎР‚Р В°РЎвЂљР Р…Р С• Р Р† Р С”Р С‘РЎР‚Р С‘Р В»Р В»Р С‘РЎвЂ РЎС“ Р Т‘Р В»РЎРЏ Р С•РЎвЂљР С•Р В±РЎР‚Р В°Р В¶Р ВµР Р…Р С‘РЎРЏ
            df_assignees = df_assignees.rename(columns={
                'tasks_count': 'Р вЂ”Р В°Р Т‘Р В°РЎвЂЎ',
                'correct_count': 'Р С™Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№РЎвЂ¦',
                'issues_count': 'Р РЋ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°Р СР С‘',
                'fact_sum': 'Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)',
                'estimate_sum': 'Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)'
            })
            df_assignees['Р С›РЎвЂљР С”Р В»Р С•Р Р…Р ВµР Р…Р С‘Р Вµ'] = df_assignees['Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)'] - df_assignees['Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)']
            df_assignees = df_assignees.round(2)
            df_assignees = df_assignees.sort_values(by='Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)', ascending=False)
            
            # Р вЂќР С•Р В±Р В°Р Р†Р В»РЎРЏР ВµР С Р С”Р С•Р В»Р С•Р Р…Р С”РЎС“ ID Р Т‘Р В»РЎРЏ extra_verbose (Р С‘Р В·Р Р†Р В»Р ВµР С”Р В°Р ВµР С Р С‘Р В· "Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ [ID]")
            if extra_verbose:
                def extract_id(name):
                    if '[' in name and ']' in name:
                        return name.split('[')[-1].split(']')[0]
                    return ''
                df_assignees.insert(1, 'ID', df_assignees['Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЉ'].apply(extract_id))
        else:
            df_assignees = pd.DataFrame()
    else:
        df_assignees = pd.DataFrame()
    
    result = {
        'period': f"{start_date_str} РІР‚вЂќ {end_date_str}",
        'blocks': blocks or list(REPORT_BLOCKS.keys()),
        'total_projects': len(df_summary),
        'total_tasks': len(df_detail),
        'total_correct': len(df_detail[df_detail['Р СџРЎР‚Р С•Р В±Р В»Р ВµР СРЎвЂ№'] == '']) if not df_detail.empty else 0,
        'total_issues': len(df_issues),
        'total_spent': df_summary['Р В¤Р В°Р С”РЎвЂљ (РЎвЂЎ)'].sum() if not df_summary.empty else 0,
        'total_estimated': df_summary['Р С›РЎвЂ Р ВµР Р…Р С”Р В° (РЎвЂЎ)'].sum() if not df_summary.empty else 0,
    }
    
    if 'summary' in result['blocks']:
        result['summary'] = df_summary
    if 'assignees' in result['blocks']:
        result['assignees'] = df_assignees
    if 'detail' in result['blocks']:
        result['detail'] = df_detail
    if 'issues' in result['blocks']:
        result['issues'] = df_issues
    
    # Р В¤Р С‘Р В»РЎРЉРЎвЂљРЎР‚Р В°РЎвЂ Р С‘РЎРЏ Р С”Р С•Р В»Р С•Р Р…Р С•Р С” Р Т‘Р В»РЎРЏ Р С”Р В°Р В¶Р Т‘Р С•Р С–Р С• Р В±Р В»Р С•Р С”Р В°
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
    Р вЂ™РЎвЂ№Р С–РЎР‚РЎС“Р В¶Р В°Р ВµРЎвЂљ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљ Р Р† Excel.
    
    Args:
        report_data: Р вЂќР В°Р Р…Р Р…РЎвЂ№Р Вµ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР В°
        output: Р СџРЎС“РЎвЂљРЎРЉ Р С” РЎвЂћР В°Р в„–Р В»РЎС“ Р С‘Р В»Р С‘ BytesIO Р С•Р В±РЎР‰Р ВµР С”РЎвЂљ
        
    Returns:
        Union[str, io.BytesIO]: Р ВР СРЎРЏ РЎвЂћР В°Р в„–Р В»Р В° Р С‘Р В»Р С‘ BytesIO Р С•Р В±РЎР‰Р ВµР С”РЎвЂљ
    """
    if output is None:
        output = f"jira_report_{report_data['period'].replace(' РІР‚вЂќ ', '_to_').replace(' ', '')}.xlsx"

    writer = pd.ExcelWriter(output, engine='openpyxl')
    
    try:
        if 'summary' in report_data and not report_data['summary'].empty:
            report_data['summary'].to_excel(writer, sheet_name='Р РЋР Р†Р С•Р Т‘Р С”Р В°', index=False)
        if 'assignees' in report_data and not report_data['assignees'].empty:
            report_data['assignees'].to_excel(writer, sheet_name='Р ВРЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»Р С‘', index=False)
        if 'detail' in report_data and not report_data['detail'].empty:
            report_data['detail'].to_excel(writer, sheet_name='Р вЂќР ВµРЎвЂљР В°Р В»Р С‘', index=False)
        if 'issues' in report_data and not report_data['issues'].empty:
            report_data['issues'].to_excel(writer, sheet_name='Р СџРЎР‚Р С•Р В±Р В»Р ВµР СРЎвЂ№', index=False)
    finally:
        writer.close()
    
    return output

# =============================================
# Р С™Р С›Р СњР РЋР С›Р вЂєР В¬Р СњР В«Р в„ў Р вЂ”Р С’Р СџР Р€Р РЋР С™
# =============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Р вЂњР ВµР Р…Р ВµРЎР‚Р В°РЎвЂ Р С‘РЎРЏ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР В° Р С—Р С• Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљРЎвЂ№Р С Р В·Р В°Р Т‘Р В°РЎвЂЎР В°Р С Р С‘Р В· Jira',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Р вЂР вЂєР С›Р С™Р В Р С›Р СћР В§Р РѓР СћР С’:
  summary   - Р РЋР Р†Р С•Р Т‘Р С”Р В° Р С—Р С• Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В°Р С
  assignees - Р СњР В°Р С–РЎР‚РЎС“Р В·Р С”Р В° Р С—Р С• Р С‘РЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎРЏР С
  detail    - Р вЂќР ВµРЎвЂљР В°Р В»Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ Р С—Р С• Р В·Р В°Р Т‘Р В°РЎвЂЎР В°Р С
  issues    - Р СџРЎР‚Р С•Р В±Р В»Р ВµР СР Р…РЎвЂ№Р Вµ Р В·Р В°Р Т‘Р В°РЎвЂЎР С‘

Р СџР В Р ВР СљР вЂўР В Р В«:
  python3 jira_report.py -e
  python3 jira_report.py -b summary,assignees -e
  python3 jira_report.py -p WEB -a "Р ВР Р†Р В°Р Р…Р С•Р Р†" -b detail -e
  python3 jira_report.py -b issues -vv
        '''
    )
    parser.add_argument('-p', '--project', type=str, help='Р С™Р В»РЎР‹РЎвЂЎ Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В°')
    parser.add_argument('-s', '--start-date', type=str, help='Р вЂќР В°РЎвЂљР В° Р Р…Р В°РЎвЂЎР В°Р В»Р В° (Р вЂњР вЂњР вЂњР вЂњ-Р СљР Сљ-Р вЂќР вЂќ)')
    parser.add_argument('-d', '--days', type=int, default=30, help='Р СџР ВµРЎР‚Р С‘Р С•Р Т‘ Р Р† Р Т‘Р Р…РЎРЏРЎвЂ¦')
    parser.add_argument('-a', '--assignee', type=str, help='Р В¤Р С‘Р В»РЎРЉРЎвЂљРЎР‚ Р С—Р С• Р С‘РЎРѓР С—Р С•Р В»Р Р…Р С‘РЎвЂљР ВµР В»РЎР‹')
    parser.add_argument('-b', '--blocks', type=str, help='Р вЂР В»Р С•Р С”Р С‘ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР В° (РЎвЂЎР ВµРЎР‚Р ВµР В· Р В·Р В°Р С—РЎРЏРЎвЂљРЎС“РЎР‹)')
    parser.add_argument('-e', '--excel', action='store_true', help='Р вЂ™РЎвЂ№Р С–РЎР‚РЎС“Р В·Р С”Р В° Р Р† Excel')
    parser.add_argument('-v', '--verbose', action='store_true', help='Р В Р ВµР В¶Р С‘Р С Р С•РЎвЂљР В»Р В°Р Т‘Р С”Р С‘')
    parser.add_argument('-vv', '--extra-verbose', action='store_true', help='Р СџР С•Р С”Р В°Р В·РЎвЂ№Р Р†Р В°РЎвЂљРЎРЉ ID Р В·Р В°Р Т‘Р В°РЎвЂЎ Р Р†Р С• Р Р†РЎРѓР ВµРЎвЂ¦ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР В°РЎвЂ¦')
    args = parser.parse_args()
    
    blocks = None
    if args.blocks:
        blocks = [b.strip() for b in args.blocks.split(',')]
        invalid = [b for b in blocks if b not in REPORT_BLOCKS]
        if invalid:
            print(f"РІСњРЉ Р СњР ВµР Р†Р ВµРЎР‚Р Р…РЎвЂ№Р Вµ Р В±Р В»Р С•Р С”Р С‘: {invalid}")
            print(f"Р вЂќР С•РЎРѓРЎвЂљРЎС“Р С—Р Р…РЎвЂ№Р Вµ: {list(REPORT_BLOCKS.keys())}")
            sys.exit(1)
    
    # Р С’Р Р†РЎвЂљР С•-Р С•Р С—РЎР‚Р ВµР Т‘Р ВµР В»Р ВµР Р…Р С‘Р Вµ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР В° Р С—Р ВµРЎР‚Р ВµР Т‘ Р В·Р В°Р С—РЎС“РЎРѓР С”Р С•Р С
    if not CLOSED_STATUS_IDS or CLOSED_STATUS_IDS[0] == '':
        CLOSED_STATUS_IDS = get_closed_status_ids()
    
    print(f"СЂСџвЂќРЉ Р вЂњР ВµР Р…Р ВµРЎР‚Р В°РЎвЂ Р С‘РЎРЏ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљР В°...")
    if args.blocks:
        print(f"СЂСџвЂњВ¦ Р вЂР В»Р С•Р С”Р С‘: {', '.join(blocks)}")
    
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
    print(f"СЂСџвЂњвЂ№ Р С›Р СћР В§Р РѓР Сћ Р вЂ”Р С’ {report['period']}")
    print("="*100)
    
    if 'summary' in report:
        print("\nСЂСџвЂњР‰ Р РЋР вЂ™Р С›Р вЂќР С™Р С’ Р СџР С› Р СџР В Р С›Р вЂўР С™Р СћР С’Р Сљ:")
        print("="*100)
        print(report['summary'].to_string(index=False))
    
    if 'assignees' in report and not report['assignees'].empty:
        print("\nСЂСџвЂВ¤ Р СњР С’Р вЂњР В Р Р€Р вЂ”Р С™Р С’ Р СџР С› Р ВР РЋР СџР С›Р вЂєР СњР ВР СћР вЂўР вЂєР Р‡Р Сљ:")
        print("="*100)
        print(report['assignees'].to_string(index=False))
    
    if 'detail' in report and not report['detail'].empty:
        if args.verbose:
            print("\nСЂСџвЂњСњ Р вЂќР вЂўР СћР С’Р вЂєР ВР вЂ”Р С’Р В¦Р ВР Р‡ Р СџР С› Р вЂ”Р С’Р вЂќР С’Р В§Р С’Р Сљ:")
            print("="*100)
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            print(report['detail'].to_string(index=False))
    
    if 'issues' in report and not report['issues'].empty:
        print("\nРІС™В РїС‘РЏ Р СџР В Р С›Р вЂР вЂєР вЂўР СљР СњР В«Р вЂў Р вЂ”Р С’Р вЂќР С’Р В§Р В:")
        print("="*100)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(report['issues'].to_string(index=False))
    
    print("\n" + "="*100)
    print(f"СЂСџвЂ™В° Р вЂ™Р РЋР вЂўР вЂњР С› Р СџР В Р С›Р вЂўР С™Р СћР С›Р вЂ™: {report['total_projects']}")
    print(f"СЂСџвЂњВ¦ Р вЂ™Р РЋР вЂўР вЂњР С› Р вЂ”Р С’Р вЂќР С’Р В§:    {report['total_tasks']}")
    print(f"РІСљвЂ¦ Р С™Р С›Р В Р вЂўР С™Р СћР СњР В«Р Тђ:      {report['total_correct']}")
    print(f"РІС™В РїС‘РЏ  Р СџР В Р С›Р вЂР вЂєР вЂўР СљР СњР В«Р Тђ:     {report['total_issues']}")
    print(f"РІРЏВ±РїС‘РЏ  Р вЂ™Р РЋР вЂўР вЂњР С› Р В¤Р С’Р С™Р Сћ:     {report['total_spent']:.2f} РЎвЂЎ.")
    print(f"СЂСџвЂњРЏ Р вЂ™Р РЋР вЂўР вЂњР С› Р С›Р В¦Р вЂўР СњР С™Р С’:    {report['total_estimated']:.2f} РЎвЂЎ.")
    print("="*100)
    
    if args.excel:
        filename = generate_excel(report)
        print(f"\nРІСљвЂ¦ Р С›РЎвЂљРЎвЂЎРЎвЂРЎвЂљ РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎвЂР Р…: {filename}")