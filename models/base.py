"""
Базовая модель для всех таблиц базы данных.
Содержит общие методы для работы с таблицами.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
from mysql.connector import Error

# Добавляем путь к проекту для импорта логгера
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from utils.logger import get_logger

logger = get_logger('BaseModel')


class BaseModel(ABC):
    """
    Абстрактный базовый класс для всех моделей.
    
    Attributes:
        TABLE_NAME (str): Имя таблицы в базе данных (должен быть переопределён)
    """
    
    TABLE_NAME: str = None  # Должен быть переопределён в дочерних классах
    
    @classmethod
    @abstractmethod
    def get_create_table_query(cls) -> str:
        """
        Возвращает SQL запрос для создания таблицы.
        Должен быть переопределён в дочерних классах.
        
        Returns:
            str: SQL запрос CREATE TABLE
        """
        pass
    
    @classmethod
    def create_table(cls, cursor: mysql.connector.cursor.MySQLCursor) -> bool:
        """
        Создаёт таблицу в базе данных, если она не существует.
        
        Args:
            cursor: Курсор MySQL для выполнения запросов
        
        Returns:
            bool: True если таблица создана или уже существовала, False в случае ошибки
        
        Raises:
            ValueError: Если TABLE_NAME не определён
        """
        if not cls.TABLE_NAME:
            raise ValueError(f"TABLE_NAME не определён для класса {cls.__name__}")
        
        try:
            # Проверяем, существует ли уже таблица
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
                AND table_name = %s
            """, (cls.TABLE_NAME,))
            
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                logger.info(f"Таблица {cls.TABLE_NAME} уже существует")
                return True
            
            # Создаём таблицу
            create_query = cls.get_create_table_query()
            logger.debug(f"Создание таблицы {cls.TABLE_NAME}...")
            cursor.execute(create_query)
            logger.info(f"Таблица {cls.TABLE_NAME} успешно создана")
            return True
            
        except Error as e:
            logger.error(f"Ошибка при создании таблицы {cls.TABLE_NAME}: {e}")
            return False
    
    @classmethod
    def insert_default_data(cls, cursor: mysql.connector.cursor.MySQLCursor) -> bool:
        """
        Вставляет данные по умолчанию в таблицу.
        По умолчанию ничего не делает. Должен быть переопределён при необходимости.
        
        Args:
            cursor: Курсор MySQL для выполнения запросов
        
        Returns:
            bool: True если данные вставлены успешно, False в случае ошибки
        """
        # По умолчанию ничего не делаем
        return True
    
    @classmethod
    def find_by_id(cls, cursor: mysql.connector.cursor.MySQLCursor, 
                   record_id: int) -> Optional[Dict[str, Any]]:
        """
        Находит запись по ID.
        
        Args:
            cursor: Курсор MySQL для выполнения запросов
            record_id: ID записи
        
        Returns:
            Optional[Dict[str, Any]]: Словарь с данными записи или None
        """
        if not cls.TABLE_NAME:
            raise ValueError(f"TABLE_NAME не определён для класса {cls.__name__}")
        
        try:
            cursor.execute(f"SELECT * FROM {cls.TABLE_NAME} WHERE id = %s", (record_id,))
            row = cursor.fetchone()
            
            if row:
                # Получаем названия колонок
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
            
        except Error as e:
            logger.error(f"Ошибка при поиске записи в {cls.TABLE_NAME}: {e}")
            return None
    
    @classmethod
    def find_all(cls, cursor: mysql.connector.cursor.MySQLCursor,
                 limit: Optional[int] = None,
                 order_by: str = "id") -> List[Dict[str, Any]]:
        """
        Возвращает все записи из таблицы.
        
        Args:
            cursor: Курсор MySQL для выполнения запросов
            limit: Максимальное количество записей (None - все)
            order_by: Поле для сортировки
        
        Returns:
            List[Dict[str, Any]]: Список словарей с данными записей
        """
        if not cls.TABLE_NAME:
            raise ValueError(f"TABLE_NAME не определён для класса {cls.__name__}")
        
        try:
            query = f"SELECT * FROM {cls.TABLE_NAME} ORDER BY {order_by}"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
            
        except Error as e:
            logger.error(f"Ошибка при получении записей из {cls.TABLE_NAME}: {e}")
            return []
    
    @classmethod
    def delete_by_id(cls, cursor: mysql.connector.cursor.MySQLCursor,
                     record_id: int) -> bool:
        """
        Удаляет запись по ID (мягкое удаление не поддерживается).
        
        Args:
            cursor: Курсор MySQL для выполнения запросов
            record_id: ID записи для удаления
        
        Returns:
            bool: True если запись удалена, False в случае ошибки
        """
        if not cls.TABLE_NAME:
            raise ValueError(f"TABLE_NAME не определён для класса {cls.__name__}")
        
        try:
            cursor.execute(f"DELETE FROM {cls.TABLE_NAME} WHERE id = %s", (record_id,))
            return cursor.rowcount > 0
            
        except Error as e:
            logger.error(f"Ошибка при удалении записи из {cls.TABLE_NAME}: {e}")
            return False