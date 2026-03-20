"""
Модуль для подключения к базе данных MySQL.
Читает параметры из переменных окружения и устанавливает соединение.
"""

import os
import sys
from pathlib import Path

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Добавляем путь к проекту для импорта логгера
sys.path.append(str(Path(__file__).parent.parent))
from utils.logger import get_logger

# Загружаем переменные окружения из .env файла
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Создаем логгер для этого модуля
logger = get_logger('Database')


def get_connection():
    """
    Устанавливает соединение с MySQL базой данных.
    
    Returns:
        mysql.connector.connection: Объект соединения с БД
    
    Raises:
        SystemExit: Если не удается подключиться к БД
    """
    # Получаем параметры подключения из переменных окружения
    config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'database': os.getenv('MYSQL_DATABASE'),
        'charset': 'utf8mb4',
        'use_unicode': True,
        'autocommit': False,  # Отключаем автокоммит для управления транзакциями
        'connection_timeout': 30  # Таймаут подключения 30 секунд
    }
    
    # Проверяем наличие обязательных параметров
    required_params = ['user', 'password', 'database']
    missing_params = [param for param in required_params if not config.get(param)]
    
    if missing_params:
        logger.error(f"Отсутствуют обязательные параметры подключения: {', '.join(missing_params)}")
        logger.error("Проверьте наличие и содержимое файла .env")
        sys.exit(1)
    
    try:
        logger.debug(f"Попытка подключения к MySQL: {config['host']}:{config['port']}")
        connection = mysql.connector.connect(**config)
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            logger.info(f"Успешное подключение к MySQL Server версии {db_info}")
            logger.info(f"База данных: {config['database']}")
            return connection
            
    except Error as e:
        logger.error(f"Ошибка подключения к MySQL: {e}")
        logger.error("Проверьте:")
        logger.error("  - Запущен ли MySQL сервер")
        logger.error("  - Правильность учетных данных в .env файле")
        logger.error("  - Существует ли база данных")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Неожиданная ошибка при подключении к БД: {e}")
        sys.exit(1)


def test_connection():
    """
    Тестовая функция для проверки подключения.
    Можно использовать для отладки.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        logger.info(f"MySQL version: {version[0]}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Тест подключения не пройден: {e}")
        return False


if __name__ == "__main__":
    # Если файл запущен напрямую, тестируем подключение
    test_connection()