# -*- coding: utf-8 -*-
"""
Jira Report System — Ядро отчётов

Модуль для сбора, обработки и выгрузки данных из Jira.
Поддерживает консольный режим и работу через Web-интерфейс.
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

# Импортируем настройки из config.py
from config import (
    JIRA_SERVER,
    JIRA_USER,
    JIRA_PASS,
    EXCLUDED_PROJECTS,
    INTERNAL_PROJECTS,
    CLOSED_STATUS_IDS,
    EXCLUDED_ASSIGNEE_CLOSE,
    SSL_VERIFY,
    REPORT_BLOCKS,
    LOG_LEVEL,
    LOG_FORMAT,
    LOG_DATE_FORMAT
)

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT
)
logger = logging.getLogger(__name__)

# --- НАСТРОЙКА SSL ---
if not SSL_VERIFY:
    logger.warning("⚠️  Проверка SSL отключена (SSL_VERIFY=false)")
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    os.environ['CURL_CA_BUNDLE'] = ''
    warnings.simplefilter('ignore', InsecureRequestWarning)
else:
    logger.info("✅ Проверка SSL включена")
