# billing_system/models/competitor.py
"""
Модель конкурента
"""

from models.base import BaseModel


class Competitor(BaseModel):
    """Модель конкурента"""
    
    TABLE_NAME = "competitors"
    
    @classmethod
    def create_table(cls, cursor):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitors (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(100) NOT NULL UNIQUE,
                website VARCHAR(255),
                logo_url VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                sort_order INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        return True
    
    @classmethod
    def get_all_active(cls, cursor):
        """Получить всех активных конкурентов, отсортированных по sort_order"""
        cursor.execute("""
            SELECT * FROM competitors 
            WHERE is_active = TRUE 
            ORDER BY sort_order ASC, name ASC
        """)
        return cursor.fetchall()
    
    @classmethod
    def get_all(cls, cursor):
        """Получить всех конкурентов"""
        cursor.execute("""
            SELECT * FROM competitors 
            ORDER BY sort_order ASC, name ASC
        """)
        return cursor.fetchall()
    
    @classmethod
    def get_by_id(cls, cursor, competitor_id):
        """Получить конкурента по ID"""
        cursor.execute("SELECT * FROM competitors WHERE id = %s", (competitor_id,))
        return cursor.fetchone()
    
    @classmethod
    def create(cls, cursor, data):
        """Создать нового конкурента"""
        cursor.execute("""
            INSERT INTO competitors (name, website, logo_url, is_active, sort_order)
            VALUES (%s, %s, %s, %s, %s)
        """, (data.get('name'), data.get('website'), data.get('logo_url'),
              data.get('is_active', True), data.get('sort_order', 0)))
        return cursor.lastrowid
    
    @classmethod
    def update(cls, cursor, competitor_id, data):
        """Обновить конкурента"""
        cursor.execute("""
            UPDATE competitors 
            SET name = %s, website = %s, logo_url = %s, is_active = %s, sort_order = %s
            WHERE id = %s
        """, (data.get('name'), data.get('website'), data.get('logo_url'),
              data.get('is_active', True), data.get('sort_order', 0), competitor_id))
        return True
    
    @classmethod
    def delete(cls, cursor, competitor_id):
        """Удалить конкурента"""
        cursor.execute("DELETE FROM competitors WHERE id = %s", (competitor_id,))
        return True
