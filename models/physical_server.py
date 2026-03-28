"""
Модель для таблицы physical_servers (физические серверы дата-центра).
"""

from typing import Dict, Any, Optional, List

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.base import BaseModel
from utils.logger import get_logger

logger = get_logger('PhysicalServerModel')


class PhysicalServer(BaseModel):
    """
    Модель для работы с таблицей physical_servers.
    
    Таблица хранит информацию о физических серверах в дата-центре.
    
    Attributes:
        TABLE_NAME (str): Имя таблицы в базе данных
    """
    
    TABLE_NAME = 'physical_servers'
    
    @classmethod
    def get_create_table_query(cls) -> str:
        """
        Возвращает SQL запрос для создания таблицы physical_servers.
        
        Returns:
            str: SQL запрос CREATE TABLE
        """
        return """
        CREATE TABLE IF NOT EXISTS physical_servers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE COMMENT 'Уникальное имя сервера',
            total_cores INT NOT NULL COMMENT 'Общее количество ядер CPU',
            total_ram_gb INT NOT NULL COMMENT 'Общий объем RAM в ГБ',
            total_nvme_gb INT DEFAULT 0 COMMENT 'Общий объем NVME дисков в ГБ',
            total_sata_gb INT DEFAULT 0 COMMENT 'Общий объем SATA дисков в ГБ',
            notes TEXT COMMENT 'Дополнительные заметки',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_physical_servers_name (name),
            INDEX idx_physical_servers_created_at (created_at),
            
            CONSTRAINT chk_cores_positive CHECK (total_cores > 0),
            CONSTRAINT chk_ram_positive CHECK (total_ram_gb > 0),
            CONSTRAINT chk_nvme_non_negative CHECK (total_nvme_gb >= 0),
            CONSTRAINT chk_sata_non_negative CHECK (total_sata_gb >= 0)
            
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Физические серверы дата-центра';
        """
    
    @classmethod
    def create(cls, cursor, name: str, total_cores: int, total_ram_gb: int,
               total_nvme_gb: int = 0, total_sata_gb: int = 0,
               notes: Optional[str] = None) -> Optional[int]:
        """
        Создаёт новый физический сервер.
        
        Args:
            cursor: Курсор MySQL
            name: Имя сервера
            total_cores: Количество ядер CPU
            total_ram_gb: Объем RAM в ГБ
            total_nvme_gb: Объем NVME дисков в ГБ (по умолчанию 0)
            total_sata_gb: Объем SATA дисков в ГБ (по умолчанию 0)
            notes: Дополнительные заметки
        
        Returns:
            Optional[int]: ID созданного сервера или None в случае ошибки
        """
        try:
            query = f"""
                INSERT INTO {cls.TABLE_NAME} 
                (name, total_cores, total_ram_gb, total_nvme_gb, total_sata_gb, notes) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (name, total_cores, total_ram_gb, 
                                  total_nvme_gb, total_sata_gb, notes))
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка при создании физического сервера: {e}")
            return None
    
    @classmethod
    def update(cls, cursor, server_id: int, **kwargs) -> bool:
        """
        Обновляет данные физического сервера.
        
        Args:
            cursor: Курсор MySQL
            server_id: ID сервера
            **kwargs: Поля для обновления (name, total_cores, total_ram_gb, 
                     total_nvme_gb, total_sata_gb, notes)
        
        Returns:
            bool: True если обновление успешно, False в случае ошибки
        """
        allowed_fields = {'name', 'total_cores', 'total_ram_gb', 
                         'total_nvme_gb', 'total_sata_gb', 'notes'}
        
        # Фильтруем только разрешенные поля
        update_data = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_data:
            logger.warning("Нет полей для обновления")
            return False
        
        try:
            set_clause = ", ".join([f"{field} = %s" for field in update_data.keys()])
            values = list(update_data.values())
            values.append(server_id)
            
            query = f"UPDATE {cls.TABLE_NAME} SET {set_clause} WHERE id = %s"
            cursor.execute(query, values)
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка при обновлении физического сервера: {e}")
            return False
    
    @classmethod
    def find_by_name(cls, cursor, name: str) -> Optional[Dict[str, Any]]:
        """
        Находит физический сервер по точному имени.
        
        Args:
            cursor: Курсор MySQL
            name: Имя сервера
        
        Returns:
            Optional[Dict[str, Any]]: Данные сервера или None
        """
        try:
            query = f"SELECT * FROM {cls.TABLE_NAME} WHERE name = %s"
            cursor.execute(query, (name,))
            row = cursor.fetchone()
            
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            logger.error(f"Ошибка при поиске сервера по имени: {e}")
            return None
    
    @classmethod
    def get_available_resources(cls, cursor) -> List[Dict[str, Any]]:
        """
        Возвращает информацию о доступных ресурсах на всех серверах.
        
        Args:
            cursor: Курсор MySQL
        
        Returns:
            List[Dict[str, Any]]: Список серверов с их ресурсами
        """
        try:
            query = f"""
                SELECT 
                    id, name, 
                    total_cores, total_ram_gb, 
                    total_nvme_gb, total_sata_gb,
                    (SELECT SUM(cpu_cores) FROM virtual_servers 
                     WHERE physical_server_id = physical_servers.id 
                     AND status_id = (SELECT id FROM vm_statuses WHERE code = 'active')
                    ) as used_cores,
                    (SELECT SUM(ram_gb) FROM virtual_servers 
                     WHERE physical_server_id = physical_servers.id 
                     AND status_id = (SELECT id FROM vm_statuses WHERE code = 'active')
                    ) as used_ram_gb
                FROM {cls.TABLE_NAME}
                ORDER BY name
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            result = []
            for row in rows:
                data = dict(zip(columns, row))
                # Вычисляем свободные ресурсы
                data['free_cores'] = data['total_cores'] - (data['used_cores'] or 0)
                data['free_ram_gb'] = data['total_ram_gb'] - (data['used_ram_gb'] or 0)
                result.append(data)
            
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении доступных ресурсов: {e}")
            return []
    @classmethod
    def get_all(cls, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Получить все физические серверы"""
        from config.database import get_connection
        get_db_connection = get_connection
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"""
                SELECT * FROM {cls.TABLE_NAME} 
                ORDER BY id 
                LIMIT %s OFFSET %s
            """, (limit, offset))
            return cursor.fetchall()
        finally:
            conn.close()
    
    @classmethod
    def get_by_id(cls, server_id: int) -> Optional[Dict[str, Any]]:
        """Получить физический сервер по ID"""
        from config.database import get_connection
        get_db_connection = get_connection
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"""
                SELECT * FROM {cls.TABLE_NAME} 
                WHERE id = %s
            """, (server_id,))
            return cursor.fetchone()
        finally:
            conn.close()
    
    
    @classmethod
    def update(cls, server_id: int, data: Dict[str, Any]) -> bool:
        """Обновить физический сервер"""
        from config.database import get_connection
        get_db_connection = get_connection
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
            values = list(data.values())
            values.append(server_id)
            query = f"UPDATE {cls.TABLE_NAME} SET {set_clause} WHERE id = %s"
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    @classmethod
    def delete(cls, server_id: int) -> bool:
        """Удалить физический сервер"""
        from config.database import get_connection
        get_db_connection = get_connection
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {cls.TABLE_NAME} WHERE id = %s", (server_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
