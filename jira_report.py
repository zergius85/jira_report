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

def validate_config() -> Tuple[bool, List[str]]:
    """
    Проверяет корректность конфигурации.
    
    Returns:
        Tuple[bool, List[str]]: (успех, список ошибок)
    """
    errors = []
    
    if not JIRA_SERVER:
        errors.append("Не указан JIRA_SERVER в .env")
    if not JIRA_USER:
        errors.append("Не указан JIRA_USER в .env")
    if not JIRA_PASS:
        errors.append("Не указан JIRA_PASS в .env")
    
    return (len(errors) == 0, errors)


def get_jira_connection() -> JIRA:
    """
    Устанавливает соединение с Jira.
    
    Returns:
        JIRA: Объект подключения к Jira
        
    Raises:
        ConnectionError: При ошибке подключения
    """
    try:
        logger.info(f"🔌 Подключение к Jira: {JIRA_SERVER}")
        
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
        
        # Проверка подключения
        jira.myself()
        logger.info("✅ Успешное подключение к Jira")
        return jira
        
    except JIRAError as e:
        logger.error(f"❌ Ошибка подключения к Jira: {e.text}")
        raise ConnectionError(f"Не удалось подключиться к Jira: {e.text}")
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка подключения: {e}")
        raise ConnectionError(f"Ошибка подключения: {e}")

def get_default_start_date() -> datetime:
    """
    Возвращает дату начала по умолчанию (1 число прошлого месяца).
    
    Returns:
        datetime: Дата начала
    """
    today = datetime.now()
    if today.month == 1:
        return datetime(today.year - 1, 12, 1)
    else:
        return datetime(today.year, today.month - 1, 1)


def convert_seconds_to_hours(seconds: Optional[int]) -> float:
    """
    Конвертирует секунды в часы.
    
    Args:
        seconds: Время в секундах
        
    Returns:
        float: Время в часах
    """
    if seconds is None:
        return 0.0
    return round(seconds / 3600, 2)


def get_closed_status_ids() -> List[str]:
    """
    Автоматически определяет ID статуса "Закрыт" в Jira.
    Кэширует результат в .env для последующих запусков.
    
    Returns:
        List[str]: Список ID статусов
    """
    if CLOSED_STATUS_IDS and CLOSED_STATUS_IDS[0] != '':
        logger.info(f"✅ ID статуса 'Закрыт' загружен из .env: {CLOSED_STATUS_IDS}")
        return CLOSED_STATUS_IDS

    logger.info("🔍 Определение ID статуса 'Закрыт' в Jira...")

    try:
        jira = get_jira_connection()
        statuses = jira.statuses()

        closed_ids = []
        for status in statuses:
            if status.name.lower() in ['закрыт', 'closed', 'закрыто']:
                closed_ids.append(status.id)
                logger.info(f"   📌 Найден статус: {status.name} (ID: {status.id})")

        if closed_ids:
            save_closed_status_ids(closed_ids)
            logger.info(f"✅ ID сохранены в .env: {closed_ids}")
            return closed_ids
        else:
            logger.warning("⚠️  Статус 'Закрыт' не найден.")
            return []

    except Exception as e:
        logger.error(f"❌ Ошибка определения статуса: {e}")
        return []


def save_closed_status_ids(status_ids: List[str]) -> None:
    """
    Сохраняет ID статусов в файл .env.
    
    Args:
        status_ids: Список ID для сохранения
    """
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

    env_content = ''
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            env_content = f.read()

    if 'CLOSED_STATUS_IDS=' in env_content:
        env_content = env_content.replace(
            env_content.split('CLOSED_STATUS_IDS=')[1].split('\n')[0],
            ','.join(status_ids)
        )
    else:
        env_content += f"\nCLOSED_STATUS_IDS={','.join(status_ids)}"

    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)

def validate_issue(issue: Any, jira: Optional[JIRA] = None) -> List[str]:
    """
    Проверяет задачу на корректность заполнения.
    
    Args:
        issue: Объект задачи Jira
        jira: Объект подключения к Jira (не используется)
        
    Returns:
        List[str]: Список проблем
    """
    problems = []

    # Проверка даты решения
    if not issue.fields.resolutiondate:
        problems.append('Нет даты решения')

    # Проверка фактического времени
    if issue.fields.timespent is None or issue.fields.timespent == 0:
        problems.append('Нет фактического времени')

    # Проверка статуса "Закрыт" по ID
    if issue.fields.status:
        status_id = issue.fields.status.id
        status_name = issue.fields.status.name

        if status_id in CLOSED_STATUS_IDS:
            # Проверяем, не является ли исполнитель исключением
            assignee_name = ''
            if issue.fields.assignee:
                assignee_name = issue.fields.assignee.name if hasattr(issue.fields.assignee, 'name') else issue.fields.assignee.displayName

            is_exception = False
            for exc in EXCLUDED_ASSIGNEE_CLOSE:
                if exc.lower() in assignee_name.lower():
                    is_exception = True
                    break

            if not is_exception:
                problems.append(f"Статус '{status_name}' (ID: {status_id})")

    return problems


def get_column_order(block: str, extra_verbose: bool = False) -> List[str]:
    """
    Возвращает порядок колонок для каждого блока.
    
    Args:
        block: Название блока отчёта
        extra_verbose: Показывать ли ID объектов
        
    Returns:
        List[str]: Список названий колонок
    """
    if block == 'summary':
        return ['Клиент (Проект)', 'Задач закрыто', 'Корректных', 'С ошибками', 'Оценка (ч)', 'Факт (ч)', 'Отклонение']
    elif block == 'assignees':
        return ['Исполнитель', 'Задач', 'Корректных', 'С ошибками', 'Оценка (ч)', 'Факт (ч)', 'Отклонение']
    elif block == 'detail':
        return ['URL', 'Дата исполнения', 'Дата создания', 'Проект', 'Статус', 'Задача', 'Исполнитель', 'Факт (ч)', 'Тип']
    elif block == 'issues':
        return ['URL', 'Дата исполнения', 'Дата создания', 'Проект', 'Задача', 'Исполнитель', 'Автор', 'Проблемы']
    else:
        return ['Проект', 'Ключ', 'Задача', 'Исполнитель', 'Статус', 'Дата создания', 'Дата исполнения', 'Факт (ч)', 'Оценка (ч)']
        
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
    Генерирует отчёт по задачам Jira.
    
    Args:
        project_key: Ключ проекта (None = все проекты)
        start_date: Дата начала в формате ГГГГ-ММ-ДД (None = прошлый месяц)
        days: Количество дней для отчёта
        assignee_filter: Фильтр по исполнителю
        blocks: Список блоков отчёта (None = все)
        verbose: Режим отладки
        extra_verbose: Показывать ID объектов
        
    Returns:
        Dict[str, Any]: Словарь с данными отчёта
    """
    # Авто-определение ID статуса "Закрыт"
    global CLOSED_STATUS_IDS
    if not CLOSED_STATUS_IDS or CLOSED_STATUS_IDS[0] == '':
        CLOSED_STATUS_IDS = get_closed_status_ids()

    # Обработка дат
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date_obj = get_default_start_date()

    start_date_str = start_date_obj.strftime('%Y-%m-%d')
    end_date_obj = start_date_obj + timedelta(days=days - 1)
    end_date_str = end_date_obj.strftime('%Y-%m-%d')

    # Для проблемных задач: +2 месяца к концу периода
    issues_end_obj = start_date_obj + timedelta(days=days) + relativedelta(months=2)
    issues_end_str = issues_end_obj.strftime('%Y-%m-%d')

    jira = get_jira_connection()
    
    # Список проектов
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
        
        # Обычные отчёты - фильтр по resolved (дата закрытия)
        jql_normal = (f"project = {proj_key} "
                      f"AND resolved >= '{start_date_str}' "
                      f"AND resolved <= '{end_date_str}' "
                      f"ORDER BY resolved ASC")
        
        # Проблемные задачи - фильтр по created + 2 месяца
        jql_issues = (f"project = {proj_key} "
                      f"AND created >= '{start_date_str}' "
                      f"AND created <= '{issues_end_str}' "
                      f"ORDER BY created ASC")
        
        # Получаем все задачи для проблемных (больший период)
        issues_all = jira.search_issues(jql_issues, maxResults=False, 
                                        fields='summary, assignee, timespent, timeoriginalestimate, resolutiondate, issuetype, duedate, status, created, creator')
        
        # Получаем задачи для обычных отчётов (меньший период)
        issues_normal = jira.search_issues(jql_normal, maxResults=False, 
                                           fields='summary, assignee, timespent, timeoriginalestimate, resolutiondate, issuetype, duedate, status, created')
        
        # Обработка для обычных отчётов
        proj_spent = 0.0
        proj_estimated = 0.0
        proj_correct = 0
        proj_issues = 0
        
        for issue in issues_normal:
            spent = convert_seconds_to_hours(issue.fields.timespent)
            estimated = convert_seconds_to_hours(issue.fields.timeoriginalestimate)
            
            issue_type = issue.fields.issuetype.name if issue.fields.issuetype else 'Задача'
            assignee = issue.fields.assignee.displayName if issue.fields.assignee else 'Без исполнителя'
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
            project_display = f"{proj_name} [{issue.fields.project.id}]" if extra_verbose and hasattr(issue.fields, 'project') and hasattr(issue.fields.project, 'id') else proj_name
            status_display = f"{status_full} [{issue.fields.status.id}]" if extra_verbose and issue.fields.status and hasattr(issue.fields.status, 'id') else status_full
            issue_type_display = f"{issue_type} [{issue.fields.issuetype.id}]" if extra_verbose and issue.fields.issuetype and hasattr(issue.fields.issuetype, 'id') else issue_type
            assignee_display = f"{assignee} [{issue.fields.assignee.id}]" if extra_verbose and issue.fields.assignee and hasattr(issue.fields.assignee, 'id') else assignee
            
            issue_data = {
                'URL': issue_url,
                'ID': issue_id,
                'Проект': project_display,
                'Ключ': issue.key,
                'Тип': issue_type_display,
                'Задача': issue.fields.summary,
                'Исполнитель': assignee_display,
                'Статус': status_display,
                'Дата создания': created,
                'Дата исполнения': duedate,
                'Дата решения': resolved,
                'Факт (ч)': spent,
                'Оценка (ч)': estimated,
                'Проблемы': ', '.join(problems) if problems else ''
            }
            
            all_issues_data.append(issue_data)
            
            if not problems:
                proj_spent += spent
                proj_estimated += estimated
                proj_correct += 1
            else:
                proj_issues += 1
            
            if problems:
                # Для проблемных задач берём СОЗДАТЕЛЯ задачи (creator)
                author = 'N/A'
                author_id = ''
                if hasattr(issue.fields, 'creator') and issue.fields.creator:
                    author = issue.fields.creator.displayName if hasattr(issue.fields.creator, 'displayName') else str(issue.fields.creator)
                    author_id = issue.fields.creator.id if hasattr(issue.fields.creator, 'id') else ''
                elif hasattr(issue.fields, 'author') and issue.fields.author:
                    author = issue.fields.author.displayName if hasattr(issue.fields.author, 'displayName') else str(issue.fields.author)
                    author_id = issue.fields.author.id if hasattr(issue.fields.author, 'id') else ''
                
                # Формируем имя автора с ID если нужно
                author_display = f"{author} [{author_id}]" if extra_verbose and author_id else author
                
                issues_with_problems.append({
                    'URL': issue_url,
                    'Проект': proj_name,
                    'Задача': issue.fields.summary,
                    'Исполнитель': assignee,
                    'Автор': author_display,
                    'Дата создания': created,
                    'Дата исполнения': duedate,
                    'Проблемы': ', '.join(problems)
                })
        
        if proj_correct > 0 or proj_issues > 0:
            summary_data.append({
                'Клиент (Проект)': proj_name,
                'Задач закрыто': proj_correct + proj_issues,
                'Корректных': proj_correct,
                'С ошибками': proj_issues,
                'Оценка (ч)': round(proj_estimated, 2),
                'Факт (ч)': round(proj_spent, 2),
                'Отклонение': round(proj_estimated - proj_spent, 2)
            })
    
    df_detail = pd.DataFrame(all_issues_data)
    df_summary = pd.DataFrame(summary_data)
    df_issues = pd.DataFrame(issues_with_problems)
    
    # Сортировка и группировка
    if not df_detail.empty:
        df_detail = df_detail.sort_values(by=['Тип', 'Проект', 'Дата решения'], ascending=[True, True, True])
        
        # Группировка по исполнителям - СЧИТАЕМ ВСЕ ЗАДАЧИ (разделяем на корректные и с ошибками)
        if not df_detail.empty:
            df_assignees = df_detail.groupby('Исполнитель').agg(
                Задач=('Ключ', 'count'),
                Корректных=('Проблемы', lambda x: (x == '').sum()),
                С_ошибками=('Проблемы', lambda x: (x != '').sum()),
                **{'Факт (ч)': ('Факт (ч)', 'sum'), 'Оценка (ч)': ('Оценка (ч)', 'sum')}
            ).reset_index()
            df_assignees['Отклонение'] = df_assignees['Оценка (ч)'] - df_assignees['Факт (ч)']
            df_assignees = df_assignees.round(2)
            df_assignees = df_assignees.sort_values(by='Факт (ч)', ascending=False)
        else:
            df_assignees = pd.DataFrame()
    else:
        df_assignees = pd.DataFrame()
    
    result = {
        'period': f"{start_date_str} — {end_date_str}",
        'blocks': blocks or list(REPORT_BLOCKS.keys()),
        'total_projects': len(df_summary),
        'total_tasks': len(df_detail),
        'total_correct': len(df_detail[df_detail['Проблемы'] == '']) if not df_detail.empty else 0,
        'total_issues': len(df_issues),
        'total_spent': df_summary['Факт (ч)'].sum() if not df_summary.empty else 0,
        'total_estimated': df_summary['Оценка (ч)'].sum() if not df_summary.empty else 0,
    }
    
    if 'summary' in result['blocks']:
        result['summary'] = df_summary
    if 'assignees' in result['blocks']:
        result['assignees'] = df_assignees
    if 'detail' in result['blocks']:
        result['detail'] = df_detail
    if 'issues' in result['blocks']:
        result['issues'] = df_issues
    
    # Фильтрация колонок для каждого блока
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
    Выгружает отчёт в Excel.
    
    Args:
        report_data: Данные отчёта
        output: Путь к файлу или BytesIO объект
        
    Returns:
        Union[str, io.BytesIO]: Имя файла или BytesIO объект
    """
    if output is None:
        output = f"jira_report_{report_data['period'].replace(' — ', '_to_').replace(' ', '')}.xlsx"

    writer = pd.ExcelWriter(output, engine='openpyxl')
    
    try:
        if 'summary' in report_data and not report_data['summary'].empty:
            report_data['summary'].to_excel(writer, sheet_name='Сводка', index=False)
        if 'assignees' in report_data and not report_data['assignees'].empty:
            report_data['assignees'].to_excel(writer, sheet_name='Исполнители', index=False)
        if 'detail' in report_data and not report_data['detail'].empty:
            report_data['detail'].to_excel(writer, sheet_name='Детали', index=False)
        if 'issues' in report_data and not report_data['issues'].empty:
            report_data['issues'].to_excel(writer, sheet_name='Проблемы', index=False)
    finally:
        writer.close()
    
    return output

# =============================================
# КОНСОЛЬНЫЙ ЗАПУСК
# =============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Генерация отчёта по закрытым задачам из Jira',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
БЛОКИ ОТЧЁТА:
  summary   - Сводка по проектам
  assignees - Нагрузка по исполнителям
  detail    - Детализация по задачам
  issues    - Проблемные задачи

ПРИМЕРЫ:
  python3 jira_report.py -e
  python3 jira_report.py -b summary,assignees -e
  python3 jira_report.py -p WEB -a "Иванов" -b detail -e
  python3 jira_report.py -b issues -vv
        '''
    )
    parser.add_argument('-p', '--project', type=str, help='Ключ проекта')
    parser.add_argument('-s', '--start-date', type=str, help='Дата начала (ГГГГ-ММ-ДД)')
    parser.add_argument('-d', '--days', type=int, default=30, help='Период в днях')
    parser.add_argument('-a', '--assignee', type=str, help='Фильтр по исполнителю')
    parser.add_argument('-b', '--blocks', type=str, help='Блоки отчёта (через запятую)')
    parser.add_argument('-e', '--excel', action='store_true', help='Выгрузка в Excel')
    parser.add_argument('-v', '--verbose', action='store_true', help='Режим отладки')
    parser.add_argument('-vv', '--extra-verbose', action='store_true', help='Показывать ID задач во всех отчётах')
    args = parser.parse_args()
    
    blocks = None
    if args.blocks:
        blocks = [b.strip() for b in args.blocks.split(',')]
        invalid = [b for b in blocks if b not in REPORT_BLOCKS]
        if invalid:
            print(f"❌ Неверные блоки: {invalid}")
            print(f"Доступные: {list(REPORT_BLOCKS.keys())}")
            sys.exit(1)
    
    # Авто-определение статуса перед запуском
    if not CLOSED_STATUS_IDS or CLOSED_STATUS_IDS[0] == '':
        CLOSED_STATUS_IDS = get_closed_status_ids()
    
    print(f"🔌 Генерация отчёта...")
    if args.blocks:
        print(f"📦 Блоки: {', '.join(blocks)}")
    
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
    print(f"📋 ОТЧЁТ ЗА {report['period']}")
    print("="*100)
    
    if 'summary' in report:
        print("\n📊 СВОДКА ПО ПРОЕКТАМ:")
        print("="*100)
        print(report['summary'].to_string(index=False))
    
    if 'assignees' in report and not report['assignees'].empty:
        print("\n👤 НАГРУЗКА ПО ИСПОЛНИТЕЛЯМ:")
        print("="*100)
        print(report['assignees'].to_string(index=False))
    
    if 'detail' in report and not report['detail'].empty:
        if args.verbose:
            print("\n📝 ДЕТАЛИЗАЦИЯ ПО ЗАДАЧАМ:")
            print("="*100)
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            print(report['detail'].to_string(index=False))
    
    if 'issues' in report and not report['issues'].empty:
        print("\n⚠️ ПРОБЛЕМНЫЕ ЗАДАЧИ:")
        print("="*100)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(report['issues'].to_string(index=False))
    
    print("\n" + "="*100)
    print(f"💰 ВСЕГО ПРОЕКТОВ: {report['total_projects']}")
    print(f"📦 ВСЕГО ЗАДАЧ:    {report['total_tasks']}")
    print(f"✅ КОРЕКТНЫХ:      {report['total_correct']}")
    print(f"⚠️  ПРОБЛЕМНЫХ:     {report['total_issues']}")
    print(f"⏱️  ВСЕГО ФАКТ:     {report['total_spent']:.2f} ч.")
    print(f"📏 ВСЕГО ОЦЕНКА:    {report['total_estimated']:.2f} ч.")
    print("="*100)
    
    if args.excel:
        filename = generate_excel(report)
        print(f"\n✅ Отчёт сохранён: {filename}")