# -*- coding: utf-8 -*-
"""
Утилиты для системы отчётности Jira.

Общие функции для санитизации, валидации и обработки данных.
"""
import re
import logging

logger = logging.getLogger(__name__)


# =============================================
# САНИТИЗАЦИЯ JQL
# =============================================

# Паттерн для безопасных идентификаторов (проекты, пользователи, типы задач)
IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z0-9_\-\.@]+$')


def sanitize_jql_identifier(value: str) -> str:
    """
    Санитизирует идентификатор для использования в JQL.

    Проверяет, что значение содержит только разрешённые символы:
    - Буквы (A-Z, a-z)
    - Цифры (0-9)
    - Дефис (-)
    - Подчёркивание (_)
    - Точка (.)
    - Собака (@)

    Args:
        value: Значение для санитизации

    Returns:
        str: Очищенное значение

    Raises:
        ValueError: Если значение содержит недопустимые символы
    """
    if not value:
        raise ValueError("Пустое значение идентификатора")

    if not IDENTIFIER_PATTERN.match(value):
        raise ValueError(
            f"Недопустимые символы в идентификаторе: {value}. "
            "Разрешены только буквы, цифры, дефис, подчёркивание, точка и @"
        )

    return value


def sanitize_jql_string_literal(value: str) -> str:
    """
    Санитизирует строковое значение для использования в JQL (внутри кавычек).

    Экранирует одиночные кавычки и удаляет потенциально опасные конструкции.

    Args:
        value: Значение для санитизации

    Returns:
        str: Очищенное и экранированное значение
    """
    if not value:
        return ''

    # Удаляем потенциально опасные SQL-подобные конструкции
    dangerous_patterns = ['--', '/*', '*/', ';', 'EXEC', 'DROP', 'DELETE', 'UPDATE']
    value_upper = value.upper()
    for pattern in dangerous_patterns:
        if pattern in value_upper:
            logger.warning(f"Обнаружена потенциально опасная конструкция в JQL: {pattern}")
            value = value.replace(pattern, '').replace(pattern.lower(), '')

    # Экранируем одиночные кавычки (заменяем ' на '')
    value = value.replace("'", "''")

    return value


# =============================================
# ЛОГИРОВАНИЕ С КОНТЕКСТОМ
# =============================================

class LogContext:
    """
    Контекст для логирования.
    
    Используется для добавления дополнительной информации в логи:
    - user: пользователь
    - project: проект
    - duration: длительность операции
    - issue_key: ключ задачи
    """
    
    def __init__(self, **kwargs):
        """
        Инициализация контекста.
        
        Args:
            **kwargs: Произвольные параметры для логирования
        """
        self._context = kwargs
    
    def set(self, key: str, value: any) -> 'LogContext':
        """
        Установить значение в контексте.
        
        Args:
            key: Ключ
            value: Значение
            
        Returns:
            self: Для цепочки вызовов
        """
        self._context[key] = value
        return self
    
    def get(self, key: str, default: any = None) -> any:
        """
        Получить значение из контекста.
        
        Args:
            key: Ключ
            default: Значение по умолчанию
            
        Returns:
            Значение из контекста
        """
        return self._context.get(key, default)
    
    def to_dict(self) -> dict:
        """
        Получить контекст как словарь.
        
        Returns:
            dict: Словарь с контекстом
        """
        return self._context.copy()
    
    def clear(self) -> None:
        """Очистить контекст."""
        self._context.clear()


def format_log_message(
    message: str,
    context: Optional[LogContext] = None,
    **kwargs
) -> str:
    """
    Форматирует сообщение лога с контекстом.
    
    Args:
        message: Основное сообщение
        context: Объект контекста (опционально)
        **kwargs: Дополнительные параметры
        
    Returns:
        str: Отформатированное сообщение
        
    Пример:
        >>> ctx = LogContext().set('user', 'ivan').set('project', 'WEB')
        >>> format_log_message('Отчёт сгенерирован', context=ctx)
        'Отчёт сгенерирован [user=ivan, project=WEB]'
    """
    parts = [message]
    
    # Собираем контекст
    ctx_dict = {}
    if context:
        ctx_dict.update(context.to_dict())
    ctx_dict.update(kwargs)
    
    # Добавляем контекст в сообщение
    if ctx_dict:
        ctx_parts = []
        if 'duration' in ctx_dict:
            ctx_parts.append(f"duration={ctx_dict['duration']:.2f}s")
            del ctx_dict['duration']
        
        for key, value in ctx_dict.items():
            if value is not None:
                ctx_parts.append(f"{key}={value}")
        
        if ctx_parts:
            parts.append(f"[{', '.join(ctx_parts)}]")
    
    return ' '.join(parts)


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    context: Optional[LogContext] = None,
    **kwargs
) -> None:
    """
    Логирует сообщение с контекстом.
    
    Args:
        logger: Объект logger
        level: Уровень лога ('debug', 'info', 'warning', 'error')
        message: Сообщение
        context: Объект контекста (опционально)
        **kwargs: Дополнительные параметры
    """
    formatted_message = format_log_message(message, context, **kwargs)
    
    log_func = getattr(logger, level, logger.info)
    log_func(formatted_message)


# Функции для замера времени
class Timer:
    """Таймер для замера длительности операций."""
    
    def __init__(self):
        self._start = None
        self._end = None
    
    def start(self) -> 'Timer':
        """Запустить таймер."""
        self._start = time.time()
        return self
    
    def stop(self) -> 'Timer':
        """Остановить таймер."""
        self._end = time.time()
        return self
    
    @property
    def duration(self) -> float:
        """Длительность в секундах."""
        if self._start is None:
            return 0.0
        if self._end is None:
            return time.time() - self._start
        return self._end - self._start
    
    def __enter__(self) -> 'Timer':
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()


# Импорт time для Timer
import time
