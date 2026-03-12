"""
Модуль генерации отчётов с объектно-ориентированной архитектурой.

Рефакторинг функции generate_report() на классы для улучшения:
- Тестируемости
- Поддерживаемости
- Расширяемости
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
import pandas as pd
import logging
from dateutil.relativedelta import relativedelta

from core.config import (
    JIRA_SERVER,
    EXCLUDED_PROJECTS,
    CLOSED_STATUS_IDS,
    EXCLUDED_ASSIGNEE_CLOSE,
    REPORT_BLOCKS,
    MAX_SEARCH_RESULTS,
    RISK_ZONE_INACTIVITY_THRESHOLD
)
from core.jira_report import (
    get_jira_connection,
    get_default_start_date,
    convert_seconds_to_hours,
    normalize_filter,
    sanitize_jql_identifier,
    sanitize_jql_string_literal,
    search_all_issues,
    get_column_order,
    get_closed_status_ids
)
from core.services.issue_validator import IssueValidator

logger = logging.getLogger(__name__)


class IssueDataExtractor:
    """Извлекает и форматирует данные из задачи Jira."""

    def __init__(self, extra_verbose: bool = False):
        self.extra_verbose = extra_verbose

    def extract(self, issue, proj_name: str, problems: List[str]) -> Dict[str, Any]:
        """
        Извлекает данные из задачи.

        Args:
            issue: Объект задачи Jira
            proj_name: Название проекта
            problems: Список проблем задачи

        Returns:
            Dict с данными задачи
        """
        fields = issue.fields

        spent = convert_seconds_to_hours(fields.timespent)
        estimated = convert_seconds_to_hours(fields.timeoriginalestimate)

        issue_type = fields.issuetype.name if fields.issuetype else 'Задача'
        assignee = fields.assignee.displayName if fields.assignee else 'Без исполнителя'
        duedate = fields.duedate[:10] if fields.duedate else '-'
        resolved = fields.resolutiondate[:10] if fields.resolutiondate else '-'
        created = fields.created[:10] if fields.created else '-'

        status_name = fields.status.name if fields.status else '-'
        status_category = (
            fields.status.statusCategory.key
            if fields.status and fields.status.statusCategory
            else '-'
        )
        status_full = f"{status_name} ({status_category})"

        # Формируем URL с иконкой 🔍 при extra_verbose
        issue_url = f"{JIRA_SERVER}/browse/{issue.key}"
        if self.extra_verbose:
            issue_url = f"{issue_url} 🔍"

        # Формируем отображаемые значения с ID если нужно
        project_display = self._format_with_id(
            proj_name,
            getattr(fields, 'project', None)
        )
        status_display = self._format_with_id(
            status_full,
            fields.status
        )
        issue_type_display = self._format_with_id(
            issue_type,
            fields.issuetype
        )
        assignee_display = self._format_with_id(
            assignee,
            fields.assignee
        )

        # Даты и числа форматируем с ID при extra_verbose
        duedate_display = self._format_date_with_id(duedate, fields.duedate)
        resolved_display = self._format_date_with_id(resolved, fields.resolutiondate)
        created_display = self._format_date_with_id(created, fields.created)
        spent_display = self._format_number_with_id(spent, fields.timespent)
        estimated_display = self._format_number_with_id(estimated, fields.timeoriginalestimate)

        return {
            'URL': issue_url,
            'Проект': project_display,
            'Ключ': issue.key,
            'Тип': issue_type_display,
            'Задача': fields.summary,
            'Исполнитель': assignee_display,
            'Статус': status_display,
            'Дата создания': created_display,
            'Дата исполнения': duedate_display,
            'Дата решения': resolved_display,
            'Факт (ч)': spent_display,
            'Оценка (ч)': estimated_display,
            'Проблемы': ', '.join(problems) if problems else ''
        }

    def _format_with_id(self, name: str, obj: Any) -> str:
        """
        Форматирует значение с ID если включён extra_verbose.

        Args:
            name: Отображаемое имя
            obj: Объект с id атрибутом

        Returns:
            Строка формата "name [id]" или "name"
        """
        if self.extra_verbose and obj and hasattr(obj, 'id'):
            return f"{name} [{obj.id}]"
        return name

    def _format_date_with_id(self, display_value: str, original_value: Any) -> str:
        """Форматирует дату с ID поля при extra_verbose."""
        if self.extra_verbose and original_value:
            # Извлекаем имя поля из original_value (это строка даты)
            # Для дат используем название поля
            return f"{display_value} [duedate]" if 'due' in str(original_value) else f"{display_value} [created]"
        return display_value

    def _format_number_with_id(self, display_value: float, original_value: Any) -> str:
        """Форматирует число с ID поля при extra_verbose."""
        if self.extra_verbose and original_value is not None:
            return f"{display_value} [timespent]"
        return str(display_value)


class ReportBlockGenerator:
    """Генерирует отдельный блок отчёта."""

    def __init__(self, block_name: str, extra_verbose: bool = False):
        self.block_name = block_name
        self.extra_verbose = extra_verbose
        self.extractor = IssueDataExtractor(extra_verbose)

    def generate_summary(
        self,
        proj_name: str,
        proj_correct: int,
        proj_issues: int,
        proj_estimated: float,
        proj_spent: float,
        issues_normal: Optional[List] = None
    ) -> Dict[str, Any]:
        """Генерирует строку сводки по проекту."""
        if self.extra_verbose and issues_normal:
            proj_obj = getattr(issues_normal[0].fields, 'project', None)
            proj_id = proj_obj.id if proj_obj else ''
            return {
                'Клиент (Проект)': f"{proj_name} [{proj_id}]" if proj_id else proj_name,
                'Задач закрыто': proj_correct + proj_issues,
                'Корректных': proj_correct,
                'С ошибками': proj_issues,
                'Оценка (ч)': f"{round(proj_estimated, 2)} [timeoriginalestimate]",
                'Факт (ч)': f"{round(proj_spent, 2)} [timespent]",
                'Отклонение': round(proj_estimated - proj_spent, 2)
            }
        
        return {
            'Клиент (Проект)': proj_name,
            'Задач закрыто': proj_correct + proj_issues,
            'Корректных': proj_correct,
            'С ошибками': proj_issues,
            'Оценка (ч)': round(proj_estimated, 2),
            'Факт (ч)': round(proj_spent, 2),
            'Отклонение': round(proj_estimated - proj_spent, 2)
        }

    def generate_issue_row(
        self,
        issue,
        assignee: str,
        created: str,
        duedate: str,
        proj_name: str
    ) -> Dict[str, Any]:
        """Генерирует строку проблемной задачи."""
        author = self._get_author(issue)
        author_id = self._get_author_id(issue)
        
        # Формируем URL с иконкой 🔍 при extra_verbose
        issue_url = f"{JIRA_SERVER}/browse/{issue.key}"
        if self.extra_verbose:
            issue_url = f"{issue_url} 🔍"
        
        # Формируем отображаемые значения
        author_display = f"{author} [{author_id}]" if self.extra_verbose and author_id else author
        
        # Получаем ID объекта для полей
        fields = issue.fields
        proj_id = getattr(fields, 'project', None)
        proj_id_str = proj_id.id if proj_id else ''
        proj_display = f"{proj_name} [{proj_id_str}]" if self.extra_verbose and proj_id_str else proj_name
        
        # Формируем даты с [field_name] при extra_verbose
        created_display = f"{created} [created]" if self.extra_verbose and created != '-' else created
        duedate_display = f"{duedate} [duedate]" if self.extra_verbose and duedate != '-' else duedate
        
        # Формируем базовую строку
        return {
            'URL': issue_url,
            'Проект': proj_display,
            'Задача': issue.fields.summary,
            'Исполнитель': assignee,
            'Автор': author_display,
            'Дата создания': created_display,
            'Дата исполнения': duedate_display,
            'Проблемы': ''  # Будет заполнено позже
        }

    def _get_author(self, issue) -> str:
        """Получает автора/создателя задачи."""
        # Пробуем creator
        if hasattr(issue.fields, 'creator') and issue.fields.creator:
            return (
                issue.fields.creator.displayName
                if hasattr(issue.fields.creator, 'displayName')
                else str(issue.fields.creator)
            )
        # Пробуем reporter
        if hasattr(issue.fields, 'reporter') and issue.fields.reporter:
            return (
                issue.fields.reporter.displayName
                if hasattr(issue.fields.reporter, 'displayName')
                else str(issue.fields.reporter)
            )
        # Пробуем author
        if hasattr(issue.fields, 'author') and issue.fields.author:
            return (
                issue.fields.author.displayName
                if hasattr(issue.fields.author, 'displayName')
                else str(issue.fields.author)
            )
        return 'N/A'

    def _get_author_id(self, issue) -> str:
        """Получает ID автора/создателя задачи."""
        if hasattr(issue.fields, 'creator') and issue.fields.creator:
            return (
                issue.fields.creator.id
                if hasattr(issue.fields.creator, 'id')
                else ''
            )
        elif hasattr(issue.fields, 'author') and issue.fields.author:
            return (
                issue.fields.author.id
                if hasattr(issue.fields.author, 'id')
                else ''
            )
        return ''


class RiskZoneAnalyzer:
    """Анализирует задачи на факторы риска."""

    def __init__(self):
        self.today = datetime.now()

    def analyze(self, issue) -> List[str]:
        """
        Анализирует задачу на факторы риска.

        Args:
            issue: Объект задачи Jira

        Returns:
            Список факторов риска
        """
        risk_factors = []

        # 1. Задачи без исполнителя
        if not issue.fields.assignee:
            risk_factors.append('Без исполнителя')

        # 2. Задачи с истёкшим сроком (Due Date)
        if issue.fields.duedate:
            due_date = datetime.strptime(issue.fields.duedate[:10], '%Y-%m-%d')
            status_name = (
                issue.fields.status.name
                if issue.fields.status
                else ''
            )
            status_id = (
                issue.fields.status.id
                if issue.fields.status
                else ''
            )
            # Используем сервис для проверки закрытого статуса
            from core.services.closed_status_service import is_status_closed

            if due_date < self.today and not is_status_closed(status_name=status_name, status_id=status_id):
                days_overdue = (self.today - due_date).days
                risk_factors.append(f'Просрочена на {days_overdue} дн.')

        # 3. Задачи, которые не двигались > порога неактивности
        if hasattr(issue.fields, 'updated') and issue.fields.updated:
            updated = datetime.strptime(
                issue.fields.updated[:19],
                '%Y-%m-%dT%H:%M:%S'
            )
            days_inactive = (self.today - updated).days
            status_name = (
                issue.fields.status.name
                if issue.fields.status
                else ''
            )
            status_id = (
                issue.fields.status.id
                if issue.fields.status
                else ''
            )
            # Используем сервис для проверки закрытого статуса
            from core.services import is_status_closed
            
            if days_inactive > RISK_ZONE_INACTIVITY_THRESHOLD and not is_status_closed(status_name=status_name, status_id=status_id):
                risk_factors.append(f'Не двигается {days_inactive} дн.')

        return risk_factors

    def create_risk_row(self, issue) -> Dict[str, str]:
        """Создаёт строку отчёта Risk Zone."""
        assignee = (
            issue.fields.assignee.displayName
            if issue.fields.assignee
            else 'Без исполнителя'
        )

        return {
            'URL': f"{JIRA_SERVER}/browse/{issue.key}",
            'Ключ': issue.key,
            'Задача': issue.fields.summary,
            'Исполнитель': assignee,
            'Статус': issue.fields.status.name,
            'Факторы риска': '',  # Будет заполнено позже
            'Приоритет': (
                issue.fields.priority.name
                if issue.fields.priority
                else 'Normal'
            )
        }


class ReportGenerator:
    """
    Основной класс генерации отчётов.

    Рефакторинг функции generate_report() в объектно-ориентированном стиле.
    """

    def __init__(
        self,
        project_keys: Optional[Union[str, List[str]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
        assignee_filter: Optional[Union[str, List[str]]] = None,
        issue_types: Optional[Union[str, List[str]]] = None,
        blocks: Optional[List[str]] = None,
        verbose: bool = False,
        extra_verbose: bool = False,
        closed_status_ids: Optional[List[str]] = None,
        include_risk_zone: bool = True
    ):
        self.project_keys = normalize_filter(project_keys, upper=True)
        self.start_date_input = start_date
        self.end_date_input = end_date
        self.days = days
        self.assignee_filter = normalize_filter(assignee_filter)
        self.issue_types = normalize_filter(issue_types)
        self.blocks = blocks if blocks else list(REPORT_BLOCKS.keys())
        self.verbose = verbose
        self.extra_verbose = extra_verbose
        self.closed_status_ids = closed_status_ids or CLOSED_STATUS_IDS
        self.include_risk_zone = include_risk_zone

        # Компоненты
        self.issue_extractor = IssueDataExtractor(extra_verbose)
        self.block_generator = ReportBlockGenerator('summary', extra_verbose)
        self.risk_analyzer = RiskZoneAnalyzer()
        self.issue_validator = IssueValidator(closed_status_ids=self.closed_status_ids)

        # Данные
        self.jira = None
        self.projects_map = {}
        self.all_issues_data = []
        self.summary_data = []
        self.issues_with_problems = []
        self.start_date_obj = None
        self.end_date_obj = None
        self.issues_end_obj = None

    def generate(self) -> Dict[str, Any]:
        """
        Генерирует отчёт по задачам Jira.

        Returns:
            Dict с данными отчёта
        """
        self._initialize()
        self._fetch_projects()
        self._process_projects()
        return self._build_result()

    def _initialize(self):
        """Инициализация: даты, статусы, подключение."""
        # Авто-определение ID статуса "Закрыт"
        if not self.closed_status_ids or self.closed_status_ids[0] == '':
            self.closed_status_ids = get_closed_status_ids()

        # Обработка дат
        if self.start_date_input:
            self.start_date_obj = datetime.strptime(self.start_date_input, '%Y-%m-%d')
        else:
            self.start_date_obj = get_default_start_date()

        start_date_str = self.start_date_obj.strftime('%Y-%m-%d')

        if self.end_date_input:
            self.end_date_obj = datetime.strptime(self.end_date_input, '%Y-%m-%d')
            self.issues_end_obj = self.end_date_obj + relativedelta(months=2)
        elif self.days > 0:
            self.end_date_obj = self.start_date_obj + timedelta(days=self.days - 1)
            self.issues_end_obj = (
                self.start_date_obj
                + timedelta(days=self.days)
                + relativedelta(months=2)
            )
        else:
            self.end_date_obj = datetime.now()
            self.issues_end_obj = self.end_date_obj

        self.start_date_str = self.start_date_obj.strftime('%Y-%m-%d')
        self.end_date_str = self.end_date_obj.strftime('%Y-%m-%d')
        self.issues_end_str = self.issues_end_obj.strftime('%Y-%m-%d')

        # Подключение к Jira
        self.jira = get_jira_connection()

    def _fetch_projects(self):
        """Получает список проектов."""
        if self.project_keys and len(self.project_keys) > 0:
            for proj_key in self.project_keys:
                try:
                    # Пробуем использовать кэширующую функцию
                    try:
                        from web.app import get_project_cached
                        proj = get_project_cached(self.jira, proj_key)
                    except ImportError:
                        proj = self.jira.project(proj_key)

                    if proj:
                        self.projects_map[proj.key] = proj.name
                except Exception:
                    logger.warning(f"Проект {proj_key} не найден")
        else:
            all_projects = self.jira.projects()
            for proj in all_projects:
                if proj.key in EXCLUDED_PROJECTS:
                    continue
                if hasattr(proj, 'archived') and proj.archived:
                    continue
                self.projects_map[proj.key] = proj.name

    def _process_projects(self):
        """Обрабатывает все проекты."""
        for proj_key in self.projects_map:
            self._process_single_project(proj_key)

    def _process_single_project(self, proj_key: str):
        """Обрабатывает один проект."""
        try:
            proj_key = sanitize_jql_identifier(proj_key)
        except ValueError as e:
            logger.warning(f"Пропущен недопустимый ключ проекта: {e}")
            return

        proj_name = self.projects_map.get(proj_key, proj_key)

        # Формируем JQL запросы
        jql_normal = self._build_jql_normal(proj_key)
        jql_issues = self._build_jql_issues(proj_key)

        # Получаем задачи
        issues_normal = search_all_issues(
            self.jira,
            jql_normal,
            fields='summary, assignee, timespent, timeoriginalestimate, resolutiondate, issuetype, duedate, status, created, updated, priority',
            expand='changelog'
        )

        issues_all = search_all_issues(
            self.jira,
            jql_issues,
            fields='summary, assignee, timespent, timeoriginalestimate, resolutiondate, issuetype, duedate, status, created, updated, creator, priority',
            expand='changelog'
        )

        # Обрабатываем задачи
        self._process_normal_issues(issues_normal, proj_name, proj_key)
        self._process_issues_data(issues_all, issues_normal, proj_name, proj_key)

    def _build_jql_normal(self, proj_key: str) -> str:
        """Строит JQL для обычных отчётов."""
        start_date_safe = sanitize_jql_string_literal(self.start_date_str)
        end_date_safe = sanitize_jql_string_literal(self.end_date_str)

        issue_type_filter = self._build_issue_type_filter()
        assignee_filter_jql = self._build_assignee_filter()

        if self.days > 0:
            return (
                f"project = {proj_key} "
                f"AND duedate >= '{start_date_safe}' "
                f"AND duedate <= '{end_date_safe}' "
                f"AND duedate is not null"
                f"{issue_type_filter}"
                f"{assignee_filter_jql} "
                f"ORDER BY duedate ASC"
            )
        else:
            return (
                f"project = {proj_key} "
                f"AND duedate is not null"
                f"{issue_type_filter}"
                f"{assignee_filter_jql} "
                f"ORDER BY duedate DESC"
            )

    def _build_jql_issues(self, proj_key: str) -> str:
        """Строит JQL для проблемных задач."""
        start_date_safe = sanitize_jql_string_literal(self.start_date_str)
        issues_end_safe = sanitize_jql_string_literal(self.issues_end_str)

        issue_type_filter = self._build_issue_type_filter()
        assignee_filter_jql = self._build_assignee_filter()

        if self.days > 0:
            return (
                f"project = {proj_key} "
                f"AND created >= '{start_date_safe}' "
                f"AND created <= '{issues_end_safe}'"
                f"{issue_type_filter}"
                f"{assignee_filter_jql} "
                f"ORDER BY created ASC"
            )
        else:
            return (
                f"project = {proj_key} "
                f"AND created is not null"
                f"{issue_type_filter}"
                f"{assignee_filter_jql} "
                f"ORDER BY created DESC"
            )

    def _build_issue_type_filter(self) -> str:
        """Строит фильтр по типам задач."""
        if self.issue_types and len(self.issue_types) > 0:
            sanitized_types = []
            for t in self.issue_types:
                try:
                    sanitized_types.append(sanitize_jql_identifier(t))
                except ValueError as e:
                    logger.warning(f"Пропущен недопустимый тип задачи '{t}': {e}")
            if sanitized_types:
                return ' AND issuetype IN (' + ','.join(sanitized_types) + ')'
        return ''

    def _build_assignee_filter(self) -> str:
        """Строит фильтр по исполнителям."""
        if self.assignee_filter and len(self.assignee_filter) > 0:
            sanitized_assignees = []
            for a in self.assignee_filter:
                try:
                    sanitized_assignees.append(sanitize_jql_identifier(a))
                except ValueError as e:
                    logger.warning(f"Пропущен недопустимый пользователь '{a}': {e}")
            if sanitized_assignees:
                return ' AND assignee IN (' + ','.join(sanitized_assignees) + ')'
        return ''

    def _process_normal_issues(self, issues_normal: List, proj_name: str, proj_key: str):
        """Обрабатывает обычные задачи проекта."""
        proj_spent = 0.0
        proj_estimated = 0.0
        proj_correct = 0
        proj_issues = 0

        for issue in issues_normal:
            problems = self.issue_validator.validate(issue, proj_key)
            issue_data = self.issue_extractor.extract(
                issue,
                proj_name,
                problems
            )

            self.all_issues_data.append(issue_data)

            if not issue_data['Проблемы']:
                proj_spent += issue_data['Факт (ч)']
                proj_estimated += issue_data['Оценка (ч)']
                proj_correct += 1
            else:
                proj_issues += 1

        if proj_correct > 0 or proj_issues > 0:
            summary_row = self.block_generator.generate_summary(
                proj_name,
                proj_correct,
                proj_issues,
                proj_estimated,
                proj_spent,
                issues_normal
            )
            self.summary_data.append(summary_row)

    def _process_issues_data(
        self,
        issues_all: List,
        issues_normal: List,
        proj_name: str,
        proj_key: str
    ):
        """Обрабатывает проблемные задачи."""
        for issue in issues_all:
            problems = self.issue_validator.validate(issue, proj_key)
            if problems:
                assignee = (
                    issue.fields.assignee.displayName
                    if issue.fields.assignee
                    else 'Без исполнителя'
                )
                duedate = issue.fields.duedate[:10] if issue.fields.duedate else '-'
                created = issue.fields.created[:10] if issue.fields.created else '-'

                issue_row = self.block_generator.generate_issue_row(
                    issue,
                    assignee,
                    created,
                    duedate,
                    proj_name
                )
                issue_row['Проблемы'] = ', '.join(problems)
                self.issues_with_problems.append(issue_row)

    def _build_result(self) -> Dict[str, Any]:
        """Строит итоговый результат отчёта."""
        df_detail = pd.DataFrame(self.all_issues_data)
        df_summary = pd.DataFrame(self.summary_data)
        df_issues = pd.DataFrame(self.issues_with_problems)

        # Сортировка и группировка
        self._sort_and_group(df_detail, df_summary)

        # Risk Zone
        if self.include_risk_zone:
            self._add_risk_zone(df_detail)

        result = {
            'period': f"{self.start_date_str} — {self.end_date_str}",
            'blocks': self.blocks,
            'total_projects': len(df_summary),
            'total_tasks': len(df_detail),
            'total_correct': (
                len(df_detail[df_detail['Проблемы'] == ''])
                if not df_detail.empty
                else 0
            ),
            'total_issues': len(df_issues),
            'total_spent': (
                df_summary['Факт (ч)'].sum()
                if not df_summary.empty
                else 0
            ),
            'total_estimated': (
                df_summary['Оценка (ч)'].sum()
                if not df_summary.empty
                else 0
            ),
        }

        # Добавляем блоки
        block_mapping = {
            'summary': df_summary,
            'assignees': getattr(self, 'df_assignees', pd.DataFrame()),
            'detail': df_detail,
            'issues': df_issues,
            'internal': getattr(self, 'df_internal', pd.DataFrame()),
            'risk_zone': getattr(self, 'df_risk_zone', pd.DataFrame())
        }

        for block_name, df in block_mapping.items():
            if block_name in self.blocks and not df.empty:
                result[block_name] = self._filter_columns(df, block_name)

        return result

    def _sort_and_group(self, df_detail: pd.DataFrame, df_summary: pd.DataFrame):
        """Сортирует и группирует данные."""
        if not df_detail.empty:
            df_detail = df_detail.sort_values(
                by=['Тип', 'Проект', 'Дата решения'],
                ascending=[True, True, True]
            )

            # Группировка по исполнителям
            df_with_assignee = df_detail[
                ~df_detail['Исполнитель'].str.contains('Без исполнителя', na=False)
            ]

            if not df_with_assignee.empty:
                self.df_assignees = self._group_by_assignee(df_with_assignee)
            else:
                self.df_assignees = pd.DataFrame()
        else:
            self.df_assignees = pd.DataFrame()

        # Внутренние проекты
        if 'internal' in self.blocks:
            self.df_internal = self._fetch_internal_projects()
        else:
            self.df_internal = pd.DataFrame()

    def _group_by_assignee(self, df: pd.DataFrame) -> pd.DataFrame:
        """Группирует данные по исполнителям."""
        df_assignees = df.groupby('Исполнитель').agg(
            tasks_count=('Ключ', 'count'),
            correct_count=('Проблемы', lambda x: (x == '').sum()),
            issues_count=('Проблемы', lambda x: (x != '').sum()),
            fact_sum=('Факт (ч)', 'sum'),
            estimate_sum=('Оценка (ч)', 'sum')
        ).reset_index()

        df_assignees = df_assignees.rename(columns={
            'tasks_count': 'Задач',
            'correct_count': 'Корректных',
            'issues_count': 'С ошибками',
            'fact_sum': 'Факт (ч)',
            'estimate_sum': 'Оценка (ч)'
        })

        df_assignees['Отклонение'] = (
            df_assignees['Оценка (ч)'] - df_assignees['Факт (ч)']
        )
        df_assignees = df_assignees.round(2)
        df_assignees = df_assignees.sort_values(by='Факт (ч)', ascending=False)
        
        # В extra_verbose режиме добавляем [field_name] к числовым полям
        if self.extra_verbose:
            df_assignees['Факт (ч)'] = df_assignees['Факт (ч)'].apply(lambda x: f"{x} [timespent]")
            df_assignees['Оценка (ч)'] = df_assignees['Оценка (ч)'].apply(lambda x: f"{x} [timeoriginalestimate]")

        return df_assignees

    def _fetch_internal_projects(self) -> pd.DataFrame:
        """Получает задачи из внутренних проектов."""
        from core.config import INTERNAL_PROJECTS

        if not INTERNAL_PROJECTS:
            return pd.DataFrame()

        internal_issues_data = []
        for internal_proj_key in INTERNAL_PROJECTS:
            if internal_proj_key not in self.projects_map:
                continue

            internal_proj_name = self.projects_map[internal_proj_key]
            jql_internal = (
                f"project = {internal_proj_key} "
                f"AND created >= '{self.start_date_str}' "
                f"AND created <= '{self.end_date_str}' "
                f"ORDER BY created ASC"
            )

            try:
                internal_issues = self.jira.search_issues(
                    jql_internal,
                    maxResults=False,
                    fields='summary, assignee, timespent, timeoriginalestimate, resolutiondate, issuetype, duedate, status, created'
                )

                for issue in internal_issues:
                    spent = convert_seconds_to_hours(issue.fields.timespent)
                    estimated = convert_seconds_to_hours(issue.fields.timeoriginalestimate)
                    issue_type = (
                        issue.fields.issuetype.name
                        if issue.fields.issuetype
                        else 'Задача'
                    )
                    assignee = (
                        issue.fields.assignee.displayName
                        if issue.fields.assignee
                        else 'Без исполнителя'
                    )
                    status_name = (
                        issue.fields.status.name
                        if issue.fields.status
                        else '-'
                    )
                    created = (
                        issue.fields.created[:10]
                        if issue.fields.created
                        else '-'
                    )

                    # Формируем данные с ID при extra_verbose
                    proj_display = internal_proj_name
                    assignee_display = assignee
                    status_display = status_name
                    issue_type_display = issue_type
                    spent_display = str(spent)
                    estimated_display = str(estimated)
                    created_display = created
                    
                    if self.extra_verbose:
                        # URL с иконкой 🔍
                        issue_url = f"{JIRA_SERVER}/browse/{issue.key} 🔍"
                        # Проект с ID
                        proj_obj = getattr(issue.fields, 'project', None)
                        if proj_obj and hasattr(proj_obj, 'id'):
                            proj_display = f"{internal_proj_name} [{proj_obj.id}]"
                        # Исполнитель с ID
                        if issue.fields.assignee and hasattr(issue.fields.assignee, 'id'):
                            assignee_display = f"{assignee} [{issue.fields.assignee.id}]"
                        # Статус с ID
                        if issue.fields.status and hasattr(issue.fields.status, 'id'):
                            status_display = f"{status_name} [{issue.fields.status.id}]"
                        # Тип с ID
                        if issue.fields.issuetype and hasattr(issue.fields.issuetype, 'id'):
                            issue_type_display = f"{issue_type} [{issue.fields.issuetype.id}]"
                        # Ключ с ID
                        key_display = f"{issue.key} [id]"
                        # Факт с [timespent]
                        spent_display = f"{spent} [timespent]"
                        # Оценка с [timeoriginalestimate]
                        estimated_display = f"{estimated} [timeoriginalestimate]"
                        # Дата создания с [created]
                        if created != '-':
                            created_display = f"{created} [created]"
                    else:
                        issue_url = f"{JIRA_SERVER}/browse/{issue.key}"
                        key_display = issue.key

                    row = {
                        'URL': issue_url,
                        'Проект': proj_display,
                        'Ключ': key_display,
                        'Тип': issue_type_display,
                        'Задача': issue.fields.summary,
                        'Исполнитель': assignee_display,
                        'Статус': status_display,
                        'Дата создания': created_display,
                        'Факт (ч)': spent_display,
                        'Оценка (ч)': estimated_display
                    }
                    
                    internal_issues_data.append(row)
            except Exception as e:
                logger.warning(
                    f"Не удалось получить задачи из проекта {internal_proj_key}: {e}"
                )

        if internal_issues_data:
            df_internal = pd.DataFrame(internal_issues_data)
            return df_internal.sort_values(by='Дата создания', ascending=True)

        return pd.DataFrame()

    def _add_risk_zone(self, df_detail: pd.DataFrame):
        """Добавляет блок Risk Zone.
        
        Risk Zone данные обрабатываются в _process_normal_issues,
        этот метод существует для совместимости структуры.
        """
        pass

    def _filter_columns(self, df: pd.DataFrame, block_name: str) -> pd.DataFrame:
        """Фильтрует колонки для блока."""
        cols = get_column_order(block_name, self.extra_verbose)
        available_cols = [c for c in cols if c in df.columns]
        return df[available_cols]


def generate_report(
    project_keys: Optional[Union[str, List[str]]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 30,
    assignee_filter: Optional[Union[str, List[str]]] = None,
    issue_types: Optional[Union[str, List[str]]] = None,
    blocks: Optional[List[str]] = None,
    verbose: bool = False,
    extra_verbose: bool = False,
    closed_status_ids: Optional[List[str]] = None,
    include_risk_zone: bool = True
) -> Dict[str, Any]:
    """
    Генерирует отчёт по задачам Jira (обёртка над ReportGenerator).

    Args:
        project_keys: Ключ проекта или список проектов
        start_date: Дата начала в формате ГГГГ-ММ-ДД
        end_date: Дата окончания в формате ГГГГ-ММ-ДД
        days: Количество дней для отчёта
        assignee_filter: Фильтр по исполнителю
        issue_types: Фильтр по типам задач
        blocks: Список блоков отчёта
        verbose: Режим отладки
        extra_verbose: Показывать ID объектов
        closed_status_ids: Список ID закрытых статусов
        include_risk_zone: Включить блок Risk Zone

    Returns:
        Dict с данными отчёта
    """
    generator = ReportGenerator(
        project_keys=project_keys,
        start_date=start_date,
        end_date=end_date,
        days=days,
        assignee_filter=assignee_filter,
        issue_types=issue_types,
        blocks=blocks,
        verbose=verbose,
        extra_verbose=extra_verbose,
        closed_status_ids=closed_status_ids,
        include_risk_zone=include_risk_zone
    )
    return generator.generate()
