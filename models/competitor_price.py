# billing_system/models/competitor_price.py
"""
Модель цен конкурента
"""

from models.base import BaseModel


class CompetitorPrice(BaseModel):
    """Модель цен конкурента"""
    
    TABLE_NAME = "competitor_prices"
    
    @classmethod
    def create_table(cls, cursor):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitor_prices (
                id INT PRIMARY KEY AUTO_INCREMENT,
                competitor_id INT NOT NULL UNIQUE,
                cpu_price DECIMAL(10,4) NOT NULL DEFAULT 0,
                ram_price DECIMAL(10,4) NOT NULL DEFAULT 0,
                nvme_price DECIMAL(10,4) NOT NULL DEFAULT 0,
                hdd_price DECIMAL(10,4) NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE
            )
        """)
        return True
    
    @classmethod
    def get_by_competitor_id(cls, cursor, competitor_id):
        """Получить цены для конкретного конкурента"""
        cursor.execute(
            "SELECT * FROM competitor_prices WHERE competitor_id = %s",
            (competitor_id,)
        )
        return cursor.fetchone()
    
    @classmethod
    def upsert(cls, cursor, competitor_id, prices):
        """Добавить или обновить цены конкурента"""
        cursor.execute("""
            INSERT INTO competitor_prices (competitor_id, cpu_price, ram_price, nvme_price, hdd_price)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                cpu_price = VALUES(cpu_price),
                ram_price = VALUES(ram_price),
                nvme_price = VALUES(nvme_price),
                hdd_price = VALUES(hdd_price)
        """, (competitor_id, prices.get('cpu', 0), prices.get('ram', 0),
              prices.get('nvme', 0), prices.get('hdd', 0)))
        return True
    
    @classmethod
    def delete_by_competitor_id(cls, cursor, competitor_id):
        """Удалить цены конкурента"""
        cursor.execute("DELETE FROM competitor_prices WHERE competitor_id = %s", (competitor_id,))
        return True
