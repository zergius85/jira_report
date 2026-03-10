# -*- coding: utf-8 -*-
"""
Точка входа для консольного режима Jira Report System.

Этот файл импортирует функции из core/jira_report.py
и предоставляет CLI интерфейс.
"""
import sys
import os
import pandas as pd

# Добавляем корень проекта в path для корректных импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.jira_report import (
    generate_report,
    generate_excel,
    get_closed_status_ids,
    REPORT_BLOCKS,
    CLOSED_STATUS_IDS
)

if __name__ == "__main__":
    import argparse

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

    # Авто-определение статуса перед запуском (локальная переменная)
    closed_status_ids = CLOSED_STATUS_IDS
    if not closed_status_ids or closed_status_ids[0] == '':
        closed_status_ids = get_closed_status_ids()

    print(f"🔌 Генерация отчёта...")
    if args.blocks:
        print(f"📦 Блоки: {', '.join(blocks)}")

    report = generate_report(
        project_keys=args.project,
        start_date=args.start_date,
        days=args.days,
        assignee_filter=args.assignee,
        blocks=blocks,
        verbose=args.verbose,
        extra_verbose=args.extra_verbose,
        closed_status_ids=closed_status_ids
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
