"""
Валидаторы для API endpoints.
Используется для проверки входных данных запросов.
"""
from functools import wraps
from typing import Optional, List, Callable, Any, Dict
from flask import request, jsonify, current_app
from datetime import datetime, timedelta
import re


class ValidationError(Exception):
    """Исключение валидации."""
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class Validator:
    """Базовый класс валидатора."""

    @staticmethod
    def validate_date_format(date_str: str, field_name: str = 'date') -> datetime:
        """
        Проверяет формат даты (ГГГГ-ММ-ДД).

        Args:
            date_str: Строка даты
            field_name: Имя поля для ошибки

        Returns:
            datetime объект

        Raises:
            ValidationError: Если формат неверный
        """
        if not date_str:
            raise ValidationError(f"{field_name} не указана", field_name)

        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise ValidationError(
                f"Неверный формат {field_name}. Ожидается ГГГГ-ММ-ДД",
                field_name
            )

    @staticmethod
    def validate_date_range(
        start_date: datetime,
        end_date: datetime,
        max_days: int = 365
    ) -> None:
        """
        Проверяет диапазон дат.

        Args:
            start_date: Дата начала
            end_date: Дата окончания
            max_days: Максимальное количество дней

        Raises:
            ValidationError: Если диапазон неверный
        """
        if end_date < start_date:
            raise ValidationError(
                "Дата окончания не может быть раньше даты начала",
                'end_date'
            )

        if (end_date - start_date).days > max_days:
            raise ValidationError(
                f"Период не может превышать {max_days} дней",
                'date_range'
            )

    @staticmethod
    def validate_days(days: int, min_days: int = 0, max_days: int = 365) -> int:
        """
        Проверяет значение дней.

        Args:
            days: Количество дней
            min_days: Минимальное значение
            max_days: Максимальное значение

        Returns:
            Проверенное значение дней

        Raises:
            ValidationError: Если значение неверное
        """
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ValidationError("days должно быть числом", 'days')

        if days < min_days:
            raise ValidationError(
                f"days не может быть меньше {min_days}",
                'days'
            )

        if days > max_days:
            raise ValidationError(
                f"days не может превышать {max_days}",
                'days'
            )

        return days

    @staticmethod
    def validate_project_key(key: str) -> str:
        """
        Проверяет ключ проекта.

        Args:
            key: Ключ проекта

        Returns:
            Проверенный ключ

        Raises:
            ValidationError: Если ключ неверный
        """
        if not key:
            raise ValidationError("Ключ проекта не указан", 'project')

        # Ключ проекта: буквы, цифры, дефис
        if not re.match(r'^[A-Z][A-Z0-9\-]*$', key.upper()):
            raise ValidationError(
                "Неверный формат ключа проекта",
                'project'
            )

        return key.upper()

    @staticmethod
    def validate_project_keys(keys: List[str]) -> List[str]:
        """
        Проверяет список ключей проектов.

        Args:
            keys: Список ключей

        Returns:
            Проверенный список ключей

        Raises:
            ValidationError: Если ключи неверные
        """
        if not keys:
            return []

        validated = []
        for key in keys:
            try:
                validated.append(Validator.validate_project_key(key))
            except ValidationError:
                raise ValidationError(
                    f"Неверный ключ проекта: {key}",
                    'projects'
                )

        return validated

    @staticmethod
    def validate_username(username: str) -> str:
        """
        Проверяет имя пользователя.

        Args:
            username: Имя пользователя

        Returns:
            Проверенное имя

        Raises:
            ValidationError: Если имя неверное
        """
        if not username:
            raise ValidationError("Имя пользователя не указано", 'username')

        # Разрешённые символы: буквы, цифры, точка, подчёркивание, @, дефис
        if not re.match(r'^[a-zA-Z0-9_\-\.@]+$', username):
            raise ValidationError(
                "Неверный формат имени пользователя",
                'username'
            )

        return username

    @staticmethod
    def validate_usernames(usernames: List[str]) -> List[str]:
        """
        Проверяет список имён пользователей.

        Args:
            usernames: Список имён

        Returns:
            Проверенный список имён

        Raises:
            ValidationError: Если имена неверные
        """
        if not usernames:
            return []

        validated = []
        for username in usernames:
            try:
                validated.append(Validator.validate_username(username))
            except ValidationError:
                raise ValidationError(
                    f"Неверное имя пользователя: {username}",
                    'assignees'
                )

        return validated

    @staticmethod
    def validate_issue_type(type_name: str) -> str:
        """
        Проверяет тип задачи.

        Args:
            type_name: Название типа

        Returns:
            Проверенное название

        Raises:
            ValidationError: Если тип неверный
        """
        if not type_name:
            raise ValidationError("Тип задачи не указан", 'issue_type')

        # Разрешённые символы: буквы, цифры, пробел, дефис
        if not re.match(r'^[A-Za-zА-Яа-я0-9\s\-]+$', type_name):
            raise ValidationError(
                "Неверный формат типа задачи",
                'issue_type'
            )

        return type_name

    @staticmethod
    def validate_issue_types(types: List[str]) -> List[str]:
        """
        Проверяет список типов задач.

        Args:
            types: Список типов

        Returns:
            Проверенный список типов

        Raises:
            ValidationError: Если типы неверные
        """
        if not types:
            return []

        validated = []
        for type_name in types:
            try:
                validated.append(Validator.validate_issue_type(type_name))
            except ValidationError:
                raise ValidationError(
                    f"Неверный тип задачи: {type_name}",
                    'issue_types'
                )

        return validated

    @staticmethod
    def validate_blocks(blocks: List[str], allowed_blocks: List[str]) -> List[str]:
        """
        Проверяет список блоков отчёта.

        Args:
            blocks: Запрошенные блоки
            allowed_blocks: Разрешённые блоки

        Returns:
            Проверенный список блоков

        Raises:
            ValidationError: Если блоки неверные
        """
        if not blocks:
            return allowed_blocks

        invalid = [b for b in blocks if b not in allowed_blocks]
        if invalid:
            raise ValidationError(
                f"Неверные блоки: {', '.join(invalid)}",
                'blocks'
            )

        return blocks

    @staticmethod
    def validate_task_key(key: str) -> str:
        """
        Проверяет ключ задачи.

        Args:
            key: Ключ задачи (например, WEB-123)

        Returns:
            Проверенный ключ

        Raises:
            ValidationError: Если ключ неверный
        """
        if not key:
            raise ValidationError("Ключ задачи не указан", 'task_key')

        # Формат: КЛЮЧ-123
        if not re.match(r'^[A-Z][A-Z0-9\-]*-\d+$', key.upper()):
            raise ValidationError(
                "Неверный формат ключа задачи (ожидалось KEY-123)",
                'task_key'
            )

        return key.upper()

    @staticmethod
    def validate_task_keys(keys: List[str]) -> List[str]:
        """
        Проверяет список ключей задач.

        Args:
            keys: Список ключей

        Returns:
            Проверенный список ключей

        Raises:
            ValidationError: Если ключи неверные
        """
        if not keys:
            raise ValidationError("task_keys required", 'task_keys')

        if len(keys) > 50:
            raise ValidationError(
                "Максимум 50 задач за запрос",
                'task_keys'
            )

        validated = []
        for key in keys:
            try:
                validated.append(Validator.validate_task_key(key))
            except ValidationError:
                raise ValidationError(
                    f"Неверный ключ задачи: {key}",
                    'task_keys'
                )

        return validated


# =============================================
# ДЕКОРАТОРЫ ВАЛИДАЦИИ
# =============================================

def validate_report_request(allowed_blocks: List[str], max_days: int = 365):
    """
    Декоратор валидации запроса отчёта.

    Usage:
        @app.route('/api/report', methods=['POST'])
        @validate_report_request(REPORT_BLOCKS, max_days=365)
        def api_report():
            data = request.get_json()
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs) -> Any:
            try:
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

                # Валидация дат
                start_date = data.get('start_date', '').strip() or None
                end_date = data.get('end_date', '').strip() or None
                days = data.get('days', 0)

                if start_date:
                    start_dt = Validator.validate_date_format(start_date, 'start_date')
                else:
                    start_dt = datetime.now() - timedelta(days=30)

                if end_date:
                    end_dt = Validator.validate_date_format(end_date, 'end_date')
                    Validator.validate_date_range(start_dt, end_dt, max_days)
                else:
                    days = Validator.validate_days(days, 0, max_days)

                # Валидация проектов
                projects_raw = data.get('projects', []) or data.get('project', '').strip() or None
                if projects_raw:
                    if isinstance(projects_raw, str):
                        projects_raw = [projects_raw]
                    Validator.validate_project_keys(projects_raw)

                # Валидация исполнителей
                assignees_raw = data.get('assignees', []) or data.get('assignee', '').strip() or None
                if assignees_raw:
                    if isinstance(assignees_raw, str):
                        assignees_raw = [assignees_raw]
                    Validator.validate_usernames(assignees_raw)

                # Валидация типов задач
                issue_types_raw = data.get('issue_types', []) or data.get('issue_type', '').strip() or None
                if issue_types_raw:
                    if isinstance(issue_types_raw, str):
                        issue_types_raw = [issue_types_raw]
                    Validator.validate_issue_types(issue_types_raw)

                # Валидация блоков
                blocks = data.get('blocks', None)
                if blocks:
                    Validator.validate_blocks(blocks, allowed_blocks)

                # Валидация extra_verbose
                extra_verbose = data.get('extra_verbose', False)
                if not isinstance(extra_verbose, bool):
                    raise ValidationError("extra_verbose должно быть boolean", 'extra_verbose')

                return f(*args, **kwargs)

            except ValidationError as e:
                return jsonify({
                    'success': False,
                    'error': e.message,
                    'field': e.field
                }), 400
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        return decorated
    return decorator


def validate_task_info_request():
    """
    Декоратор валидации запроса информации о задаче.

    Usage:
        @app.route('/api/task-info', methods=['POST'])
        @validate_task_info_request
        def api_task_info():
            data = request.get_json()
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs) -> Any:
            try:
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

                task_key = data.get('task_key', '')
                Validator.validate_task_key(task_key)

                return f(*args, **kwargs)

            except ValidationError as e:
                return jsonify({
                    'success': False,
                    'error': e.message,
                    'field': e.field
                }), 400
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        return decorated
    return decorator


def validate_task_info_batch_request():
    """
    Декоратор валидации batch-запроса информации о задачах.

    Usage:
        @app.route('/api/task-info-batch', methods=['POST'])
        @validate_task_info_batch_request
        def api_task_info_batch():
            data = request.get_json()
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs) -> Any:
            try:
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

                task_keys = data.get('task_keys', [])
                Validator.validate_task_keys(task_keys)

                return f(*args, **kwargs)

            except ValidationError as e:
                return jsonify({
                    'success': False,
                    'error': e.message,
                    'field': e.field
                }), 400
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        return decorated
    return decorator


# =============================================
# RATE LIMITING
# =============================================

class RateLimiter:
    """Простой rate limiter для защиты от DDoS."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Инициализация rate limiter.

        Args:
            max_requests: Максимум запросов в окно
            window_seconds: Размер окна в секундах
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        """
        Проверяет, разрешён ли запрос.

        Args:
            client_id: Идентификатор клиента (IP, user_id)

        Returns:
            True если запрос разрешён
        """
        import time
        current_time = time.time()

        if client_id not in self.requests:
            self.requests[client_id] = []

        # Удаляем старые запросы
        self.requests[client_id] = [
            t for t in self.requests[client_id]
            if current_time - t < self.window_seconds
        ]

        # Проверяем лимит
        if len(self.requests[client_id]) >= self.max_requests:
            return False

        # Добавляем текущий запрос
        self.requests[client_id].append(current_time)
        return True

    def get_retry_after(self, client_id: str) -> int:
        """
        Возвращает время до следующего разрешённого запроса.

        Args:
            client_id: Идентификатор клиента

        Returns:
            Время в секундах
        """
        import time
        if client_id not in self.requests:
            return 0

        current_time = time.time()
        oldest_request = min(self.requests[client_id])
        retry_after = int(self.window_seconds - (current_time - oldest_request)) + 1

        return max(1, retry_after)


# Глобальный rate limiter (100 запросов в минуту)
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """
    Декоратор rate limiting.

    Usage:
        @app.route('/api/report', methods=['POST'])
        @rate_limit(max_requests=10, window_seconds=60)
        def api_report():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs) -> Any:
            # Получаем client_id (IP адрес)
            client_id = request.remote_addr or 'unknown'

            limiter = RateLimiter(max_requests, window_seconds)

            if not limiter.is_allowed(client_id):
                retry_after = limiter.get_retry_after(client_id)
                response = jsonify({
                    'success': False,
                    'error': 'Too many requests',
                    'retry_after': retry_after
                })
                response.headers['Retry-After'] = str(retry_after)
                return response, 429

            return f(*args, **kwargs)

        return decorated
    return decorator


# =============================================
# УТИЛИТЫ
# =============================================

def get_client_ip() -> str:
    """Получает IP адрес клиента с учётом прокси."""
    if request.headers.get('X-Forwarded-For'):
        # X-Forwarded-For может содержать несколько IP
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'


def sanitize_input(value: Any) -> Any:
    """
    Санизирует входное значение.

    Args:
        value: Значение для санилизации

    Returns:
        Очищенное значение
    """
    if isinstance(value, str):
        # Удаляем потенциально опасные символы
        value = value.strip()
        value = value.replace('<', '&lt;')
        value = value.replace('>', '&gt;')
        value = value.replace('javascript:', '')
        return value
    return value
