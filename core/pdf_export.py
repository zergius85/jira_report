# -*- coding: utf-8 -*-
"""
Сервис экспорта отчётов в PDF формат.

Использует WeasyPrint для генерации PDF из HTML.
"""
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
import io

from core.config import REPORTS_DIR

logger = logging.getLogger(__name__)

# Проверка доступности WeasyPrint
WEASYPRINT_AVAILABLE = False
try:
    from weasyprint import HTML, CSS
    
    # FontConfiguration в разных версиях WeasyPrint находится в разных местах
    # Версия 52.5 (для Python 3.7)
    try:
        from weasyprint.text.fonts import FontConfiguration
    except ImportError:
        # Более старые версии
        try:
            from weasyprint.fonts import FontConfiguration
        except ImportError:
            # Если не найдено — используем None
            FontConfiguration = None
    
    WEASYPRINT_AVAILABLE = True
    logger.info("✅ WeasyPrint доступен")
except ImportError as e:
    logger.warning(f"⚠️  WeasyPrint не установлен. Экспорт в PDF недоступен: {e}")


def generate_pdf_report(
    report_data: Dict[str, Any],
    filename: Optional[str] = None,
    include_charts: bool = True,
    client_mode: bool = False,
) -> Optional[bytes]:
    """
    Генерирует PDF файл из данных отчёта.
    
    Args:
        report_data: Данные отчёта (из generate_report)
        filename: Имя файла для сохранения (опционально)
        include_charts: Включать ли графики
        client_mode: Режим для клиента (только детали, без проблемных)
    
    Returns:
        bytes: PDF данные или None
    """
    if not WEASYPRINT_AVAILABLE:
        logger.error("WeasyPrint недоступен")
        return None

    try:
        html_content = _render_pdf_html(report_data, include_charts, client_mode)

        # Проверка html_content
        if not html_content or len(html_content.strip()) == 0:
            logger.error("Пустой HTML контент для PDF")
            return None

        logger.info(f"✅ HTML сгенерирован, размер: {len(html_content)} символов")

        # Генерируем PDF
        # FontConfiguration может быть None если не найден в импорте
        if FontConfiguration is not None:
            font_config = FontConfiguration()
            pdf_bytes = HTML(string=html_content).write_pdf(
                stylesheets=[
                    CSS(string='''
                    @page {
                        size: A4;
                        margin: 2cm;
                        @bottom-right {
                            content: "Page " counter(page) " of " counter(pages);
                            font-size: 10px;
                            color: #666;
                        }
                    }
                    body { 
                        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
                        font-size: 11px;
                        line-height: 1.4;
                        color: #333;
                    }
                    table { 
                        width: 100%; 
                        border-collapse: collapse; 
                        margin: 15px 0;
                        font-size: 10px;
                    }
                    th, td { 
                        padding: 8px; 
                        text-align: left; 
                        border-bottom: 1px solid #ddd; 
                    }
                    th { 
                        background: #f5f5f5; 
                        font-weight: 600;
                        border-bottom: 2px solid #ccc;
                    }
                    tr:nth-child(even) { background: #fafafa; }
                    h1, h2, h3 { color: #2c3e50; }
                    h1 { 
                        font-size: 24px; 
                        border-bottom: 3px solid #3498db;
                        padding-bottom: 10px;
                        margin-bottom: 20px;
                    }
                    h2 { 
                        font-size: 18px; 
                        border-bottom: 2px solid #eee;
                        padding-bottom: 8px;
                        margin-top: 25px;
                    }
                    .header-info {
                        background: #f8f9fa;
                        padding: 15px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                        border-left: 4px solid #3498db;
                    }
                    .stats-grid {
                        display: grid;
                        grid-template-columns: repeat(4, 1fr);
                        gap: 15px;
                        margin: 20px 0;
                    }
                    .stat-card {
                        background: #34495e;
                        color: white;
                        padding: 15px;
                        border-radius: 5px;
                        text-align: center;
                    }
                    .stat-card.warning { background: #e74c3c; }
                    .stat-card.success { background: #27ae60; }
                    .stat-value { 
                        font-size: 28px; 
                        font-weight: bold; 
                        margin-bottom: 5px; 
                    }
                    .stat-label { 
                        font-size: 11px; 
                        opacity: 0.9; 
                        text-transform: uppercase;
                    }
                    .risk-zone {
                        background: #fff3cd;
                        border: 1px solid #ffc107;
                        border-radius: 5px;
                        padding: 15px;
                        margin: 20px 0;
                    }
                    .risk-zone h3 { color: #856404; }
                    .page-break { page-break-before: always; }
                    .client-cover {
                        text-align: center;
                        padding: 100px 20px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border-radius: 10px;
                        margin-bottom: 30px;
                    }
                    .client-cover h1 { 
                        color: white; 
                        border: none;
                        font-size: 36px;
                    }
                    .client-cover .date {
                        font-size: 18px;
                        margin-top: 20px;
                        opacity: 0.9;
                    }
                ''')
            ],
            font_config=font_config if FontConfiguration is not None else None,
        )
        
        # Сохраняем если указан filename
        if filename:
            filepath = os.path.join(REPORTS_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(pdf_bytes)
            logger.info(f"✅ PDF сохранён: {filepath}")
        
        return pdf_bytes
    
    except Exception as e:
        logger.error(f"❌ Ошибка генерации PDF: {e}", exc_info=True)
        return None


def _render_pdf_html(
    report_data: Dict[str, Any],
    include_charts: bool,
    client_mode: bool,
) -> str:
    """
    Рендерит HTML шаблон для PDF.
    
    Args:
        report_data: Данные отчёта
        include_charts: Включать ли графики
        client_mode: Режим для клиента
    
    Returns:
        str: HTML контент
    """
    period = report_data.get('period', 'Отчёт')
    totals = report_data.get('totals', {})
    
    html_parts = []
    
    # Обложка для клиентского режима
    if client_mode:
        html_parts.append(f'''
            <div class="client-cover">
                <h1>Отчёт по задачам</h1>
                <div class="date">{period}</div>
                <div style="margin-top: 40px; font-size: 14px; opacity: 0.8;">
                    Сформирован автоматически системой Jira Report
                </div>
            </div>
            <div class="page-break"></div>
        ''')
    
    # Заголовок
    if not client_mode:
        html_parts.append(f'<h1>📊 Jira Report — {period}</h1>')
    else:
        html_parts.append(f'<h1>Отчёт по задачам — {period}</h1>')
    
    # Информация об отчёте
    html_parts.append(f'''
        <div class="header-info">
            <strong>Период:</strong> {period}<br>
            <strong>Дата формирования:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}
        </div>
    ''')
    
    # Статистика
    html_parts.append('<h2>📈 Сводная статистика</h2>')
    html_parts.append('<div class="stats-grid">')
    html_parts.append(f'''
        <div class="stat-card">
            <div class="stat-value">{totals.get('projects', 0)}</div>
            <div class="stat-label">Проектов</div>
        </div>
        <div class="stat-card success">
            <div class="stat-value">{totals.get('correct', 0)}</div>
            <div class="stat-label">Корректных</div>
        </div>
        <div class="stat-card warning">
            <div class="stat-value">{totals.get('issues', 0)}</div>
            <div class="stat-label">Проблемных</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{totals.get('spent', 0):.1f}</div>
            <div class="stat-label">Факт (ч)</div>
        </div>
    ''')
    html_parts.append('</div>')

    # Сводка по проектам
    if 'summary' in report_data and not report_data['summary'].empty:
        html_parts.append('<div class="page-break"></div>')
        html_parts.append('<h2>📋 Сводка по проектам</h2>')
        html_parts.append(_render_table(report_data['summary'], [
            'Клиент (Проект)', 'Задач закрыто', 'Корректных', 'С ошибками',
            'Оценка (ч)', 'Факт (ч)', 'Отклонение'
        ]))

    # Детализация (в клиентском режиме только этот блок)
    if 'detail' in report_data and not report_data['detail'].empty:
        if client_mode:
            html_parts.append('<div class="page-break"></div>')
        html_parts.append('<h2>📝 Детализация по задачам</h2>')
        html_parts.append(_render_table(report_data['detail'], [
            'URL', 'Дата решения', 'Дата исполнения', 'Дата создания',
            'Проект', 'Статус', 'Задача', 'Исполнитель', 'Факт (ч)', 'Тип'
        ], max_rows=100))

    # Проблемные задачи (только не в клиентском режиме)
    if not client_mode and 'issues' in report_data and not report_data['issues'].empty:
        html_parts.append('<div class="page-break"></div>')
        html_parts.append('<h2>⚠️ Проблемные задачи</h2>')
        html_parts.append(_render_table(report_data['issues'], [
            'URL', 'Дата исполнения', 'Дата создания', 'Проект',
            'Задача', 'Исполнитель', 'Автор', 'Проблемы'
        ]))

    # Risk Zone
    if not client_mode and 'risk_zone' in report_data and not report_data['risk_zone'].empty:
        html_parts.append('<div class="page-break"></div>')
        html_parts.append('<div class="risk-zone">')
        html_parts.append('<h3>🔴 Risk Zone — Зависшие задачи</h3>')
        html_parts.append('<p>Задачи с факторами риска: без исполнителя, просрочены, не двигаются более 5 дней.</p>')
        html_parts.append(_render_table(report_data['risk_zone'], [
            'URL', 'Ключ', 'Задача', 'Исполнитель', 'Статус', 'Факторы риска', 'Приоритет'
        ]))
        html_parts.append('</div>')
    
    # Исполнители
    if 'assignees' in report_data and not report_data['assignees'].empty:
        html_parts.append('<div class="page-break"></div>')
        html_parts.append('<h2>👤 Нагрузка по исполнителям</h2>')
        html_parts.append(_render_table(report_data['assignees'], [
            'Исполнитель', 'Задач', 'Корректных', 'С ошибками',
            'Оценка (ч)', 'Факт (ч)', 'Отклонение'
        ]))
    
    return '\n'.join(html_parts)


def _render_table(
    data: List[Dict[str, Any]],
    columns: List[str],
    max_rows: int = 200,
) -> str:
    """
    Рендерит таблицу из данных.
    
    Args:
        data: Список словарей с данными
        columns: Список колонок для отображения
        max_rows: Максимум строк
    
    Returns:
        str: HTML таблицы
    """
    if not data:
        return '<p>Нет данных</p>'
    
    # Ограничиваем количество строк
    truncated = len(data) > max_rows
    data = data[:max_rows]
    
    html = ['<table>', '<thead><tr>']
    
    # Заголовки
    for col in columns:
        html.append(f'<th>{col}</th>')
    
    html.append('</tr></thead><tbody>')
    
    # Данные
    for row in data:
        html.append('<tr>')
        for col in columns:
            value = row.get(col, '')
            # Экранируем HTML
            if isinstance(value, str):
                value = value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            html.append(f'<td>{value}</td>')
        html.append('</tr>')
    
    html.append('</tbody></table>')
    
    if truncated:
        html.append(f'<p style="color: #666; font-size: 10px;">Показано {max_rows} из {len(data)} строк</p>')
    
    return '\n'.join(html)


def generate_client_pdf(
    report_data: Dict[str, Any],
    task_key: str,
    task_data: Dict[str, Any],
) -> Optional[bytes]:
    """
    Генерирует PDF для конкретной задачи (для клиента).
    
    Args:
        report_data: Данные отчёта
        task_key: Ключ задачи (WEB-123)
        task_data: Данные задачи (суммарные часы, тип, и т.д.)
    
    Returns:
        bytes: PDF данные
    """
    client_data = {
        'period': report_data.get('period', 'Отчёт'),
        'totals': {
            'projects': 1,
            'correct': 1,
            'issues': 0,
            'spent': task_data.get('spent', 0),
        },
        'detail': report_data.get('detail', [])[:1],  # Только одна задача
    }
    
    return generate_pdf_report(client_data, client_mode=True)
