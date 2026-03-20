"""
Модель для таблицы daily_billing (ежедневный биллинг).
Хранит рассчитанные стоимости для каждой ВМ за каждый день.
"""

from typing import Dict, Any, Optional, List
from datetime import date, datetime, timedelta

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.base import BaseModel
from models.virtual_server import VirtualServer
from models.resource_price import ResourcePrice
from models.vm_config_history import VMConfigHistory
from utils.logger import get_logger

logger = get_logger('DailyBillingModel')


class DailyBilling(BaseModel):
    """
    Модель для работы с таблицей daily_billing.
    
    Таблица хранит результаты ежедневного расчета стоимости для каждой ВМ.
    Содержит как исходные данные (ресурсы), так и рассчитанные стоимости.
    
    Attributes:
        TABLE_NAME (str): Имя таблицы в базе данных
    """
    
    TABLE_NAME = 'daily_billing'
    
    @classmethod
    def get_create_table_query(cls) -> str:
        """
        Возвращает SQL запрос для создания таблицы daily_billing.
        
        Returns:
            str: SQL запрос CREATE TABLE
        """
        return """
        CREATE TABLE IF NOT EXISTS daily_billing (
            id INT AUTO_INCREMENT PRIMARY KEY,
            billing_date DATE NOT NULL COMMENT 'Дата, за которую произведен расчет',
            vm_id INT NOT NULL COMMENT 'ID виртуального сервера',
            client_id INT NOT NULL COMMENT 'ID клиента (денормализация для ускорения запросов)',
            
            -- Использованные ресурсы (на дату биллинга)
            cpu_cores INT NOT NULL COMMENT 'Количество ядер CPU',
            ram_gb INT NOT NULL COMMENT 'Объем RAM в ГБ',
            
            -- NVME диски (до 5 штук)
            nvme1_gb INT DEFAULT 0 COMMENT 'NVME диск 1 в ГБ',
            nvme2_gb INT DEFAULT 0 COMMENT 'NVME диск 2 в ГБ',
            nvme3_gb INT DEFAULT 0 COMMENT 'NVME диск 3 в ГБ',
            nvme4_gb INT DEFAULT 0 COMMENT 'NVME диск 4 в ГБ',
            nvme5_gb INT DEFAULT 0 COMMENT 'NVME диск 5 в ГБ',
            
            hdd_gb INT DEFAULT 0 COMMENT 'Объем HDD диска в ГБ',
            
            -- Цены на ресурсы (на дату биллинга)
            cpu_price DECIMAL(10, 4) NOT NULL COMMENT 'Цена за ядро',
            ram_price DECIMAL(10, 4) NOT NULL COMMENT 'Цена за ГБ RAM',
            nvme_price DECIMAL(10, 4) NOT NULL COMMENT 'Цена за ГБ NVME',
            hdd_price DECIMAL(10, 4) NOT NULL COMMENT 'Цена за ГБ HDD',
            
            -- Рассчитанные стоимости
            cpu_cost DECIMAL(10, 2) NOT NULL COMMENT 'Стоимость CPU',
            ram_cost DECIMAL(10, 2) NOT NULL COMMENT 'Стоимость RAM',
            nvme_cost DECIMAL(10, 2) NOT NULL COMMENT 'Стоимость NVME',
            hdd_cost DECIMAL(10, 2) NOT NULL COMMENT 'Стоимость HDD',
            total_cost DECIMAL(10, 2) NOT NULL COMMENT 'Общая стоимость',
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Индексы
            INDEX idx_daily_billing_date (billing_date),
            INDEX idx_daily_billing_client (client_id),
            INDEX idx_daily_billing_vm (vm_id),
            INDEX idx_daily_billing_client_date (client_id, billing_date),
            
            -- Внешние ключи
            CONSTRAINT fk_daily_billing_vm 
                FOREIGN KEY (vm_id) REFERENCES virtual_servers(id) 
                ON DELETE CASCADE ON UPDATE CASCADE,
            
            CONSTRAINT fk_daily_billing_client 
                FOREIGN KEY (client_id) REFERENCES clients(id) 
                ON DELETE RESTRICT ON UPDATE CASCADE,
            
            -- Уникальность: для одной ВМ не может быть двух записей за один день
            CONSTRAINT uk_daily_billing_vm_date UNIQUE (vm_id, billing_date),
            
            -- Проверки
            CONSTRAINT chk_billing_costs_non_negative CHECK (
                cpu_cost >= 0 AND ram_cost >= 0 AND 
                nvme_cost >= 0 AND hdd_cost >= 0 AND total_cost >= 0
            )
            
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Ежедневный биллинг';
        """
    
    @classmethod
    def calculate_total_nvme_gb(cls, record: Dict[str, Any]) -> int:
        """
        Вычисляет общий объем NVME дисков из записи биллинга.
        
        Args:
            record: Словарь с данными биллинга
        
        Returns:
            int: Суммарный объем NVME в ГБ
        """
        total = 0
        for i in range(1, 6):
            total += record.get(f'nvme{i}_gb', 0)
        return total
    
    @classmethod
    def calculate_day_cost(cls, cursor, vm_id: int, billing_date: date) -> Optional[Dict[str, Any]]:
        """
        Рассчитывает стоимость для одной ВМ за указанный день.
        
        Args:
            cursor: Курсор MySQL
            vm_id: ID виртуальной машины
            billing_date: Дата расчета
        
        Returns:
            Optional[Dict[str, Any]]: Результат расчета или None
        """
        try:
            # Получаем конфигурацию ВМ на указанную дату
            vm_config = VMConfigHistory.get_config_at_date(cursor, vm_id, billing_date)
            if not vm_config:
                logger.error(f"Не найдена конфигурация для ВМ {vm_id} на {billing_date}")
                return None
            
            # Получаем цены на указанную дату
            prices = ResourcePrice.get_prices_at_date(cursor, billing_date)
            if not prices:
                logger.error(f"Не найдены цены на {billing_date}")
                return None
            
            # Получаем информацию о ВМ (нужен client_id)
            vm_info = VirtualServer.find_by_id(cursor, vm_id)
            if not vm_info:
                logger.error(f"Не найдена информация о ВМ {vm_id}")
                return None
            
            # Проверяем, была ли ВМ активна в этот день
            from models.vm_status import VMStatus
            status_query = """
                SELECT status_id FROM virtual_servers 
                WHERE id = %s
            """
            cursor.execute(status_query, (vm_id,))
            status_id = cursor.fetchone()[0]
            
            # Получаем код статуса
            status_code_query = "SELECT code FROM vm_statuses WHERE id = %s"
            cursor.execute(status_code_query, (status_id,))
            status_code = cursor.fetchone()[0]
            
            # Если ВМ не активна, стоимость = 0
            if status_code != VMStatus.ACTIVE:
                logger.debug(f"ВМ {vm_id} не активна на {billing_date}, стоимость 0")
                return {
                    'vm_id': vm_id,
                    'client_id': vm_info['client_id'],
                    'billing_date': billing_date,
                    'cpu_cores': vm_config['cpu_cores'],
                    'ram_gb': vm_config['ram_gb'],
                    'nvme1_gb': vm_config.get('nvme1_gb', 0),
                    'nvme2_gb': vm_config.get('nvme2_gb', 0),
                    'nvme3_gb': vm_config.get('nvme3_gb', 0),
                    'nvme4_gb': vm_config.get('nvme4_gb', 0),
                    'nvme5_gb': vm_config.get('nvme5_gb', 0),
                    'hdd_gb': vm_config.get('hdd_gb', 0),
                    'cpu_price': prices['cpu_price_per_core'],
                    'ram_price': prices['ram_price_per_gb'],
                    'nvme_price': prices['nvme_price_per_gb'],
                    'hdd_price': prices['hdd_price_per_gb'],
                    'cpu_cost': 0,
                    'ram_cost': 0,
                    'nvme_cost': 0,
                    'hdd_cost': 0,
                    'total_cost': 0
                }
            
            # Рассчитываем стоимости
            cpu_cost = vm_config['cpu_cores'] * prices['cpu_price_per_core']
            ram_cost = vm_config['ram_gb'] * prices['ram_price_per_gb']
            
            # Суммируем все NVME диски
            total_nvme_gb = VirtualServer.get_total_nvme_gb(vm_config)
            nvme_cost = total_nvme_gb * prices['nvme_price_per_gb']
            
            hdd_cost = vm_config.get('hdd_gb', 0) * prices['hdd_price_per_gb']
            
            total_cost = cpu_cost + ram_cost + nvme_cost + hdd_cost
            
            return {
                'vm_id': vm_id,
                'client_id': vm_info['client_id'],
                'billing_date': billing_date,
                'cpu_cores': vm_config['cpu_cores'],
                'ram_gb': vm_config['ram_gb'],
                'nvme1_gb': vm_config.get('nvme1_gb', 0),
                'nvme2_gb': vm_config.get('nvme2_gb', 0),
                'nvme3_gb': vm_config.get('nvme3_gb', 0),
                'nvme4_gb': vm_config.get('nvme4_gb', 0),
                'nvme5_gb': vm_config.get('nvme5_gb', 0),
                'hdd_gb': vm_config.get('hdd_gb', 0),
                'cpu_price': prices['cpu_price_per_core'],
                'ram_price': prices['ram_price_per_gb'],
                'nvme_price': prices['nvme_price_per_gb'],
                'hdd_price': prices['hdd_price_per_gb'],
                'cpu_cost': round(cpu_cost, 2),
                'ram_cost': round(ram_cost, 2),
                'nvme_cost': round(nvme_cost, 2),
                'hdd_cost': round(hdd_cost, 2),
                'total_cost': round(total_cost, 2)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при расчете стоимости для ВМ {vm_id}: {e}")
            return None
    
    @classmethod
    def save_day_billing(cls, cursor, billing_data: Dict[str, Any]) -> bool:
        """
        Сохраняет результат расчета за день.
        
        Args:
            cursor: Курсор MySQL
            billing_data: Словарь с данными для сохранения
        
        Returns:
            bool: True если сохранено успешно
        """
        try:
            query = f"""
                INSERT INTO {cls.TABLE_NAME} 
                (billing_date, vm_id, client_id, 
                 cpu_cores, ram_gb, 
                 nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb,
                 cpu_price, ram_price, nvme_price, hdd_price,
                 cpu_cost, ram_cost, nvme_cost, hdd_cost, total_cost)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (
                billing_data['billing_date'],
                billing_data['vm_id'],
                billing_data['client_id'],
                billing_data['cpu_cores'],
                billing_data['ram_gb'],
                billing_data['nvme1_gb'],
                billing_data['nvme2_gb'],
                billing_data['nvme3_gb'],
                billing_data['nvme4_gb'],
                billing_data['nvme5_gb'],
                billing_data['hdd_gb'],
                billing_data['cpu_price'],
                billing_data['ram_price'],
                billing_data['nvme_price'],
                billing_data['hdd_price'],
                billing_data['cpu_cost'],
                billing_data['ram_cost'],
                billing_data['nvme_cost'],
                billing_data['hdd_cost'],
                billing_data['total_cost']
            ))
            
            logger.info(f"Сохранен биллинг для ВМ {billing_data['vm_id']} на {billing_data['billing_date']}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении биллинга: {e}")
            return False