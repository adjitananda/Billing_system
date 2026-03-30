"""
Модель для таблицы vm_statuses (статусы виртуальных машин).
Справочник с предопределенными статусами.
"""

from typing import Dict, Any, Optional

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.base import BaseModel
from utils.logger import get_logger

logger = get_logger('VMStatusModel')


class VMStatus(BaseModel):
    """
    Модель для работы с таблицей vm_statuses.
    
    Таблица хранит возможные статусы виртуальных машин:
    - inactive: Не активен (сервер создан, но не запущен, ресурсы заняты)
    - active: Активен (сервер работает и тарифицируется)
    - deleted: Удалён (сервер удален, ресурсы освобождены)
    
    Attributes:
        TABLE_NAME (str): Имя таблицы в базе данных
        DEFAULT_STATUSES (dict): Словарь со статусами по умолчанию
    """
    
    TABLE_NAME = 'vm_statuses'
    
    # Константы для статусов (для использования в коде)
    INACTIVE = 'inactive'
    ACTIVE = 'active'
    DELETED = 'deleted'
    
    DEFAULT_STATUSES = [
        {'code': INACTIVE, 'name': 'Не активен'},
        {'code': ACTIVE, 'name': 'Активен'},
        {'code': DELETED, 'name': 'Удалён'}
    ]
    
    @classmethod
    def get_create_table_query(cls) -> str:
        """
        Возвращает SQL запрос для создания таблицы vm_statuses.
        
        Returns:
            str: SQL запрос CREATE TABLE
        """
        return """
        CREATE TABLE IF NOT EXISTS vm_statuses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(50) NOT NULL UNIQUE COMMENT 'Уникальный код статуса (inactive, active, deleted)',
            name VARCHAR(100) NOT NULL COMMENT 'Отображаемое название статуса',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            INDEX idx_vm_statuses_code (code)
            
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Статусы виртуальных машин';
        """
    
    @classmethod
    def insert_default_data(cls, cursor) -> bool:
        """
        Вставляет начальные статусы в таблицу.
        
        Args:
            cursor: Курсор MySQL
        
        Returns:
            bool: True если данные вставлены успешно, False в случае ошибки
        """
        try:
            # Проверяем, есть ли уже данные в таблице
            cursor.execute(f"SELECT COUNT(*) FROM {cls.TABLE_NAME}")
            count = cursor.fetchone()[0]
            
            if count > 0:
                logger.info(f"Таблица {cls.TABLE_NAME} уже содержит {count} записей")
                return True
            
            # Вставляем статусы по умолчанию
            for status in cls.DEFAULT_STATUSES:
                query = f"""
                    INSERT INTO {cls.TABLE_NAME} (code, name) 
                    VALUES (%s, %s)
                """
                cursor.execute(query, (status['code'], status['name']))
            
            logger.info(f"Добавлено {len(cls.DEFAULT_STATUSES)} статусов ВМ")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при вставке начальных статусов: {e}")
            return False
    
    @classmethod
    def get_status_id_by_code(cls, cursor, code: str) -> Optional[int]:
        """
        Возвращает ID статуса по его коду.
        
        Args:
            cursor: Курсор MySQL
            code: Код статуса (inactive, active, deleted)
        
        Returns:
            Optional[int]: ID статуса или None
        """
        try:
            query = f"SELECT id FROM {cls.TABLE_NAME} WHERE code = %s"
            cursor.execute(query, (code,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Ошибка при получении ID статуса {code}: {e}")
            return None
    
    @classmethod
    def get_all_statuses(cls, cursor) -> list:
        """
        Возвращает все статусы.
        
        Args:
            cursor: Курсор MySQL
        
        Returns:
            list: Список всех статусов
        """
        try:
            query = f"SELECT id, code, name FROM {cls.TABLE_NAME} ORDER BY id"
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка при получении списка статусов: {e}")
            return []
