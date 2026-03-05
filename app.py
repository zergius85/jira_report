# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, send_file
from jira_report import generate_report, generate_excel, get_jira_connection
from config import REPORT_BLOCKS, EXCLUDED_PROJECTS, ACTIVE_PORT, FLASK_HOST, IS_PRODUCTION, JIRA_SERVER
from datetime import datetime
import io
import os
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

@app.route('/')
def index():
    return render_template('index.html', blocks=REPORT_BLOCKS, JIRA_SERVER=JIRA_SERVER)

@app.route('/api/projects')
def api_projects():
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
def api_assignees():
    """Получить список исполнителей через Jira Users API"""
    try:
        jira = get_jira_connection()
        logger.info("🔍 Загрузка исполнителей из Jira...")
        
        # Пробуем разные методы получения пользователей
        assignees = {}
        
        # Метод 1: search_users с пустым запросом
        try:
            logger.info("  → Пробуем search_users('')...")
            users = jira.search_users('')
            logger.info(f"     Найдено пользователей: {len(users)}")
            for user in users:
                if isinstance(user, dict):
                    is_active = user.get('active', True)
                    key = user.get('name') or user.get('accountId') or user.get('key')
                    name = user.get('displayName', key) or user.get('name', key)
                else:
                    is_active = getattr(user, 'active', True)
                    key = getattr(user, 'name', None) or getattr(user, 'accountId', None) or getattr(user, 'key', None)
                    name = getattr(user, 'displayName', None) or getattr(user, 'name', key)
                
                if is_active and key:
                    assignees[key] = name
            logger.info(f"     Активных: {len(assignees)}")
        except Exception as e1:
            logger.warning(f"  ✗ search_users не сработал: {e1}")
            
            # Метод 2: получить пользователей из проектов
            try:
                logger.info("  → Пробуем search_assignable_users_for_projects...")
                projects = jira.projects()
                for proj in projects:
                    if proj.key in EXCLUDED_PROJECTS:
                        continue
                    # Получаем назначаемых пользователей для проекта
                    assignable = jira.search_assignable_users_for_projects(proj.key)
                    for user in assignable:
                        if isinstance(user, dict):
                            is_active = user.get('active', True)
                            key = user.get('name') or user.get('accountId') or user.get('key')
                            name = user.get('displayName', key)
                        else:
                            is_active = getattr(user, 'active', True)
                            key = getattr(user, 'name', None) or getattr(user, 'accountId', None)
                            name = getattr(user, 'displayName', key)
                        
                        if is_active and key:
                            assignees[key] = name
                logger.info(f"     Найдено уникальных исполнителей: {len(assignees)}")
            except Exception as e2:
                logger.warning(f"  ✗ search_assignable_users_for_projects не сработал: {e2}")

        result = [{'key': k, 'name': v} for k, v in sorted(assignees.items(), key=lambda x: x[1])]
        logger.info(f"✅ Возвращаем {len(result)} исполнителей")
        return jsonify({'success': True, 'assignees': result})
    except Exception as e:
        import traceback
        logger.error(f"❌ Ошибка загрузки исполнителей: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

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
        import traceback
        traceback.print_exc()
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
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/report', methods=['POST'])
def api_report():
    try:
        data = request.json
        # Поддержка множественного выбора (список) или одиночного (строка)
        projects = data.get('projects', []) or data.get('project', '').strip() or None
        if isinstance(projects, str):
            projects = [projects]
        
        assignees = data.get('assignees', []) or data.get('assignee', '').strip() or None
        if isinstance(assignees, str):
            assignees = [assignees]
        
        issue_types = data.get('issue_types', []) or data.get('issue_type', '').strip() or None
        if isinstance(issue_types, str):
            issue_types = [issue_types]
        
        start_date = data.get('start_date', '').strip() or None
        days = int(data.get('days', 0) or 0)  # 0 = без ограничений по датам
        blocks = data.get('blocks', None)
        extra_verbose = data.get('extra_verbose', False)

        if days < 0 or days > 365:
            return jsonify({'error': 'Период должен быть от 0 до 365 дней (0 = без ограничений)'}), 400

        report = generate_report(
            project_keys=projects,
            start_date=start_date,
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

        # Debug-информация
        response['debug'] = {
            'jira_server': JIRA_SERVER,
            'query_params': {
                'projects': projects,
                'assignees': assignees,
                'issue_types': issue_types,
                'start_date': start_date,
                'days': days,
                'blocks': blocks,
                'extra_verbose': extra_verbose
            }
        }

        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def api_download():
    try:
        data = request.json
        # Поддержка множественного выбора
        projects = data.get('projects', []) or data.get('project', '').strip() or None
        if isinstance(projects, str):
            projects = [projects]
        
        assignees = data.get('assignees', []) or data.get('assignee', '').strip() or None
        if isinstance(assignees, str):
            assignees = [assignees]
        
        issue_types = data.get('issue_types', []) or data.get('issue_type', '').strip() or None
        if isinstance(issue_types, str):
            issue_types = [issue_types]
        
        start_date = data.get('start_date', '').strip() or None
        days = int(data.get('days', 0) or 0)
        blocks = data.get('blocks', None)
        extra_verbose = data.get('extra_verbose', False)

        report = generate_report(
            project_keys=projects,
            start_date=start_date,
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

if __name__ == '__main__':
    mode = "prod" if IS_PRODUCTION else "dev"
    print("🚀 Запуск веб-интерфейса...")
    print(f"📍 Откройте в браузере: http://localhost:{ACTIVE_PORT}")
    print(f"📦 Доступные блоки: {', '.join(REPORT_BLOCKS.keys())}")
    print(f"🔧 Режим: {mode}, Хост: {FLASK_HOST}, Порт: {ACTIVE_PORT}")
    app.run(host=FLASK_HOST, port=ACTIVE_PORT, debug=not IS_PRODUCTION)
