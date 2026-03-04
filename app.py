# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, send_file
from jira_report import generate_report, generate_excel, REPORT_BLOCKS, EXCLUDED_PROJECTS, get_jira_connection
from datetime import datetime
import io
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))

@app.route('/')
def index():
    return render_template('index.html', blocks=REPORT_BLOCKS)

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

        # Используем API пользователей — намного эффективнее
        # Получаем всех активных пользователей с правами на просмотр задач
        users = jira.search_assignable_users_for_projects('')

        assignees = {}
        for user in users:
            if user.get('active', True):  # Только активные
                key = user.get('name') or user.get('accountId') or user.get('key')
                name = user.get('displayName', key)
                if key:
                    assignees[key] = name

        result = [{'key': k, 'name': v} for k, v in sorted(assignees.items(), key=lambda x: x[1])]
        return jsonify({'success': True, 'assignees': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/report', methods=['POST'])
def api_report():
    try:
        data = request.json
        project = data.get('project', '').strip() or None
        start_date = data.get('start_date', '').strip() or None
        days = int(data.get('days', 30))
        assignee = data.get('assignee', '').strip() or None
        blocks = data.get('blocks', None)
        extra_verbose = data.get('extra_verbose', False)
        
        if days < 1 or days > 365:
            return jsonify({'error': 'Период должен быть от 1 до 365 дней'}), 400
        
        report = generate_report(
            project_key=project,
            start_date=start_date,
            days=days,
            assignee_filter=assignee,
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
        
        return jsonify(response)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def api_download():
    try:
        data = request.json
        project = data.get('project', '').strip() or None
        start_date = data.get('start_date', '').strip() or None
        days = int(data.get('days', 30))
        assignee = data.get('assignee', '').strip() or None
        blocks = data.get('blocks', None)
        extra_verbose = data.get('extra_verbose', False)
        
        report = generate_report(
            project_key=project,
            start_date=start_date,
            days=days,
            assignee_filter=assignee,
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
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5000'))
    
    print("🚀 Запуск веб-интерфейса...")
    print(f"📍 Откройте в браузере: http://localhost:{port}")
    print(f"📦 Доступные блоки: {', '.join(REPORT_BLOCKS.keys())}")
    print(f"🔧 Хост: {host}, Порт: {port}")
    app.run(host=host, port=port, debug=False)