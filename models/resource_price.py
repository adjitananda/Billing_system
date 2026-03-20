"""
Модель для таблицы resource_prices (цены на ресурсы).
Хранит историю изменения цен на вычислительные ресурсы.
"""

from typing import Dict, Any, Optional, List
from datetime import date

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from models.base import BaseModel
from utils.logger import get_logger

logger = get_logger('ResourcePriceModel')


class ResourcePrice(BaseModel):
    """
    Модель для работы с таблицей resource_prices.
    
    Таблица хранит цены на ресурсы в разные периоды времени.
    Цены могут меняться, поэтому важно хранить историю.
    
    Attributes:
        TABLE_NAME (str): Имя таблицы в базе данных
    """
    
    TABLE_NAME = 'resource_prices'
    
    @classmethod
    def get_create_table_query(cls) -> str:
        """
        Возвращает SQL запрос для создания таблицы resource_prices.
        
        Returns:
            str: SQL запрос CREATE TABLE
        """
        return """
        CREATE TABLE IF NOT EXISTS resource_prices (
            id INT AUTO_INCREMENT PRIMARY KEY,
            effective_from DATE NOT NULL COMMENT 'Дата начала действия цен',
            
            cpu_price_per_core DECIMAL(10, 4) NOT NULL COMMENT 'Цена за ядро в день',
            ram_price_per_gb DECIMAL(10, 4) NOT NULL COMMENT 'Цена за ГБ RAM в день',
            nvme_price_per_gb DECIMAL(10, 4) NOT NULL COMMENT 'Цена за ГБ NVME в день',
            hdd_price_per_gb DECIMAL(10, 4) NOT NULL COMMENT 'Цена за ГБ HDD в день',
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Индексы
            INDEX idx_resource_prices_date (effective_from),
            
            -- Уникальность: не может быть двух записей с одинаковой датой
            CONSTRAINT uk_resource_prices_date UNIQUE (effective_from),
            
            -- Проверки
            CONSTRAINT chk_cpu_price_positive CHECK (cpu_price_per_core > 0),
            CONSTRAINT chk_ram_price_positive CHECK (ram_price_per_gb > 0),
            CONSTRAINT chk_nvme_price_positive CHECK (nvme_price_per_gb > 0),
            CONSTRAINT chk_hdd_price_positive CHECK (hdd_price_per_gb > 0)
            
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='Цены на ресурсы';
        """
    
    @classmethod
    def insert_default_data(cls, cursor) -> bool:
        """
        Вставляет начальные цены, если таблица пуста.
        
        Args:
            cursor: Курсор MySQL
        
        Returns:
            bool: True если данные вставлены успешно
        """
        try:
            # Проверяем, есть ли уже данные
            cursor.execute(f"SELECT COUNT(*) FROM {cls.TABLE_NAME}")
            count = cursor.fetchone()[0]
            
            if count > 0:
                logger.info(f"Таблица {cls.TABLE_NAME} уже содержит {count} записей")
                return True
            
            # Вставляем начальные цены (примерные)
            query = f"""
                INSERT INTO {cls.TABLE_NAME} 
                (effective_from, cpu_price_per_core, ram_price_per_gb, 
                 nvme_price_per_gb, hdd_price_per_gb)
                VALUES 
                (CURDATE(), 50.0000, 10.0000, 0.5000, 0.2500)
            """
            
            cursor.execute(query)
            logger.info("Добавлены начальные цены на ресурсы")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при вставке начальных цен: {e}")
            return False
    
    @classmethod
    def create(cls, cursor, effective_from: date, cpu_price: float, ram_price: float,
               nvme_price: float, hdd_price: float) -> Optional[int]:
        """
        Создает новую запись с ценами.
        
        Args:
            cursor: Курсор MySQL
            effective_from: Дата начала действия
            cpu_price: Цена за ядро
            ram_price: Цена за ГБ RAM
            nvme_price: Цена за ГБ NVME
            hdd_price: Цена за ГБ HDD
        
        Returns:
            Optional[int]: ID созданной записи или None
        """
        try:
            query = f"""
                INSERT INTO {cls.TABLE_NAME} 
                (effective_from, cpu_price_per_core, ram_price_per_gb, 
                 nvme_price_per_gb, hdd_price_per_gb)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (effective_from, cpu_price, ram_price, 
                                  nvme_price, hdd_price))
            return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Ошибка при создании записи цен: {e}")
            return None
    
    @classmethod
    def get_prices_at_date(cls, cursor, target_date: date) -> Optional[Dict[str, Any]]:
        """
        Возвращает цены, действующие на указанную дату.
        
        Args:
            cursor: Курсор MySQL
            target_date: Дата, на которую нужны цены
        
        Returns:
            Optional[Dict[str, Any]]: Словарь с ценами или None
        """
        try:
            # Находим ближайшую запись с датой <= target_date
            query = f"""
                SELECT * FROM {cls.TABLE_NAME}
                WHERE effective_from <= %s
                ORDER BY effective_from DESC
                LIMIT 1
            """
            
            cursor.execute(query, (target_date,))
            row = cursor.fetchone()
            
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            
            logger.warning(f"Не найдены цены на дату {target_date}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении цен на дату: {e}")
            return None
    
    @classmethod
    def get_current_prices(cls, cursor) -> Optional[Dict[str, Any]]:
        """
        Возвращает актуальные цены на сегодня.
        
        Args:
            cursor: Курсор MySQL
        
        Returns:
            Optional[Dict[str, Any]]: Словарь с текущими ценами
        """
        return cls.get_prices_at_date(cursor, date.today())
    
    @classmethod
    def get_price_history(cls, cursor, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Возвращает историю изменения цен.
        
        Args:
            cursor: Курсор MySQL
            limit: Максимальное количество записей
        
        Returns:
            List[Dict[str, Any]]: Список записей с ценами
        """
        try:
            query = f"""
                SELECT * FROM {cls.TABLE_NAME}
                ORDER BY effective_from DESC
                LIMIT %s
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
            
        except Exception as e:
            logger.error(f"Ошибка при получении истории цен: {e}")
            return []