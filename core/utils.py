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
