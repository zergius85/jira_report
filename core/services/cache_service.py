# -*- coding: utf-8 -*-
"""
Сервис кэширования метаданных.

Инкапсулирует логику кэширования с TTL и инвалидацией по времени.
"""
import time
import logging
from typing import Any, Optional, Dict, Generic, TypeVar
from functools import wraps

from core.config import CACHE_METADATA_TTL, CACHE_MAX_SIZE

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheEntry(Generic[T]):
    """Запись в кэше с временем жизни."""
    
    def __init__(self, value: T, ttl: int):
        """
        Инициализация записи.
        
        Args:
            value: Значение
            ttl: Время жизни в секундах
        """
        self.value = value
        self.expires_at = time.time() + ttl
    
    def is_expired(self) -> bool:
        """Проверить, истёк ли срок жизни."""
        return time.time() > self.expires_at


class MetadataCache:
    """
    Кэш метаданных с TTL.
    
    Использует LRU-стратегию с ограничением по размеру.
    Автоматически инвалидирует устаревшие записи по TTL.
    
    Attributes:
        ttl: Время жизни записей в секундах
        max_size: Максимальный размер кэша
    """
    
    def __init__(self, ttl: Optional[int] = None, max_size: Optional[int] = None):
        """
        Инициализация кэша.
        
        Args:
            ttl: Время жизни записей (секунды). По умолчанию из config.
            max_size: Максимальный размер кэша. По умолчанию из config.
        """
        self.ttl = ttl or CACHE_METADATA_TTL
        self.max_size = max_size or CACHE_MAX_SIZE
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: list = []  # Для LRU
        
        logger.debug(f"MetadataCache инициализирован: TTL={self.ttl}s, max_size={self.max_size}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Получить значение из кэша.
        
        Args:
            key: Ключ
            default: Значение по умолчанию
            
        Returns:
            Значение из кэша или default
        """
        if key not in self._cache:
            logger.debug(f"Cache miss: {key}")
            return default
        
        entry = self._cache[key]
        
        if entry.is_expired():
            logger.debug(f"Cache expired: {key}")
            self.delete(key)
            return default
        
        # Обновляем порядок доступа (LRU)
        self._update_access(key)
        
        logger.debug(f"Cache hit: {key}")
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Сохранить значение в кэш.
        
        Args:
            key: Ключ
            value: Значение
            ttl: Время жизни (секунды). По умолчанию используется self.ttl
        """
        # Удаляем старую запись если есть
        if key in self._cache:
            self.delete(key)
        
        # Проверяем размер кэша
        if len(self._cache) >= self.max_size:
            self._evict_lru()
        
        # Создаём запись
        entry_ttl = ttl or self.ttl
        self._cache[key] = CacheEntry(value, entry_ttl)
        self._access_order.append(key)
        
        logger.debug(f"Cache set: {key} (TTL={entry_ttl}s)")
    
    def delete(self, key: str) -> None:
        """
        Удалить значение из кэша.
        
        Args:
            key: Ключ
        """
        if key in self._cache:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            logger.debug(f"Cache delete: {key}")
    
    def clear(self) -> None:
        """Очистить весь кэш."""
        self._cache.clear()
        self._access_order.clear()
        logger.info("Cache cleared")
    
    def _update_access(self, key: str) -> None:
        """Обновить порядок доступа (LRU)."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def _evict_lru(self) -> None:
        """Удалить наименее используемую запись."""
        if self._access_order:
            lru_key = self._access_order[0]
            self.delete(lru_key)
            logger.debug(f"Cache LRU evict: {lru_key}")
    
    def stats(self) -> Dict[str, int]:
        """
        Получить статистику кэша.
        
        Returns:
            Dict с ключами: size, max_size, ttl
        """
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'ttl': self.ttl
        }


# Глобальный экземпляр кэша
_metadata_cache: Optional[MetadataCache] = None


def get_metadata_cache(ttl: Optional[int] = None, max_size: Optional[int] = None) -> MetadataCache:
    """
    Получить глобальный экземпляр кэша.
    
    Args:
        ttl: Время жизни записей (секунды)
        max_size: Максимальный размер кэша
        
    Returns:
        MetadataCache: Экземпляр кэша
    """
    global _metadata_cache
    if _metadata_cache is None:
        _metadata_cache = MetadataCache(ttl=ttl, max_size=max_size)
    return _metadata_cache


def cached(ttl: Optional[int] = None, key_prefix: str = ''):
    """
    Декоратор для кэширования результатов функции.
    
    Args:
        ttl: Время жизни кэша (секунды)
        key_prefix: Префикс для ключа кэша
        
    Returns:
        Декоратор
        
    Пример:
        @cached(ttl=300, key_prefix='projects')
        def get_projects():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_metadata_cache(ttl=ttl)
            
            # Формируем ключ
            cache_key = f"{key_prefix}:{func.__name__}"
            if args:
                cache_key += f":{str(args[0]) if args else ''}"
            for k, v in sorted(kwargs.items()):
                cache_key += f":{k}={v}"
            
            # Проверяем кэш
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Вызываем функцию
            result = func(*args, **kwargs)
            
            # Сохраняем в кэш
            cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator
