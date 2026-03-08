# -*- coding: utf-8 -*-
"""
Веб-интерфейс системы отчётов Jira.

Flask-приложение для предоставления API и UI.
"""
from flask import Flask, render_template, request, jsonify, send_file
from flask_caching import Cache
from core.jira_report import generate_report, generate_excel, get_jira_connection, normalize_filter
from core.config import (
    REPORT_BLOCKS,
    EXCLUDED_PROJECTS,
    ACTIVE_PORT,
    FLASK_HOST,
    IS_PRODUCTION,
    JIRA_SERVER,
    MAX_REPORT_DAYS,
    MAX_SEARCH_RESULTS
)
from datetime import datetime
import io
import os
import logging
from functools import wraps

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Путь к шаблонам теперь на уровень выше (templates в корне проекта)
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, '..', 'templates'))

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


def conditional_cache(timeout=300):
    """
    Декоратор для условного кэширования: кэширует только в production.

    Args:
        timeout: Время кэширования в секундах

    Usage:
        @conditional_cache(timeout=300)
        def api_projects():
            return _api_projects_logic()
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if cache_init and cache:
                # Создаём кэшированную версию функции
                cached_f = cache.cached(timeout=timeout)(f)
                return cached_f(*args, **kwargs)
            else:
                return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_json_request(f):
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
_project_cache = {}
_project_cache_time = {}
_PROJECT_CACHE_TTL = 3600  # 1 час


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
            return _project_cache[proj_key]
    
    # Получаем из Jira
    try:
        proj = jira.project(proj_key)
        _project_cache[proj_key] = proj
        _project_cache_time[proj_key] = time.time()
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

def _get_api_projects():
    """Получить список проектов"""
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

def _get_api_assignees():
    """Получить список всех активных исполнителей"""
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


def _add_user_to_assignees(user, assignees_dict):
    """Добавляет пользователя в словарь исполнителей"""
    if isinstance(user, dict):
        is_active = user.get('active', False) is True
        key = user.get('name') or user.get('accountId') or user.get('key')
        name = user.get('displayName', key) or user.get('name', key)
    else:
        is_active = getattr(user, 'active', False) is True
        key = getattr(user, 'name', None) or getattr(user, 'accountId', None) or getattr(user, 'key', None)
        name = getattr(user, 'displayName', None) or getattr(user, 'name', key)
    
    if is_active and key:
        assignees_dict[key] = name


def _get_assignees_from_issues(jira):
    """Альтернативный метод: получаем исполнителей из последних задач"""
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
