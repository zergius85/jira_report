# -*- coding: utf-8 -*-
"""
Веб-интерфейс системы отчётов Jira.

Flask-приложение для предоставления API и UI.
"""
from flask import Flask, render_template, request, jsonify, send_file, g
from flask_caching import Cache
from core.jira_report import generate_report, generate_excel, get_jira_connection, normalize_filter, convert_seconds_to_hours
from core.config import (
    REPORT_BLOCKS,
    EXCLUDED_PROJECTS,
    ACTIVE_PORT,
    FLASK_HOST,
    IS_PRODUCTION,
    JIRA_SERVER,
    MAX_REPORT_DAYS,
    MAX_SEARCH_RESULTS,
    MAX_EXCEL_ROWS
)
from datetime import datetime
from collections import OrderedDict
from typing import Tuple, Any, Dict, List, Optional, Union, Callable
import io
import os
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

# Импортируем middleware
from web.middleware import (
    api_rate_limiter,
    handle_api_errors,
    APIError,
    JiraConnectionError,
    ValidationError,
    init_middleware
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Путь к шаблонам теперь на уровень выше (templates в корне проекта)
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, '..', 'templates'))

# Инициализируем middleware
init_middleware(app)

# Регистрируем Telegram blueprint
try:
    from web.telegram_routes import telegram_bp
    app.register_blueprint(telegram_bp, url_prefix='/telegram')
    logger.info("✅ Telegram routes зарегистрированы")
except Exception as e:
    logger.warning(f"⚠️  Telegram routes не зарегистрированы: {e}")

# Инициализируем планировщик задач
try:
    from core.scheduler import init_scheduler
    with app.app_context():
        init_scheduler()
    logger.info("✅ Планировщик задач инициализирован")
except Exception as e:
    logger.warning(f"⚠️  Планировщик задач не инициализирован: {e}")

# Кэширование для API endpoints (только для production!)
# В dev-режиме кэш отключен для быстрой отладки
if IS_PRODUCTION:
    app.config['CACHE_TYPE'] = 'simple'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 минут
    cache = Cache(app)
    cache_init = True
else:
    # В dev-режиме кэш отключен
    cache = None
    cache_init = False


def conditional_cache(timeout: int = 300) -> Callable:
    """
    Декоратор для условного кэширования: кэширует только в production.

    Args:
        timeout: Время кэширования в секундах

    Usage:
        @conditional_cache(timeout=300)
        def api_projects():
            return _api_projects_logic()
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs) -> Any:
            if cache_init and cache:
                # Создаём кэшированную версию функции
                cached_f = cache.cached(timeout=timeout)(f)
                return cached_f(*args, **kwargs)
            else:
                return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_json_request(f: Callable) -> Callable:
    """
    Декоратор для валидации JSON в API endpoints.

    Usage:
        @app.route('/api/report', methods=['POST'])
        @validate_json_request
        def api_report():
            data = request.get_json()
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type должен быть application/json'
            }), 400
        
        data = request.get_json()
        if data is None:
            return jsonify({
                'success': False,
                'error': 'Неверный формат JSON'
            }), 400
        
        return f(*args, **kwargs)
    return decorated


# =============================================
# КЭШИРОВАНИЕ PROJECTS (для core/jira_report.py)
# =============================================
# Кэш для jira.project() - используется в generate_report()
_project_cache: OrderedDict = OrderedDict()
_project_cache_time: dict = {}
_PROJECT_CACHE_TTL = 3600  # 1 час
_MAX_PROJECT_CACHE_SIZE = 1000  # Максимум 1000 проектов в кэше


def _evict_old_project_cache() -> None:
    """Удаляет старые записи из кэша проектов (LRU)."""
    while len(_project_cache) > _MAX_PROJECT_CACHE_SIZE:
        # Удаляем самую старую запись (первую в OrderedDict)
        oldest_key = next(iter(_project_cache))
        del _project_cache[oldest_key]
        _project_cache_time.pop(oldest_key, None)


def get_project_cached(jira, proj_key):
    """
    Кэширует результат jira.project(proj_key) на 1 час.

    Args:
        jira: Объект подключения к Jira
        proj_key: Ключ проекта

    Returns:
        Проект Jira
    """
    import time

    # Проверяем кэш
    if proj_key in _project_cache:
        cache_age = time.time() - _project_cache_time.get(proj_key, 0)
        if cache_age < _PROJECT_CACHE_TTL:
            # Перемещаем в конец (LRU)
            _project_cache.move_to_end(proj_key)
            return _project_cache[proj_key]

    # Получаем из Jira
    try:
        proj = jira.project(proj_key)
        _project_cache[proj_key] = proj
        _project_cache_time[proj_key] = time.time()
        
        # Перемещаем в конец (LRU)
        _project_cache.move_to_end(proj_key)
        
        # Чищим старые записи при превышении лимита
        _evict_old_project_cache()
        
        return proj
    except Exception:
        # Если проект не найден, не кэшируем
        return None

@app.route('/')
def index():
    return render_template('index.html', blocks=REPORT_BLOCKS, JIRA_SERVER=JIRA_SERVER)

@app.route('/api/projects')
@conditional_cache(timeout=300)
def api_projects():
    """Получить список проектов"""
    return _get_api_projects()

def _get_api_projects() -> Tuple[Any, int]:
    """Получить список проектов
    
    Returns:
        Tuple[Any, int]: Flask response и статус код
    """
    try:
        jira = get_jira_connection()
        projects = jira.projects()

        result = []
        for proj in projects:
            if proj.key in EXCLUDED_PROJECTS:
                continue
            if hasattr(proj, 'archived') and proj.archived:
                continue
            result.append({'key': proj.key, 'name': proj.name})

        return jsonify({'success': True, 'projects': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assignees')
@conditional_cache(timeout=300)
def api_assignees():
    """Получить список всех активных исполнителей"""
    return _get_api_assignees()

def _get_api_assignees() -> Tuple[Any, int]:
    """Получить список всех активных исполнителей
    
    Returns:
        Tuple[Any, int]: Flask response и статус код
    """
    try:
        jira = get_jira_connection()
        logger.info("🔍 Загрузка исполнителей из Jira...")

        assignees = {}

        # Пробуем разные методы поиска пользователей для совместимости
        methods_tried = []
        
        # Метод 1: search_users(query='') - для Jira Cloud
        try:
            logger.info("  → search_users(query='') [Jira Cloud]...")
            users = jira.search_users(query='', maxResults=MAX_SEARCH_RESULTS)
            methods_tried.append('query')
            for user in users:
                _add_user_to_assignees(user, assignees)
            logger.info(f"     Найдено пользователей: {len(assignees)}")
        except Exception as e1:
            logger.debug(f"  ✗ Метод query не сработал: {e1}")

            # Метод 2: search_users(user='') - для старых Jira Server
            try:
                logger.info("  → search_users(user='') [Jira Server]...")
                users = jira.search_users(user='', maxResults=MAX_SEARCH_RESULTS)
                methods_tried.append('user')
                for user in users:
                    _add_user_to_assignees(user, assignees)
                logger.info(f"     Найдено пользователей: {len(assignees)}")
            except Exception as e2:
                logger.debug(f"  ✗ Метод user не сработал: {e2}")
                
                # Метод 3: Получаем из задач (fallback)
                logger.info("  → Получаем исполнителей из задач [fallback]...")
                methods_tried.append('fallback')
                return _get_assignees_from_issues(jira)

        if not assignees:
            logger.warning("  ⚠️  Ни один метод не вернул пользователей, пробуем fallback...")
            return _get_assignees_from_issues(jira)

        # Сортируем по имени
        result = [{'key': k, 'name': v} for k, v in sorted(assignees.items(), key=lambda x: x[1])]
        logger.info(f"✅ Возвращаем {len(result)} исполнителей (метод: {', '.join(methods_tried)})")
        return jsonify({'success': True, 'assignees': result})
    except Exception as e:
        import traceback
        logger.error(f"❌ Ошибка загрузки исполнителей: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


def _add_user_to_assignees(user: Any, assignees_dict: Dict[str, str]) -> None:
    """Добавляет пользователя в словарь исполнителей

    Args:
        user: Пользователь (dict или объект Jira)
        assignees_dict: Словарь для добавления
    """
    if isinstance(user, dict):
        is_active = bool(user.get('active', False))
        key = user.get('name') or user.get('accountId') or user.get('key')
        name = user.get('displayName', key) or user.get('name', key)
    else:
        is_active = bool(getattr(user, 'active', False))
        key = getattr(user, 'name', None) or getattr(user, 'accountId', None) or getattr(user, 'key', None)
        name = getattr(user, 'displayName', None) or getattr(user, 'name', key)

    if is_active and key:
        assignees_dict[key] = name


def _get_assignees_from_issues(jira: Any) -> Tuple[Any, int]:
    """Альтернативный метод: получаем исполнителей из последних задач
    
    Args:
        jira: Подключение к Jira
        
    Returns:
        Tuple[Any, int]: Flask response и статус код
    """
    try:
        # Получаем последние задачи для извлечения исполнителей
        issues = jira.search_issues('assignee is not null ORDER BY updated DESC', maxResults=MAX_SEARCH_RESULTS,
                                    fields='assignee')
        
        assignees = {}
        for issue in issues:
            if issue.fields.assignee:
                _add_user_to_assignees(issue.fields.assignee, assignees)
        
        result = [{'key': k, 'name': v} for k, v in sorted(assignees.items(), key=lambda x: x[1])]
        logger.info(f"✅ Найдено {len(result)} исполнителей из задач")
        return jsonify({'success': True, 'assignees': result})
    except Exception as e:
        logger.error(f"❌ Альтернативный метод не сработал: {e}")
        raise

@app.route('/health')
def health_check():
    """
    Health check endpoint для мониторинга.
    
    Возвращает детальную информацию о состоянии системы:
    - Статус подключения к Jira
    - Информация о пользователе
    - Версия Jira (если доступна)
    - Время отклика
    """
    import time
    
    checks = {}
    overall_status = 'ok'
    
    # Проверка подключения к Jira
    start_time = time.time()
    try:
        jira = get_jira_connection()
        myself = jira.myself()
        jira_latency = round((time.time() - start_time) * 1000)  # мс
        
        checks['jira'] = {
            'status': 'ok',
            'latency_ms': jira_latency,
            'user': myself.get('displayName') if isinstance(myself, dict) else str(myself),
            'server': JIRA_SERVER
        }
    except Exception as e:
        logger.error(f"Jira health check failed: {e}")
        checks['jira'] = {
            'status': 'error',
            'error': str(e)
        }
        overall_status = 'degraded'
    
    return jsonify({
        'status': overall_status,
        'timestamp': datetime.now().isoformat(),
        'version': '2.1.0',
        'checks': checks
    }), 200 if overall_status == 'ok' else 503

@app.route('/api/issue-types')
def api_issue_types():
    """Получить список типов задач из Jira"""
    try:
        jira = get_jira_connection()

        # Получаем все типы задач из Jira (глобально)
        all_types = jira.issue_types()

        issue_types = {}
        for issue_type in all_types:
            # Исключаем подзадачи
            if not getattr(issue_type, 'subtask', False):
                type_id = getattr(issue_type, 'id', None)
                type_name = getattr(issue_type, 'name', None)
                if type_id and type_name:
                    issue_types[type_id] = type_name

        result = [{'id': k, 'name': v} for k, v in sorted(issue_types.items(), key=lambda x: x[1])]
        return jsonify({'success': True, 'issue_types': result})
    except Exception as e:
        logger.error(f"Ошибка получения типов задач: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/task-info', methods=['POST'])
def api_task_info():
    """Получить полную информацию о задаче со всеми полями"""
    try:
        data = request.json
        task_key = data.get('task_key', '')

        if not task_key:
            return jsonify({'success': False, 'error': 'Не указан ключ задачи'}), 400

        jira = get_jira_connection()
        issue = jira.issue(task_key, expand='changelog,renderedFields')

        task_info = {'key': issue.key, 'id': issue.id, 'fields': {}}

        if hasattr(issue, 'fields') and issue.fields:
            for field_name in dir(issue.fields):
                if not field_name.startswith('_'):
                    try:
                        value = getattr(issue.fields, field_name)
                        if value is not None:
                            task_info['fields'][field_name] = str(value)
                    except:
                        pass

        if hasattr(issue, 'changelog') and issue.changelog:
            task_info['changelog'] = []
            for history in issue.changelog.histories:
                history_item = {
                    'author': history.author.displayName if hasattr(history.author, 'displayName') else str(history.author),
                    'created': history.created,
                    'items': []
                }
                for item in history.items:
                    history_item['items'].append({
                        'field': item.field,
                        'from': item.fromString,
                        'to': item.toString
                    })
                task_info['changelog'].append(history_item)

        return jsonify({'success': True, 'task_info': task_info})
    except Exception as e:
        logger.error(f"Ошибка получения информации о задаче {task_key}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/task-info-batch', methods=['POST'])
def api_task_info_batch():
    """
    Получить информацию о нескольких задачах за один запрос.
    
    Ожидает: {task_keys: ['WEB-123', 'WEB-124', ...]}
    Возвращает: {tasks: {WEB-123: {...}, WEB-124: {...}, ...}}
    
    Максимум 50 задач за запрос.
    """
    try:
        data = request.json
        task_keys = data.get('task_keys', [])
        
        if not task_keys:
            return jsonify({'success': False, 'error': 'task_keys required'}), 400
        
        # Ограничиваем количество задач за один запрос
        if len(task_keys) > 50:
            logger.warning(f"Запрошено {len(task_keys)} задач, ограничиваем до 50")
            task_keys = task_keys[:50]
        
        jira = get_jira_connection()
        
        # Формируем JQL для получения всех задач сразу
        # Ключи задач могут быть в формате 'WEB-123' или просто '123'
        formatted_keys = []
        for key in task_keys:
            # Убераем лишние кавычки и пробелы
            key = str(key).strip().strip("'\"")
            if key:
                formatted_keys.append(key)
        
        if not formatted_keys:
            return jsonify({'success': False, 'error': 'Нет валидных ключей задач'}), 400
        
        jql = 'key IN (' + ','.join(formatted_keys) + ')'
        
        # Получаем все задачи с changelog
        issues = jira.search_issues(jql, fields='*all', expand='changelog', maxResults=50)
        
        # Формируем результат
        result = {}
        for issue in issues:
            task_data = {
                'key': issue.key,
                'id': issue.id,
                'summary': issue.fields.summary if issue.fields.summary else '',
                'status': issue.fields.status.name if issue.fields.status else '',
                'assignee': issue.fields.assignee.displayName if issue.fields.assignee else None,
                'created': issue.fields.created,
                'updated': issue.fields.updated,
                'resolutiondate': issue.fields.resolutiondate,
                'timespent': issue.fields.timespent,
                'timeoriginalestimate': issue.fields.timeoriginalestimate,
                'issuetype': issue.fields.issuetype.name if issue.fields.issuetype else '',
                'priority': issue.fields.priority.name if issue.fields.priority else '',
                'duedate': issue.fields.duedate,
            }
            
            # Добавляем changelog
            if hasattr(issue, 'changelog') and issue.changelog:
                changelog = []
                for history in issue.changelog.histories:
                    history_item = {
                        'author': history.author.displayName if hasattr(history.author, 'displayName') else str(history.author),
                        'created': history.created,
                        'items': []
                    }
                    for item in history.items:
                        history_item['items'].append({
                            'field': item.field,
                            'from': item.fromString,
                            'to': item.toString
                        })
                    changelog.append(history_item)
                task_data['changelog'] = changelog
            
            result[issue.key] = task_data
        
        logger.info(f"✅ Batch-запрос: получено {len(result)} из {len(formatted_keys)} задач")
        return jsonify({'success': True, 'tasks': result, 'count': len(result)})
    
    except Exception as e:
        import traceback
        logger.error(f"❌ Ошибка batch-запроса: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/report', methods=['POST'])
@validate_json_request
@conditional_cache(timeout=300)  # Кэш на 5 минут для production
def api_report():
    try:
        data = request.get_json()
        # Поддержка множественного выбора (список) или одиночного (строка)
        projects_raw = data.get('projects', []) or data.get('project', '').strip() or None
        assignees_raw = data.get('assignees', []) or data.get('assignee', '').strip() or None
        issue_types_raw = data.get('issue_types', []) or data.get('issue_type', '').strip() or None

        # Нормализация фильтров
        projects = normalize_filter(projects_raw, upper=True) if projects_raw else []
        assignees = normalize_filter(assignees_raw) if assignees_raw else []
        issue_types = normalize_filter(issue_types_raw) if issue_types_raw else []

        start_date = data.get('start_date', '').strip() or None
        end_date = data.get('end_date', '').strip() or None
        days = int(data.get('days', 0) or 0)  # 0 = без ограничений по датам
        blocks = data.get('blocks', None)
        extra_verbose = data.get('extra_verbose', False)

        if days < 0 or days > MAX_REPORT_DAYS:
            return jsonify({'error': f'Период должен быть от 0 до {MAX_REPORT_DAYS} дней (0 = без ограничений)'}), 400

        report = generate_report(
            project_keys=projects,
            start_date=start_date,
            end_date=end_date,
            days=days,
            assignee_filter=assignees,
            issue_types=issue_types,
            blocks=blocks,
            verbose=False,
            extra_verbose=extra_verbose
        )

        response = {
            'success': True,
            'period': report['period'],
            'totals': {
                'projects': report['total_projects'],
                'tasks': report['total_tasks'],
                'correct': report['total_correct'],
                'issues': report['total_issues'],
                'spent': round(report['total_spent'], 2),
                'estimated': round(report['total_estimated'], 2)
            },
            'blocks': report['blocks']
        }

        if 'summary' in report:
            response['summary'] = report['summary'].to_dict(orient='records')
        if 'assignees' in report:
            response['assignees'] = report['assignees'].to_dict(orient='records')
        if 'detail' in report:
            response['detail'] = report['detail'].to_dict(orient='records')
        if 'issues' in report:
            response['issues'] = report['issues'].to_dict(orient='records')
        if 'internal' in report:
            response['internal'] = report['internal'].to_dict(orient='records')
        if 'risk_zone' in report:
            response['risk_zone'] = report['risk_zone'].to_dict(orient='records')

        # Debug-информация
        response['debug'] = {
            'jira_server': JIRA_SERVER,
            'query_params': {
                'projects': projects,
                'assignees': assignees,
                'issue_types': issue_types,
                'start_date': start_date,
                'end_date': end_date,
                'days': days,
                'blocks': blocks,
                'extra_verbose': extra_verbose
            }
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Ошибка генерации отчёта: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
@validate_json_request
def api_download():
    try:
        data = request.get_json()
        # Поддержка множественного выбора
        projects_raw = data.get('projects', []) or data.get('project', '').strip() or None
        assignees_raw = data.get('assignees', []) or data.get('assignee', '').strip() or None
        issue_types_raw = data.get('issue_types', []) or data.get('issue_type', '').strip() or None
        export_format = data.get('format', 'xlsx')  # Новый параметр: format

        # Нормализация фильтров
        projects = normalize_filter(projects_raw, upper=True) if projects_raw else []
        assignees = normalize_filter(assignees_raw) if assignees_raw else []
        issue_types = normalize_filter(issue_types_raw) if issue_types_raw else []

        start_date = data.get('start_date', '').strip() or None
        end_date = data.get('end_date', '').strip() or None
        days = int(data.get('days', 0) or 0)
        blocks = data.get('blocks', None)
        extra_verbose = data.get('extra_verbose', False)

        report = generate_report(
            project_keys=projects,
            start_date=start_date,
            end_date=end_date,
            days=days,
            assignee_filter=assignees,
            issue_types=issue_types,
            blocks=blocks,
            verbose=False,
            extra_verbose=extra_verbose
        )

        # PDF экспорт
        if export_format == 'pdf':
            try:
                from core.pdf_export import generate_pdf_report
                pdf_bytes = generate_pdf_report(report)
                
                if not pdf_bytes:
                    logger.warning("PDF экспорт не удался, возвращаем Excel")
                    # Fallback на Excel
                    output = io.BytesIO()
                    generate_excel(report, output)
                    output.seek(0)
                    filename = f"jira_report_{report['period'].replace(' — ', '_to_').replace(' ', '')}.xlsx"
                    return send_file(
                        output,
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        as_attachment=True,
                        download_name=filename
                    )
                
                filename = f"jira_report_{report['period'].replace(' — ', '_to_').replace(' ', '')}.pdf"
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=filename
                )
            except ImportError:
                logger.error("WeasyPrint не установлен")
                return jsonify({'error': 'PDF экспорт недоступен'}), 503
            except Exception as e:
                logger.error(f"Ошибка PDF экспорта: {e}")
                return jsonify({'error': str(e)}), 500

        # Excel экспорт (по умолчанию)
        output = io.BytesIO()
        generate_excel(report, output)
        output.seek(0)

        filename = f"jira_report_{report['period'].replace(' — ', '_to_').replace(' ', '')}.xlsx"

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/csv', methods=['POST'])
@validate_json_request
def api_download_csv():
    """
    Скачать отчёт в формате CSV.
    
    Формирует ZIP-архив с CSV-файлами для каждого блока отчёта.
    """
    try:
        from zipfile import ZipFile
        
        data = request.get_json()
        # Поддержка множественного выбора
        projects_raw = data.get('projects', []) or data.get('project', '').strip() or None
        assignees_raw = data.get('assignees', []) or data.get('assignee', '').strip() or None
        issue_types_raw = data.get('issue_types', []) or data.get('issue_type', '').strip() or None

        # Нормализация фильтров
        projects = normalize_filter(projects_raw, upper=True) if projects_raw else []
        assignees = normalize_filter(assignees_raw) if assignees_raw else []
        issue_types = normalize_filter(issue_types_raw) if issue_types_raw else []

        start_date = data.get('start_date', '').strip() or None
        end_date = data.get('end_date', '').strip() or None
        days = int(data.get('days', 0) or 0)
        blocks = data.get('blocks', None)
        extra_verbose = data.get('extra_verbose', False)

        report = generate_report(
            project_keys=projects,
            start_date=start_date,
            end_date=end_date,
            days=days,
            assignee_filter=assignees,
            issue_types=issue_types,
            blocks=blocks,
            verbose=False,
            extra_verbose=extra_verbose
        )

        # Создаём ZIP-архив с CSV-файлами
        zip_buffer = io.BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            # Сводка по проектам
            if 'summary' in report:
                csv_buffer = io.StringIO()
                report['summary'].to_csv(csv_buffer, index=False, sep=';')
                zip_file.writestr('summary.csv', csv_buffer.getvalue().encode('utf-8'))
            
            # Нагрузка по исполнителям
            if 'assignees' in report:
                csv_buffer = io.StringIO()
                report['assignees'].to_csv(csv_buffer, index=False, sep=';')
                zip_file.writestr('assignees.csv', csv_buffer.getvalue().encode('utf-8'))
            
            # Детализация по задачам
            if 'detail' in report:
                csv_buffer = io.StringIO()
                report['detail'].to_csv(csv_buffer, index=False, sep=';')
                zip_file.writestr('detail.csv', csv_buffer.getvalue().encode('utf-8'))
            
            # Проблемные задачи
            if 'issues' in report:
                csv_buffer = io.StringIO()
                report['issues'].to_csv(csv_buffer, index=False, sep=';')
                zip_file.writestr('issues.csv', csv_buffer.getvalue().encode('utf-8'))

        zip_buffer.seek(0)

        filename = f"jira_report_{report['period'].replace(' — ', '_to_').replace(' ', '')}.zip"

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Ошибка экспорта CSV: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# =============================================
# НОВЫЕ API ENDPOINTS (Dashboard 2.0)
# =============================================

@app.route('/api/reports/history')
@conditional_cache(timeout=60)
def api_reports_history():
    """Получить историю отчётов."""
    from core.report_service import get_reports_list, initialize_database
    
    # Инициализируем БД если нужно
    initialize_database()
    
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    report_type = request.args.get('type', None)
    project_key = request.args.get('project', None)
    
    reports = get_reports_list(
        limit=limit,
        offset=offset,
        report_type=report_type,
        project_key=project_key,
    )
    
    return jsonify({
        'success': True,
        'reports': [r.to_dict() for r in reports],
        'count': len(reports),
    })


@app.route('/api/reports/<int:report_id>')
def api_report_by_id(report_id):
    """Получить отчёт по ID."""
    from core.report_service import get_report_by_id, get_comments
    
    report = get_report_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'error': 'Отчёт не найден'}), 404
    
    return jsonify({
        'success': True,
        'report': report.to_dict(),
        'comments': [c.to_dict() for c in get_comments(report_id)],
    })


@app.route('/api/reports/compare')
def api_reports_compare():
    """Сравнить два отчёта."""
    from core.report_service import compare_reports
    
    report1_id = request.args.get('report1', type=int)
    report2_id = request.args.get('report2', type=int)
    
    if not report1_id or not report2_id:
        return jsonify({'success': False, 'error': 'report1 и report2 обязательны'}), 400
    
    comparison = compare_reports(report1_id, report2_id)
    if not comparison:
        return jsonify({'success': False, 'error': 'Отчёты не найдены'}), 404
    
    return jsonify({'success': True, 'comparison': comparison})


@app.route('/api/reports/<int:report_id>/comment', methods=['POST'])
@validate_json_request
def api_add_comment(report_id):
    """Добавить комментарий к отчёту."""
    from core.report_service import add_comment
    
    data = request.get_json()
    text = data.get('text', '').strip()
    is_pinned = data.get('is_pinned', False)
    
    if not text:
        return jsonify({'success': False, 'error': 'Текст комментария обязателен'}), 400
    
    comment = add_comment(
        report_id=report_id,
        text=text,
        created_by='user',
        is_pinned=is_pinned,
    )
    
    if comment:
        return jsonify({'success': True, 'comment': comment.to_dict()})
    else:
        return jsonify({'success': False, 'error': 'Ошибка добавления комментария'}), 500


@app.route('/api/reports/<int:report_id>/comment/<int:comment_id>', methods=['DELETE'])
def api_delete_comment(report_id, comment_id):
    """Удалить комментарий."""
    from core.report_service import delete_comment
    
    if delete_comment(comment_id):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Комментарий не найден'}), 404


@app.route('/api/scheduled-reports', methods=['GET'])
def api_scheduled_reports_list():
    """Список расписаний отчётов."""
    from core.report_service import get_active_scheduled_reports
    from core.models import get_session, ScheduledReport
    
    session = get_session()
    try:
        reports = session.query(ScheduledReport).all()
        return jsonify({
            'success': True,
            'reports': [r.to_dict() for r in reports],
        })
    finally:
        session.close()


@app.route('/api/scheduled-reports', methods=['POST'])
@validate_json_request
def api_create_scheduled_report():
    """Создать расписание отчёта."""
    from core.report_service import create_scheduled_report
    from core.scheduler import add_scheduled_job
    
    data = request.get_json()
    
    scheduled = create_scheduled_report(
        name=data.get('name', 'Без названия'),
        schedule_type=data.get('schedule_type', 'weekly'),
        schedule_day=data.get('schedule_day'),
        schedule_hour=data.get('schedule_hour', 9),
        projects=data.get('projects', []),
        assignees=data.get('assignees', []),
        issue_types=data.get('issue_types', []),
        blocks=data.get('blocks', []),
        days=data.get('days', 30),
        email_recipients=data.get('email_recipients', []),
        telegram_chats=data.get('telegram_chats', []),
        send_excel=data.get('send_excel', True),
        send_pdf=data.get('send_pdf', False),
    )
    
    if scheduled:
        # Добавляем в планировщик
        add_scheduled_job(scheduled.id)
        return jsonify({'success': True, 'report': scheduled.to_dict()})
    else:
        return jsonify({'success': False, 'error': 'Ошибка создания расписания'}), 500


@app.route('/api/scheduled-reports/<int:report_id>/toggle', methods=['POST'])
def api_toggle_scheduled_report(report_id):
    """Переключить статус расписания."""
    from core.report_service import toggle_scheduled_report
    from core.scheduler import remove_scheduled_job, add_scheduled_job
    
    new_status = toggle_scheduled_report(report_id)
    if new_status is None:
        return jsonify({'success': False, 'error': 'Расписание не найдено'}), 404
    
    # Обновляем планировщик
    if new_status:
        add_scheduled_job(report_id)
    else:
        remove_scheduled_job(report_id)
    
    return jsonify({'success': True, 'is_active': new_status})


@app.route('/api/scheduled-reports/<int:report_id>', methods=['DELETE'])
def api_delete_scheduled_report(report_id):
    """Удалить расписание."""
    from core.models import get_session, ScheduledReport
    from core.scheduler import remove_scheduled_job
    
    session = get_session()
    try:
        report = session.query(ScheduledReport).filter(
            ScheduledReport.id == report_id
        ).first()
        if report:
            session.delete(report)
            session.commit()
            remove_scheduled_job(report_id)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Расписание не найдено'}), 404
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/telegram/subscribe', methods=['POST'])
@validate_json_request
def api_telegram_subscribe():
    """Подписаться на Telegram уведомления."""
    from core.report_service import subscribe_telegram
    from core.telegram_bot import send_welcome_message
    import asyncio
    
    data = request.get_json()
    chat_id = data.get('chat_id', '').strip()
    username = data.get('username', '').strip()
    
    if not chat_id:
        return jsonify({'success': False, 'error': 'chat_id обязателен'}), 400
    
    subscription = subscribe_telegram(
        chat_id=chat_id,
        username=username,
        notify_risk_zone=data.get('notify_risk_zone', True),
        notify_scheduled=data.get('notify_scheduled', True),
        threshold_days=data.get('threshold_days', 7),
    )
    
    if subscription:
        # Отправляем приветственное сообщение
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(send_welcome_message(chat_id, username))
        except Exception as e:
            logger.warning(f"Не удалось отправить welcome сообщение: {e}")
        
        return jsonify({'success': True, 'subscription': subscription.to_dict()})
    else:
        return jsonify({'success': False, 'error': 'Ошибка подписки'}), 500


@app.route('/api/telegram/unsubscribe', methods=['POST'])
@validate_json_request
def api_telegram_unsubscribe():
    """Отписаться от Telegram уведомлений."""
    from core.report_service import unsubscribe_telegram
    
    data = request.get_json()
    chat_id = data.get('chat_id', '').strip()
    
    if not chat_id:
        return jsonify({'success': False, 'error': 'chat_id обязателен'}), 400
    
    if unsubscribe_telegram(chat_id):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Подписка не найдена'}), 404


@app.route('/api/reports/<int:report_id>/download/pdf')
def api_download_pdf(report_id):
    """Скачать PDF отчёт."""
    from core.report_service import get_report_by_id
    from core.jira_report import generate_report
    from core.pdf_export import generate_pdf_report
    
    report = get_report_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'error': 'Отчёт не найден'}), 404
    
    # Если PDF уже сохранён
    if report.pdf_path and os.path.exists(report.pdf_path):
        return send_file(
            report.pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"report_{report_id}.pdf",
        )
    
    # Генерируем новый PDF
    report_data = generate_report(
        project_keys=report.projects,
        assignees=report.assignees,
        issue_types=report.issue_types,
        blocks=None,  # Все блоки
        days=0,
        start_date=report.start_date,
        end_date=report.end_date,
    )
    
    pdf_bytes = generate_pdf_report(report_data)
    if not pdf_bytes:
        return jsonify({'success': False, 'error': 'Ошибка генерации PDF'}), 500
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"report_{report_id}.pdf",
    )


@app.route('/api/reports/<int:report_id>/download/excel')
def api_download_excel(report_id):
    """Скачать Excel отчёт."""
    from core.report_service import get_report_by_id
    from core.jira_report import generate_report, generate_excel
    
    report = get_report_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'error': 'Отчёт не найден'}), 404
    
    # Если Excel уже сохранён
    if report.excel_path and os.path.exists(report.excel_path):
        return send_file(
            report.excel_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"report_{report_id}.xlsx",
        )
    
    # Генерируем новый Excel
    report_data = generate_report(
        project_keys=report.projects,
        assignees=report.assignees,
        issue_types=report.issue_types,
        blocks=None,
        days=0,
        start_date=report.start_date,
        end_date=report.end_date,
    )
    
    output = io.BytesIO()
    generate_excel(report_data, output)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f"report_{report_id}.xlsx",
    )


@app.route('/api/scheduler/status')
def api_scheduler_status():
    """Статус планировщика задач."""
    from core.scheduler import get_scheduler_status, initialize_database
    
    initialize_database()
    
    status = get_scheduler_status()
    return jsonify({'success': True, **status})


@app.route('/api/metrics/velocity')
@conditional_cache(timeout=300)
def api_velocity_metrics():
    """Метрики Sprint Velocity."""
    from core.jira_report import generate_report
    
    # Получаем данные за последние 30 дней
    report = generate_report(days=30, blocks=['detail'])
    
    if 'detail' not in report or not report['detail']:
        return jsonify({'success': True, 'velocity': [], 'avg_velocity': 0})
    
    # Группируем по неделям
    detail = report['detail']
    detail['resolution_date'] = pd.to_datetime(detail['Дата решения'])
    detail['week'] = detail['resolution_date'].dt.to_period('W').apply(lambda r: r.start_time)
    
    velocity = detail.groupby('week').size().reset_index(name='tasks')
    velocity['week'] = velocity['week'].astype(str)
    
    avg_velocity = velocity['tasks'].mean() if len(velocity) > 0 else 0
    
    return jsonify({
        'success': True,
        'velocity': velocity.to_dict('records'),
        'avg_velocity': round(avg_velocity, 2),
    })


@app.route('/api/metrics/burndown')
@conditional_cache(timeout=300)
def api_burndown_metrics():
    """Метрики Burndown Chart."""
    from core.jira_report import generate_report
    from datetime import timedelta
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    if not start_date or not end_date:
        return jsonify({'success': False, 'error': 'start_date и end_date обязательны'}), 400
    
    report = generate_report(
        start_date=start_date,
        end_date=end_date,
        blocks=['detail'],
    )
    
    if 'detail' not in report or not report['detail']:
        return jsonify({'success': True, 'burndown': []})
    
    detail = report['detail']
    detail['created_date'] = pd.to_datetime(detail['Дата создания'])
    detail['resolution_date'] = pd.to_datetime(detail['Дата решения'])
    
    # Строим burndown
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    total_tasks = len(detail)
    
    burndown = []
    current = start
    remaining = total_tasks
    
    while current <= end:
        closed_by_date = len(detail[detail['resolution_date'] <= current])
        remaining = total_tasks - closed_by_date
        
        burndown.append({
            'date': current.strftime('%Y-%m-%d'),
            'remaining': remaining,
            'ideal': max(0, total_tasks * (1 - (current - start).days / (end - start).days)),
        })
        
        current += timedelta(days=1)
    
    return jsonify({
        'success': True,
        'burndown': burndown,
        'total_tasks': total_tasks,
    })


@app.route('/api/metrics/workload')
@conditional_cache(timeout=300)
def api_workload_metrics():
    """Метрики Workload по исполнителям."""
    from core.jira_report import generate_report
    
    report = generate_report(days=30, blocks=['assignees'])
    
    if 'assignees' not in report or not report['assignees']:
        return jsonify({'success': True, 'workload': []})
    
    assignees = report['assignees']
    
    # Вычисляем перегруженность
    avg_tasks = assignees['Задач'].mean() if len(assignees) > 0 else 0
    
    workload = assignees.to_dict('records')
    for item in workload:
        item['is_overloaded'] = item['Задач'] > avg_tasks * 1.5
        item['workload_ratio'] = round(item['Задач'] / avg_tasks, 2) if avg_tasks > 0 else 0
    
    return jsonify({
        'success': True,
        'workload': workload,
        'avg_tasks': round(avg_tasks, 2),
    })


@app.route('/api/metrics/kpi')
@conditional_cache(timeout=300)
def api_kpi_metrics():
    """Custom KPI метрики: Cycle time, Lead time."""
    from core.jira_report import generate_report
    
    report = generate_report(days=30, blocks=['detail'])
    
    if 'detail' not in report or not report['detail']:
        return jsonify({'success': True, 'kpi': {}})
    
    detail = report['detail']
    detail['created'] = pd.to_datetime(detail['Дата создания'])
    detail['resolved'] = pd.to_datetime(detail['Дата решения'])
    detail['due'] = pd.to_datetime(detail['Дата исполнения'])
    
    # Cycle time: от начала работы до завершения
    # Lead time: от создания до завершения
    detail['cycle_time'] = (detail['resolved'] - detail['created']).dt.days
    detail['lead_time'] = (detail['resolved'] - detail['created']).dt.days
    
    kpi = {
        'avg_cycle_time': round(detail['cycle_time'].mean(), 2),
        'median_cycle_time': round(detail['cycle_time'].median(), 2),
        'avg_lead_time': round(detail['lead_time'].mean(), 2),
        'median_lead_time': round(detail['lead_time'].median(), 2),
        'on_time_delivery': round(
            (detail['resolved'] <= detail['due']).sum() / len(detail) * 100, 2
        ) if len(detail) > 0 else 0,
    }
    
    return jsonify({
        'success': True,
        'kpi': kpi,
    })


@app.route('/api/client-pdf', methods=['POST'])
@validate_json_request
def api_client_pdf():
    """Сгенерировать PDF для клиента по конкретной задаче."""
    from core.pdf_export import generate_client_pdf
    from core.jira_report import generate_report
    
    data = request.get_json()
    task_key = data.get('task_key', '')
    
    if not task_key:
        return jsonify({'success': False, 'error': 'task_key обязателен'}), 400
    
    # Получаем данные задачи
    jira = get_jira_connection()
    try:
        issue = jira.issue(task_key, fields='*all')
        
        task_data = {
            'key': issue.key,
            'summary': issue.fields.summary,
            'spent': convert_seconds_to_hours(issue.fields.timespent),
            'type': issue.fields.issuetype.name if issue.fields.issuetype else '',
        }
        
        # Генерируем отчёт
        report = generate_report(
            project_keys=[issue.fields.project.key],
            blocks=['detail'],
            days=0,
        )
        
        pdf_bytes = generate_client_pdf(report, task_key, task_data)
        
        if not pdf_bytes:
            return jsonify({'success': False, 'error': 'Ошибка генерации PDF'}), 500
        
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{task_key}_report.pdf",
        )
    
    except Exception as e:
        logger.error(f"Ошибка генерации client PDF: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Настройка ротации логов для production
    if IS_PRODUCTION:
        from logging.handlers import RotatingFileHandler
        import os
        
        # Создаём директорию для логов
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # Настраиваем ротацию: 10MB, 5 бэкапов
        file_handler = RotatingFileHandler(
            'logs/jira_report.log',
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.info("🚀 Запуск Jira Report System с ротацией логов")
    
    mode = "prod" if IS_PRODUCTION else "dev"
    print("🚀 Запуск веб-интерфейса...")
    print(f"📍 Откройте в браузере: http://localhost:{ACTIVE_PORT}")
    print(f"📦 Доступные блоки: {', '.join(REPORT_BLOCKS.keys())}")
    print(f"🔧 Режим: {mode}, Хост: {FLASK_HOST}, Порт: {ACTIVE_PORT}")
    app.run(host=FLASK_HOST, port=ACTIVE_PORT, debug=not IS_PRODUCTION)
