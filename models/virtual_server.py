"""
Модель для таблицы virtual_servers (виртуальные серверы).
Основная таблица для учета виртуальных машин.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.base import BaseModel
from utils.logger import get_logger

logger = get_logger('VirtualServerModel')


class VirtualServer(BaseModel):
    """
    Модель для работы с таблицей virtual_servers.
    
    Таблица хранит информацию о виртуальных серверах клиентов.
    
    Attributes:
        TABLE_NAME (str): Имя таблицы в базе данных
    """
    
    TABLE_NAME = 'virtual_servers'
    
    @classmethod
    def get_create_table_query(cls) -> str:
        """
        Возвращает SQL запрос для создания таблицы virtual_servers.
        
        Returns:
            str: SQL запрос CREATE TABLE
        """
        return """
        CREATE TABLE IF NOT EXISTS virtual_servers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL COMMENT 'Имя виртуального сервера',
            client_id INT NOT NULL COMMENT 'ID клиента',
            physical_server_id INT NOT NULL COMMENT 'ID физического сервера',
            status_id INT NOT NULL COMMENT 'ID статуса',
            
            purpose VARCHAR(500) COMMENT 'Назначение сервера',
            os VARCHAR(100) COMMENT 'Операционная система',
            
            ip_address VARCHAR(45) COMMENT 'IPv4 или IPv6 адрес',
            ip_port INT DEFAULT 22 COMMENT 'Порт для подключения',
            domain_address VARCHAR(255) COMMENT 'Доменное имя',
            domain_port INT DEFAULT 443 COMMENT 'Порт для домена',
            
            cpu_cores INT NOT NULL COMMENT 'Количество ядер CPU',
            ram_gb INT NOT NULL COMMENT 'Объем RAM в ГБ',
            
            -- NVME диски (до 5 штук)
            nvme1_gb INT DEFAULT 0 COMMENT 'NVME диск 1 в ГБ',
            nvme2_gb INT DEFAULT 0 COMMENT 'NVME диск 2 в ГБ',
            nvme3_gb INT DEFAULT 0 COMMENT 'NVME диск 3 в ГБ',
            nvme4_gb INT DEFAULT 0 COMMENT 'NVME диск 4 в ГБ',
            nvme5_gb INT DEFAULT 0 COMMENT 'NVME диск 5 в ГБ',
            
            hdd_gb INT DEFAULT 0 COMMENT 'Объем HDD диска в ГБ',
            
            start_date DATE COMMENT 'Дата начала использования',
            stop_date DATE COMMENT 'Дата остановки (для удаленных ВМ)',
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            -- Индексы
            INDEX idx_virtual_servers_name (name),
            INDEX idx_virtual_servers_client (client_id),
            INDEX idx_virtual_servers_physical (physical_server_id),
            INDEX idx_virtual_servers_status (status_id),
            INDEX idx_virtual_servers_ip (ip_address),
            INDEX idx_virtual_servers_dates (start_date, stop_date),
            
            -- Внешние ключи
            CONSTRAINT fk_virtual_servers_client 
                FOREIGN KEY (client_id) REFERENCES clients(id) 
                ON DELETE RESTRICT ON UPDATE CASCADE,
            
            CONSTRAINT fk_virtual_servers_physical 
                FOREIGN KEY (physical_server_id) REFERENCES physical_servers(id) 
                ON DELETE RESTRICT ON UPDATE CASCADE,
            
            CONSTRAINT fk_virtual_servers_status 
                FOREIGN KEY (status_id) REFERENCES vm_statuses(id) 
                ON DELETE RESTRICT ON UPDATE CASCADE,
            
            -- Проверки
            CONSTRAINT chk_vm_cpu_positive CHECK (cpu_cores > 0),
            CONSTRAINT chk_vm_ram_positive CHECK (ram_gb > 0),
            CONSTRAINT chk_vm_nvme_ranges CHECK (
                nvme1_gb >= 0 AND nvme2_gb >= 0 AND 
                nvme3_gb >= 0 AND nvme4_gb >= 0 AND nvme5_gb >= 0
            ),
            CONSTRAINT chk_vm_hdd_non_negative CHECK (hdd_gb >= 0),
            CONSTRAINT chk_vm_ip_port_range CHECK (ip_port BETWEEN 1 AND 65535),
            CONSTRAINT chk_vm_domain_port_range CHECK (domain_port BETWEEN 1 AND 65535)
            
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Виртуальные серверы';
        """
    
    @classmethod
    def create(cls, cursor, **kwargs) -> Optional[int]:
        """
        Создает новую виртуальную машину.
        
        Args:
            cursor: Курсор MySQL
            **kwargs: Поля виртуальной машины
        
        Returns:
            Optional[int]: ID созданной ВМ или None
        """
        required_fields = ['name', 'client_id', 'physical_server_id', 
                          'status_id', 'cpu_cores', 'ram_gb']
        
        # Проверяем обязательные поля
        missing_fields = [f for f in required_fields if f not in kwargs]
        if missing_fields:
            logger.error(f"Отсутствуют обязательные поля: {missing_fields}")
            return None
        
        try:
            # Формируем запрос динамически
            fields = list(kwargs.keys())
            placeholders = ", ".join(["%s"] * len(fields))
            field_names = ", ".join(fields)
            
            query = f"""
                INSERT INTO {cls.TABLE_NAME} 
                ({field_names}) 
                VALUES ({placeholders})
            """
            
            values = [kwargs[field] for field in fields]
            cursor.execute(query, values)
            return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Ошибка при создании виртуального сервера: {e}")
            return None
    
    @classmethod
    def get_total_nvme_gb(cls, server_data: Dict[str, Any]) -> int:
        """
        Вычисляет общий объем NVME дисков.
        
        Args:
            server_data: Словарь с данными сервера
        
        Returns:
            int: Суммарный объем NVME в ГБ
        """
        total = 0
        for i in range(1, 6):
            total += server_data.get(f'nvme{i}_gb', 0)
        return total
    
    @classmethod
    def get_active_servers(cls, cursor, client_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Возвращает список активных виртуальных серверов.
        
        Args:
            cursor: Курсор MySQL
            client_id: Если указан, фильтрует по клиенту
        
        Returns:
            List[Dict[str, Any]]: Список активных серверов
        """
        try:
            # Получаем ID статуса "active"
            from models.vm_status import VMStatus
            active_status_id = VMStatus.get_status_id_by_code(cursor, VMStatus.ACTIVE)
            
            if not active_status_id:
                logger.error("Статус 'active' не найден")
                return []
            
            query = f"""
                SELECT 
                    vs.*,
                    c.name as client_name,
                    ps.name as physical_server_name,
                    vms.name as status_name
                FROM {cls.TABLE_NAME} vs
                JOIN clients c ON vs.client_id = c.id
                JOIN physical_servers ps ON vs.physical_server_id = ps.id
                JOIN vm_statuses vms ON vs.status_id = vms.id
                WHERE vs.status_id = %s
            """
            
            params = [active_status_id]
            
            if client_id:
                query += " AND vs.client_id = %s"
                params.append(client_id)
            
            query += " ORDER BY vs.created_at DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            result = []
            for row in rows:
                server = dict(zip(columns, row))
                # Добавляем вычисляемые поля
                server['total_nvme_gb'] = cls.get_total_nvme_gb(server)
                result.append(server)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении активных серверов: {e}")
            return []
    
    @classmethod
    def change_status(cls, cursor, server_id: int, new_status_code: str) -> bool:
        """
        Изменяет статус виртуального сервера.
        
        Args:
            cursor: Курсор MySQL
            server_id: ID сервера
            new_status_code: Новый код статуса (draft, active, deleted)
        
        Returns:
            bool: True если статус изменен успешно
        """
        try:
            from models.vm_status import VMStatus
            status_id = VMStatus.get_status_id_by_code(cursor, new_status_code)
            
            if not status_id:
                logger.error(f"Статус с кодом '{new_status_code}' не найден")
                return False
            
            # Если переводим в deleted, устанавливаем stop_date
            if new_status_code == VMStatus.DELETED:
                query = f"""
                    UPDATE {cls.TABLE_NAME} 
                    SET status_id = %s, stop_date = CURDATE()
                    WHERE id = %s
                """
            else:
                query = f"""
                    UPDATE {cls.TABLE_NAME} 
                    SET status_id = %s, stop_date = NULL
                    WHERE id = %s
                """
            
            cursor.execute(query, (status_id, server_id))
            return cursor.rowcount > 0
            
        except Exception as e:
            logger.error(f"Ошибка при изменении статуса сервера: {e}")
            return False
    @classmethod
    def get_by_physical_server(cls, physical_server_id: int) -> List[Dict]:
        """Получить все виртуальные серверы на физическом сервере"""
        from config.database import get_connection
        get_db_connection = get_connection
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM virtual_servers 
                WHERE physical_server_id = %s 
                ORDER BY id
            """, (physical_server_id,))
            return cursor.fetchall()
        finally:
            conn.close()

    @classmethod
    def get_by_physical_server(cls, physical_server_id: int) -> List[Dict]:
        """Получить все виртуальные серверы на физическом сервере"""
        from config.database import get_connection
        get_db_connection = get_connection
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT vs.*, vs.cpu_cores, vs.ram_gb
                FROM virtual_servers vs
                WHERE vs.physical_server_id = %s 
                ORDER BY vs.id
            """, (physical_server_id,))
            return cursor.fetchall()
        finally:
            conn.close()
