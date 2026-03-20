"""
Модель для таблицы vm_config_history (история изменений конфигураций ВМ).
Хранит историю изменений ресурсов виртуальных машин.
"""

from typing import Dict, Any, Optional, List
from datetime import date, datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.base import BaseModel
from models.virtual_server import VirtualServer
from utils.logger import get_logger

logger = get_logger('VMConfigHistoryModel')


class VMConfigHistory(BaseModel):
    """
    Модель для работы с таблицей vm_config_history.
    
    Таблица хранит историю изменений конфигурации виртуальных машин.
    Позволяет отслеживать, какие ресурсы были у ВМ в разные периоды времени.
    
    Attributes:
        TABLE_NAME (str): Имя таблицы в базе данных
    """
    
    TABLE_NAME = 'vm_config_history'
    
    @classmethod
    def get_create_table_query(cls) -> str:
        """
        Возвращает SQL запрос для создания таблицы vm_config_history.
        
        Returns:
            str: SQL запрос CREATE TABLE
        """
        return """
        CREATE TABLE IF NOT EXISTS vm_config_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            vm_id INT NOT NULL COMMENT 'ID виртуального сервера',
            effective_from DATE NOT NULL COMMENT 'Дата начала действия конфигурации',
            
            cpu_cores INT NOT NULL COMMENT 'Количество ядер CPU',
            ram_gb INT NOT NULL COMMENT 'Объем RAM в ГБ',
            
            -- NVME диски (до 5 штук)
            nvme1_gb INT DEFAULT 0 COMMENT 'NVME диск 1 в ГБ',
            nvme2_gb INT DEFAULT 0 COMMENT 'NVME диск 2 в ГБ',
            nvme3_gb INT DEFAULT 0 COMMENT 'NVME диск 3 в ГБ',
            nvme4_gb INT DEFAULT 0 COMMENT 'NVME диск 4 в ГБ',
            nvme5_gb INT DEFAULT 0 COMMENT 'NVME диск 5 в ГБ',
            
            hdd_gb INT DEFAULT 0 COMMENT 'Объем HDD диска в ГБ',
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Индексы
            INDEX idx_vm_config_history_vm (vm_id),
            INDEX idx_vm_config_history_date (effective_from),
            
            -- Внешний ключ
            CONSTRAINT fk_vm_config_history_vm 
                FOREIGN KEY (vm_id) REFERENCES virtual_servers(id) 
                ON DELETE CASCADE ON UPDATE CASCADE,
            
            -- Уникальность: для одной ВМ не может быть двух записей с одинаковой датой
            CONSTRAINT uk_vm_config_history_vm_date UNIQUE (vm_id, effective_from),
            
            -- Проверки
            CONSTRAINT chk_hist_cpu_positive CHECK (cpu_cores > 0),
            CONSTRAINT chk_hist_ram_positive CHECK (ram_gb > 0),
            CONSTRAINT chk_hist_nvme_ranges CHECK (
                nvme1_gb >= 0 AND nvme2_gb >= 0 AND 
                nvme3_gb >= 0 AND nvme4_gb >= 0 AND nvme5_gb >= 0
            ),
            CONSTRAINT chk_hist_hdd_non_negative CHECK (hdd_gb >= 0)
            
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='История изменений конфигураций виртуальных машин';
        """
    
    @classmethod
    def save_config_snapshot(cls, cursor, vm_id: int, 
                            effective_from: Optional[date] = None) -> bool:
        """
        Сохраняет текущую конфигурацию ВМ в историю.
        
        Args:
            cursor: Курсор MySQL
            vm_id: ID виртуальной машины
            effective_from: Дата начала действия (по умолчанию - текущая)
        
        Returns:
            bool: True если сохранено успешно
        """
        try:
            # Получаем текущую конфигурацию ВМ
            vm_data = VirtualServer.find_by_id(cursor, vm_id)
            if not vm_data:
                logger.error(f"ВМ с ID {vm_id} не найдена")
                return False
            
            if not effective_from:
                effective_from = date.today()
            
            # Проверяем, нет ли уже записи на эту дату
            check_query = f"""
                SELECT id FROM {cls.TABLE_NAME} 
                WHERE vm_id = %s AND effective_from = %s
            """
            cursor.execute(check_query, (vm_id, effective_from))
            if cursor.fetchone():
                logger.warning(f"Запись для ВМ {vm_id} на дату {effective_from} уже существует")
                return False
            
            # Сохраняем конфигурацию
            insert_query = f"""
                INSERT INTO {cls.TABLE_NAME} 
                (vm_id, effective_from, cpu_cores, ram_gb, 
                 nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                vm_id, effective_from,
                vm_data['cpu_cores'], vm_data['ram_gb'],
                vm_data.get('nvme1_gb', 0), vm_data.get('nvme2_gb', 0),
                vm_data.get('nvme3_gb', 0), vm_data.get('nvme4_gb', 0),
                vm_data.get('nvme5_gb', 0), vm_data.get('hdd_gb', 0)
            ))
            
            logger.info(f"Сохранена конфигурация ВМ {vm_id} на {effective_from}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении конфигурации ВМ: {e}")
            return False
    
    @classmethod
    def get_config_at_date(cls, cursor, vm_id: int, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Возвращает конфигурацию ВМ на указанную дату.
        
        Args:
            cursor: Курсор MySQL
            vm_id: ID виртуальной машины
            target_date: Дата, на которую нужна конфигурация
        
        Returns:
            Optional[Dict[str, Any]]: Конфигурация ВМ или None
        """
        try:
            # Находим ближайшую запись с датой <= target_date
            query = f"""
                SELECT * FROM {cls.TABLE_NAME}
                WHERE vm_id = %s AND effective_from <= %s
                ORDER BY effective_from DESC
                LIMIT 1
            """
            
            cursor.execute(query, (vm_id, target_date))
            row = cursor.fetchone()
            
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            
            # Если нет истории, берем текущую конфигурацию из virtual_servers
            return VirtualServer.find_by_id(cursor, vm_id)
            
        except Exception as e:
            logger.error(f"Ошибка при получении конфигурации на дату: {e}")
            return None
    
    @classmethod
    def get_config_history(cls, cursor, vm_id: int) -> List[Dict[str, Any]]:
        """
        Возвращает всю историю изменений конфигурации ВМ.
        
        Args:
            cursor: Курсор MySQL
            vm_id: ID виртуальной машины
        
        Returns:
            List[Dict[str, Any]]: Список записей истории
        """
        try:
            query = f"""
                SELECT * FROM {cls.TABLE_NAME}
                WHERE vm_id = %s
                ORDER BY effective_from DESC
            """
            
            cursor.execute(query, (vm_id,))
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            history = []
            for row in rows:
                config = dict(zip(columns, row))
                config['total_nvme_gb'] = VirtualServer.get_total_nvme_gb(config)
                history.append(config)
            
            return history
            
        except Exception as e:
            logger.error(f"Ошибка при получении истории конфигураций: {e}")
            return []