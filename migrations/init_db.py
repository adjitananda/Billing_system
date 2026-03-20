"""
Скрипт для создания всех таблиц базы данных биллинговой системы.
Запускается при первом развертывании проекта.
"""

import sys
from pathlib import Path

# Добавляем путь к проекту для импорта модулей
sys.path.append(str(Path(__file__).parent.parent))

from config.database import get_connection
from utils.logger import get_logger

# Импортируем все модели
from models.client import Client
from models.physical_server import PhysicalServer
from models.vm_status import VMStatus
from models.virtual_server import VirtualServer
from models.vm_config_history import VMConfigHistory
from models.resource_price import ResourcePrice
from models.daily_billing import DailyBilling

# Создаем логгер
logger = get_logger('Migration')


def create_all_tables():
    """
    Создает все таблицы в правильном порядке с учетом внешних ключей.
    Также заполняет начальными данными справочники.
    """
    connection = None
    cursor = None
    
    try:
        # Получаем соединение с БД
        logger.info("Начало процесса создания таблиц")
        connection = get_connection()
        cursor = connection.cursor()
        
        # 1. Сначала создаем таблицы, на которые нет внешних ссылок
        logger.info("Шаг 1/8: Создание таблицы clients...")
        if not Client.create_table(cursor):
            raise Exception("Не удалось создать таблицу clients")
        
        logger.info("Шаг 2/8: Создание таблицы physical_servers...")
        if not PhysicalServer.create_table(cursor):
            raise Exception("Не удалось создать таблицу physical_servers")
        
        logger.info("Шаг 3/8: Создание таблицы vm_statuses...")
        if not VMStatus.create_table(cursor):
            raise Exception("Не удалось создать таблицу vm_statuses")
        
        # 2. Создаем таблицы, которые ссылаются на первые три
        logger.info("Шаг 4/8: Создание таблицы virtual_servers...")
        if not VirtualServer.create_table(cursor):
            raise Exception("Не удалось создать таблицу virtual_servers")
        
        logger.info("Шаг 5/8: Создание таблицы vm_config_history...")
        if not VMConfigHistory.create_table(cursor):
            raise Exception("Не удалось создать таблицу vm_config_history")
        
        logger.info("Шаг 6/8: Создание таблицы resource_prices...")
        if not ResourcePrice.create_table(cursor):
            raise Exception("Не удалось создать таблицу resource_prices")
        
        logger.info("Шаг 7/8: Создание таблицы daily_billing...")
        if not DailyBilling.create_table(cursor):
            raise Exception("Не удалось создать таблицу daily_billing")
        
        # 3. Заполняем начальными данными
        logger.info("Шаг 8/8: Заполнение справочников начальными данными...")
        
        # Статусы ВМ
        logger.info("Заполнение таблицы vm_statuses...")
        if not VMStatus.insert_default_data(cursor):
            logger.warning("Не удалось заполнить таблицу vm_statuses данными")
        
        # Цены на ресурсы (если таблица пуста)
        logger.info("Заполнение таблицы resource_prices...")
        if not ResourcePrice.insert_default_data(cursor):
            logger.warning("Не удалось заполнить таблицу resource_prices данными")
        
        # Сохраняем все изменения
        connection.commit()
        logger.info("✅ Все таблицы успешно созданы и заполнены начальными данными")
        
        # Выводим статистику
        cursor.execute("SELECT COUNT(*) FROM clients")
        clients_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM physical_servers")
        servers_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM vm_statuses")
        statuses_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM resource_prices")
        prices_count = cursor.fetchone()[0]
        
        logger.info("📊 Статистика базы данных:")
        logger.info(f"  - Клиентов: {clients_count}")
        logger.info(f"  - Физических серверов: {servers_count}")
        logger.info(f"  - Статусов ВМ: {statuses_count}")
        logger.info(f"  - Записей с ценами: {prices_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}")
        if connection:
            connection.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logger.debug("Соединение с БД закрыто")


def drop_all_tables():
    """
    Удаляет все таблицы (danger! только для разработки).
    Используется для очистки базы данных при тестировании.
    """
    connection = None
    cursor = None
    
    try:
        logger.warning("⚠️  ВНИМАНИЕ: Начинается удаление всех таблиц!")
        connection = get_connection()
        cursor = connection.cursor()
        
        # Отключаем проверку внешних ключей
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # Удаляем таблицы в обратном порядке (зависимые сначала)
        tables = [
            'daily_billing',
            'vm_config_history',
            'virtual_servers',
            'resource_prices',
            'vm_statuses',
            'physical_servers',
            'clients'
        ]
        
        for table in tables:
            logger.info(f"Удаление таблицы {table}...")
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        
        # Включаем обратно проверку внешних ключей
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        connection.commit()
        logger.info("✅ Все таблицы успешно удалены")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении таблиц: {e}")
        if connection:
            connection.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    """
    При прямом запуске скрипта создаем таблицы.
    Для удаления таблиц нужно явно вызвать drop_all_tables()
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Управление таблицами БД')
    parser.add_argument('--drop', action='store_true', 
                       help='Удалить все таблицы (осторожно!)')
    
    args = parser.parse_args()
    
    if args.drop:
        logger.warning("Выполняется удаление всех таблиц...")
        confirm = input("Вы уверены? Это действие необратимо! (yes/no): ")
        if confirm.lower() == 'yes':
            drop_all_tables()
        else:
            logger.info("Операция отменена")
    else:
        create_all_tables()