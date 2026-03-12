# -*- coding: utf-8 -*-
"""
Middleware компоненты для Flask приложения.

Rate limiting, обработка ошибок, логирование.
"""
from functools import wraps
from flask import request, jsonify, g, Response
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Callable, Any
from collections import OrderedDict
import logging
import time
from core.config import (
    API_RATE_LIMIT_MAX_REQUESTS,
    API_RATE_LIMIT_WINDOW_SECONDS,
    API_RATE_LIMIT_MAX_CLIENTS
)

logger = logging.getLogger(__name__)


# =============================================
# RATE LIMITING
# =============================================

class RateLimiter:
    """
    Простой rate limiter для API endpoints.

    Хранит информацию о запросах в памяти.
    Для production использовать Redis.

    Usage:
        rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

        @app.route('/api/report')
        @rate_limiter.limit()
        def api_report():
            ...
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        max_clients: int = 10000
    ):
        """
        Инициализирует rate limiter.

        Args:
            max_requests: Максимум запросов за окно
            window_seconds: Размер окна в секундах
            max_clients: Максимальное количество клиентов в памяти
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._requests: OrderedDict[str, list] = OrderedDict()

    def _get_client_key(self) -> str:
        """Получает ключ клиента (IP + User-Agent)."""
        ip = request.remote_addr or 'unknown'
        user_agent = request.headers.get('User-Agent', 'unknown')
        return f"{ip}:{user_agent}"

    def _clean_old_requests(self, client_key: str) -> None:
        """Удаляет старые запросы за пределами окна."""
        if client_key not in self._requests:
            return

        cutoff = datetime.now() - timedelta(seconds=self.window_seconds)
        self._requests[client_key] = [
            req_time for req_time in self._requests[client_key]
            if req_time > cutoff
        ]
        
        # Если запросов не осталось, удаляем клиента
        if not self._requests[client_key]:
            del self._requests[client_key]

    def _evict_old_clients(self) -> None:
        """
        Удаляет старых клиентов при превышении лимита.
        
        Использует LRU-стратегию: удаляет клиентов, у которых
        давно не было запросов.
        """
        while len(self._requests) > self.max_clients:
            # Удаляем самого старого клиента (первый в OrderedDict)
            self._requests.popitem(last=False)

    def is_allowed(self) -> Tuple[bool, int]:
        """
        Проверяет, разрешён ли запрос.

        Returns:
            Tuple[bool, int]: (разрешён, осталось запросов)
        """
        client_key = self._get_client_key()
        self._clean_old_requests(client_key)
        
        # Очищаем старых клиентов при превышении лимита
        self._evict_old_clients()

        current_requests = len(self._requests.get(client_key, []))
        remaining = self.max_requests - current_requests

        if current_requests >= self.max_requests:
            return False, 0

        # Записываем текущий запрос
        if client_key not in self._requests:
            self._requests[client_key] = []
        self._requests[client_key].append(datetime.now())
        
        # Перемещаем клиента в конец (LRU)
        self._requests.move_to_end(client_key)

        return True, remaining - 1

    def limit(self) -> Callable:
        """Декоратор для ограничения запросов."""
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                allowed, remaining = self.is_allowed()

                if not allowed:
                    logger.warning(
                        f"Rate limit exceeded for {self._get_client_key()}"
                    )
                    return jsonify({
                        'success': False,
                        'error': 'Превышен лимит запросов. Попробуйте позже.',
                        'retry_after': self.window_seconds
                    }), 429

                # Добавляем заголовок с оставшимися запросами
                response = f(*args, **kwargs)
                if isinstance(response, tuple):
                    resp = response[0]
                    status = response[1] if len(response) > 1 else 200
                else:
                    resp = response
                    status = 200

                if hasattr(resp, 'headers'):
                    resp.headers['X-RateLimit-Remaining'] = str(remaining)
                    resp.headers['X-RateLimit-Limit'] = str(self.max_requests)

                return response
            return wrapped
        return decorator

    def get_stats(self) -> Dict:
        """Возвращает статистику rate limiter."""
        return {
            'max_requests': self.max_requests,
            'window_seconds': self.window_seconds,
            'active_clients': len(self._requests)
        }


# Глобальный rate limiter для API
api_rate_limiter = RateLimiter(
    max_requests=API_RATE_LIMIT_MAX_REQUESTS,
    window_seconds=API_RATE_LIMIT_WINDOW_SECONDS,
    max_clients=API_RATE_LIMIT_MAX_CLIENTS
)


# =============================================
# ОБРАБОТКА ОШИБОК
# =============================================

class APIError(Exception):
    """Базовый класс для API ошибок."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        payload: Optional[Dict[str, Any]] = None
    ):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self) -> Dict[str, Any]:
        result = {'success': False, 'error': self.message}
        if self.payload:
            result.update(self.payload)
        return result


class JiraConnectionError(APIError):
    """Ошибка подключения к Jira."""

    def __init__(self, message: str = "Ошибка подключения к Jira"):
        super().__init__(message, status_code=503)


class ValidationError(APIError):
    """Ошибка валидации данных."""

    def __init__(self, message: str, field: Optional[str] = None):
        payload = {'field': field} if field else None
        super().__init__(message, status_code=400, payload=payload)


class NotFoundError(APIError):
    """Ресурс не найден."""

    def __init__(self, message: str = "Ресурс не найден"):
        super().__init__(message, status_code=404)


class RateLimitError(APIError):
    """Превышен лимит запросов."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            "Превышен лимит запросов. Попробуйте позже.",
            status_code=429,
            payload={'retry_after': retry_after}
        )


def handle_api_errors(f: Callable) -> Callable:
    """
    Декоратор для обработки стандартных API ошибок.

    Usage:
        @app.route('/api/report')
        @handle_api_errors
        def api_report():
            ...
    """
    @wraps(f)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except APIError as e:
            logger.warning(f"API Error: {e.message}", exc_info=False)
            return jsonify(e.to_dict()), e.status_code
        except Exception as e:
            logger.error(f"Unhandled error: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Внутренняя ошибка сервера',
                'type': type(e).__name__
            }), 500
    return wrapped


# =============================================
# ВРЕМЯ ОТВЕТА (REQUEST TIMING)
# =============================================

def before_request_timing() -> None:
    """Замеряет время начала запроса."""
    g.start_time = time.time()


def after_request_timing(response: Response) -> Response:
    """Добавляет заголовок со временем ответа."""
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        response.headers['X-Response-Time'] = f"{elapsed:.3f}s"
    return response


# =============================================
# ЛОГИРОВАНИЕ ЗАПРОСОВ
# =============================================

def log_request_info() -> None:
    """Логирует информацию о запросе."""
    if request.path.startswith('/api/'):
        logger.debug(
            f"API Request: {request.method} {request.path} "
            f"from {request.remote_addr}"
        )


# =============================================
# ИНИЦИАЛИЗАЦИЯ MIDDLEWARE
# =============================================

def init_middleware(app: Any) -> None:
    """
    Регистрирует middleware в Flask-приложении.

    Args:
        app: Flask-приложение
    """
    app.before_request(before_request_timing)
    app.after_request(after_request_timing)
    app.before_request(log_request_info)

    logger.debug("✅ Middleware инициализирован")


# =============================================
# ЭКСПОРТ
# =============================================

__all__ = [
    'RateLimiter',
    'api_rate_limiter',
    'APIError',
    'JiraConnectionError',
    'ValidationError',
    'NotFoundError',
    'RateLimitError',
    'handle_api_errors',
    'init_middleware',
]
