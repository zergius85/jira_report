# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, send_file
from jira_report import generate_report, generate_excel, get_jira_connection
from config import REPORT_BLOCKS, EXCLUDED_PROJECTS, ACTIVE_PORT, FLASK_HOST, IS_PRODUCTION
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
    """РџРѕР»СѓС‡РёС‚СЊ СЃРїРёСЃРѕРє РїСЂРѕРµРєС‚РѕРІ"""
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
    """РџРѕР»СѓС‡РёС‚СЊ СЃРїРёСЃРѕРє РёСЃРїРѕР»РЅРёС‚РµР»РµР№ С‡РµСЂРµР· Jira Users API"""
    try:
        jira = get_jira_connection()

        # РСЃРїРѕР»СЊР·СѓРµРј API РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ вЂ” РЅР°РјРЅРѕРіРѕ СЌС„С„РµРєС‚РёРІРЅРµРµ
        # РџРѕР»СѓС‡Р°РµРј РІСЃРµС… Р°РєС‚РёРІРЅС‹С… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ СЃ РїСЂР°РІР°РјРё РЅР° РїСЂРѕСЃРјРѕС‚СЂ Р·Р°РґР°С‡
        users = jira.search_assignable_users_for_projects('')

        assignees = {}
        for user in users:
            if user.get('active', True):  # РўРѕР»СЊРєРѕ Р°РєС‚РёРІРЅС‹Рµ
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
            return jsonify({'error': 'РџРµСЂРёРѕРґ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РѕС‚ 1 РґРѕ 365 РґРЅРµР№'}), 400
        
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
        if 'internal' in report:
            response['internal'] = report['internal'].to_dict(orient='records')

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
        
        filename = f"jira_report_{report['period'].replace(' вЂ” ', '_to_').replace(' ', '')}.xlsx"
        
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
    print("рџљЂ Р—Р°РїСѓСЃРє РІРµР±-РёРЅС‚РµСЂС„РµР№СЃР°...")
    print(f"рџ“Ќ РћС‚РєСЂРѕР№С‚Рµ РІ Р±СЂР°СѓР·РµСЂРµ: http://localhost:{ACTIVE_PORT}")
    print(f"рџ“¦ Р”РѕСЃС‚СѓРїРЅС‹Рµ Р±Р»РѕРєРё: {', '.join(REPORT_BLOCKS.keys())}")
    print(f"рџ”§ Р РµР¶РёРј: {mode}, РҐРѕСЃС‚: {FLASK_HOST}, РџРѕСЂС‚: {ACTIVE_PORT}")
    app.run(host=FLASK_HOST, port=ACTIVE_PORT, debug=not IS_PRODUCTION)