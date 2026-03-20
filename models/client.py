"""
Модель для таблицы clients (клиенты дата-центра).
"""

from typing import Dict, Any, Optional

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.base import BaseModel
from utils.logger import get_logger

logger = get_logger('ClientModel')


class Client(BaseModel):
    """
    Модель для работы с таблицей clients.
    
    Таблица хранит информацию о клиентах дата-центра.
    
    Attributes:
        TABLE_NAME (str): Имя таблицы в базе данных
    """
    
    TABLE_NAME = 'clients'
    
    @classmethod
    def get_create_table_query(cls) -> str:
        """
        Возвращает SQL запрос для создания таблицы clients.
        
        Returns:
            str: SQL запрос CREATE TABLE
        """
        return """
        CREATE TABLE IF NOT EXISTS clients (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL COMMENT 'Название клиента/компании',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_clients_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Клиенты дата-центра';
        """
    
    @classmethod
    def create(cls, cursor, name: str) -> Optional[int]:
        """
        Создаёт нового клиента.
        
        Args:
            cursor: Курсор MySQL
            name: Название клиента
        
        Returns:
            Optional[int]: ID созданного клиента или None в случае ошибки
        """
        try:
            query = f"INSERT INTO {cls.TABLE_NAME} (name) VALUES (%s)"
            cursor.execute(query, (name,))
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка при создании клиента: {e}")
            return None
    
    @classmethod
    def update(cls, cursor, client_id: int, name: str) -> bool:
        """
        Обновляет данные клиента.
        
        Args:
            cursor: Курсор MySQL
            client_id: ID клиента
            name: Новое название клиента
        
        Returns:
            bool: True если обновление успешно, False в случае ошибки
        """
        try:
            query = f"UPDATE {cls.TABLE_NAME} SET name = %s WHERE id = %s"
            cursor.execute(query, (name, client_id))
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка при обновлении клиента: {e}")
            return False
    
    @classmethod
    def find_by_name(cls, cursor, name: str, exact_match: bool = True) -> list:
        """
        Поиск клиентов по названию.
        
        Args:
            cursor: Курсор MySQL
            name: Название для поиска
            exact_match: True - точное совпадение, False - частичное
        
        Returns:
            list: Список найденных клиентов
        """
        try:
            if exact_match:
                query = f"SELECT * FROM {cls.TABLE_NAME} WHERE name = %s"
                cursor.execute(query, (name,))
            else:
                query = f"SELECT * FROM {cls.TABLE_NAME} WHERE name LIKE %s"
                cursor.execute(query, (f"%{name}%",))
            
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка при поиске клиентов: {e}")
            return []