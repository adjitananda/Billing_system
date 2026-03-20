#!/usr/bin/env python3
"""
Точка входа в биллинговую систему.
Запускает инициализацию базы данных при первом запуске.
"""

import sys
from pathlib import Path

# Добавляем текущую директорию в путь для импорта
sys.path.append(str(Path(__file__).parent))

from migrations.init_db import create_all_tables
from utils.logger import get_logger
from config.database import test_connection

# Создаем логгер
logger = get_logger('BillingSystem')


def main():
    """
    Главная функция приложения.
    Проверяет подключение к БД и инициализирует структуру таблиц.
    """
    logger.info("=" * 50)
    logger.info("🚀 Запуск биллинговой системы дата-центра")
    logger.info("=" * 50)
    
    # Шаг 1: Проверка подключения к БД
    logger.info("Шаг 1/2: Проверка подключения к MySQL...")
    if not test_connection():
        logger.error("❌ Не удалось подключиться к базе данных")
        logger.error("Проверьте настройки в файле .env и доступность MySQL сервера")
        sys.exit(1)
    
    # Шаг 2: Создание таблиц
    logger.info("Шаг 2/2: Инициализация структуры базы данных...")
    if create_all_tables():
        logger.info("=" * 50)
        logger.info("✅ База данных готова к работе!")
        logger.info("=" * 50)
        logger.info("📋 Следующие шаги:")
        logger.info("  1. Добавьте клиентов через models.client.Client.create()")
        logger.info("  2. Добавьте физические серверы через models.physical_server.PhysicalServer.create()")
        logger.info("  3. Создавайте виртуальные машины через models.virtual_server.VirtualServer.create()")
        logger.info("=" * 50)
        return 0
    else:
        logger.error("❌ Ошибка при инициализации базы данных")
        logger.error("Проверьте логи выше для детальной информации")
        return 1


def quick_test():
    """
    Быстрый тест для проверки работы всех модулей.
    Запускается при передаче аргумента --test
    """
    logger.info("🧪 Запуск быстрого тестирования...")
    
    try:
        from config.database import get_connection
        from models.client import Client
        from models.vm_status import VMStatus
        from models.resource_price import ResourcePrice
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Проверяем создание клиента
        logger.info("Тест 1/3: Создание тестового клиента...")
        client_id = Client.create(cursor, "Тестовый клиент")
        logger.info(f"  ✅ Клиент создан с ID: {client_id}")
        
        # Проверяем получение статусов
        logger.info("Тест 2/3: Получение списка статусов...")
        statuses = VMStatus.get_all_statuses(cursor)
        logger.info(f"  ✅ Найдено статусов: {len(statuses)}")
        for status in statuses:
            logger.info(f"     - {status['code']}: {status['name']}")
        
        # Проверяем получение цен
        logger.info("Тест 3/3: Получение текущих цен...")
        prices = ResourcePrice.get_current_prices(cursor)
        if prices:
            logger.info(f"  ✅ Цены на {prices['effective_from']}:")
            logger.info(f"     CPU: {prices['cpu_price_per_core']} за ядро")
            logger.info(f"     RAM: {prices['ram_price_per_gb']} за ГБ")
            logger.info(f"     NVME: {prices['nvme_price_per_gb']} за ГБ")
            logger.info(f"     HDD: {prices['hdd_price_per_gb']} за ГБ")
        else:
            logger.warning("  ⚠️ Цены не найдены")
        
        # Откатываем изменения (чтобы не засорять БД)
        conn.rollback()
        cursor.close()
        conn.close()
        
        logger.info("✅ Все тесты пройдены успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}")
        return False


if __name__ == "__main__":
    # Обработка аргументов командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # Режим тестирования
            quick_test()
            sys.exit(0)
        elif sys.argv[1] == "--help":
            print("Использование: python run.py [опции]")
            print("Опции:")
            print("  --test    Запустить быстрый тест всех модулей")
            print("  --help    Показать эту справку")
            sys.exit(0)
    
    # Обычный режим - инициализация БД
    sys.exit(main())