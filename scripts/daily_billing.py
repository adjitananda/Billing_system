#!/usr/bin/env python3
"""
Скрипт для ежедневного расчёта биллинга в дата-центре.
Поддерживает запуск за указанную дату, вчерашний день или сегодня.
С проверкой дубликатов и режимом dry-run.
"""

import argparse
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# Добавляем путь к проекту для импортов
sys.path.insert(0, '/home/billing/billing_system')

from config.database import get_connection
from utils.logger import logger


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Ежедневный расчёт биллинга для дата-центра',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s                        # расчёт за сегодня
  %(prog)s --date 2025-03-22      # расчёт за указанную дату
  %(prog)s --yesterday            # расчёт за вчерашний день
  %(prog)s --date 2025-03-22 --force  # принудительная перезапись
  %(prog)s --date 2025-03-22 --dry-run  # режим просмотра
        """
    )
    
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        '--date',
        type=str,
        help='Дата расчёта в формате YYYY-MM-DD'
    )
    date_group.add_argument(
        '--yesterday',
        action='store_true',
        help='Рассчитать за вчерашний день'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Принудительно перезаписать существующие записи'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Режим просмотра (без внесения изменений в БД)'
    )
    
    return parser.parse_args()


def get_target_date(args):
    """Определяет дату расчёта на основе аргументов"""
    if args.date:
        try:
            datetime.strptime(args.date, '%Y-%m-%d')
            return args.date
        except ValueError:
            logger.error(f"Неверный формат даты: {args.date}. Ожидается YYYY-MM-DD")
            sys.exit(1)
    elif args.yesterday:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        logger.info(f"Расчёт за вчерашний день: {target_date}")
        return target_date
    else:
        target_date = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"Расчёт за сегодня: {target_date}")
        return target_date


def get_active_servers_on_date(conn, target_date):
    """
    Получает список активных серверов на указанную дату.
    Возвращает список словарей с данными серверов.
    """
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT vs.* FROM virtual_servers vs
        JOIN vm_statuses s ON vs.status_id = s.id
        WHERE s.code = 'active'
          AND vs.start_date <= %s
          AND (vs.stop_date IS NULL OR vs.stop_date > %s)
    """, (target_date, target_date))
    servers = cursor.fetchall()
    logger.info(f"Найдено активных серверов на {target_date}: {len(servers)}")
    return servers


def check_existing_records(conn, target_date):
    """Проверяет наличие записей за указанную дату"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM daily_billing WHERE billing_date = %s",
        (target_date,)
    )
    count = cursor.fetchone()[0]
    return count > 0, count


def delete_existing_records(conn, target_date):
    """Удаляет существующие записи за указанную дату"""
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM daily_billing WHERE billing_date = %s",
        (target_date,)
    )
    deleted = cursor.rowcount
    conn.commit()
    logger.info(f"Удалено существующих записей за {target_date}: {deleted}")
    return deleted


def get_config_on_date(conn, vm_id, target_date):
    """
    Получает конфигурацию сервера на указанную дату.
    Сначала ищет в истории изменений, затем в основной таблице.
    """
    cursor = conn.cursor(dictionary=True)
    
    # Ищем в истории изменений
    cursor.execute("""
        SELECT * FROM vm_config_history
        WHERE vm_id = %s AND effective_from <= %s
        ORDER BY effective_from DESC LIMIT 1
    """, (vm_id, target_date))
    config = cursor.fetchone()
    
    if config:
        logger.debug(f"VM {vm_id}: конфигурация из истории от {config['effective_from']}")
        return config
    
    # Берём из основной таблицы
    cursor.execute(
        "SELECT * FROM virtual_servers WHERE id = %s",
        (vm_id,)
    )
    config = cursor.fetchone()
    if config:
        logger.debug(f"VM {vm_id}: конфигурация из основной таблицы")
        return config
    
    logger.warning(f"VM {vm_id}: конфигурация не найдена")
    return None


def get_prices_on_date(conn, target_date):
    """Получает актуальные цены на указанную дату"""
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM resource_prices
        WHERE effective_from <= %s
        ORDER BY effective_from DESC LIMIT 1
    """, (target_date,))
    prices = cursor.fetchone()
    
    if not prices:
        logger.error(f"Цены на ресурсы не найдены для даты {target_date}")
        return None
    
    logger.info(f"Используются цены от {prices['effective_from']}")
    return prices


def calculate_total_nvme(config):
    """Рассчитывает общий объём NVMe из всех пяти дисков"""
    nvme_total = 0
    for i in range(1, 6):
        nvme_total += config.get(f'nvme{i}_gb', 0)
    return nvme_total


def calculate_costs(config, prices):
    """Рассчитывает стоимости на основе конфигурации и цен"""
    nvme_total = calculate_total_nvme(config)
    
    cpu_cost = Decimal(config['cpu_cores']) * Decimal(prices['cpu_price_per_core'])
    ram_cost = Decimal(config['ram_gb']) * Decimal(prices['ram_price_per_gb'])
    nvme_cost = Decimal(nvme_total) * Decimal(prices['nvme_price_per_gb'])
    hdd_cost = Decimal(config.get('hdd_gb', 0)) * Decimal(prices['hdd_price_per_gb'])
    total_cost = cpu_cost + ram_cost + nvme_cost + hdd_cost
    
    return {
        'cpu_cost': cpu_cost,
        'ram_cost': ram_cost,
        'nvme_cost': nvme_cost,
        'hdd_cost': hdd_cost,
        'total_cost': total_cost,
        'nvme_total': nvme_total
    }


def insert_billing_record(conn, vm, config, prices, costs, target_date):
    """Вставляет запись биллинга в базу данных"""
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO daily_billing (
            billing_date, vm_id, client_id,
            cpu_cores, ram_gb,
            nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb,
            cpu_price, ram_price, nvme_price, hdd_price,
            cpu_cost, ram_cost, nvme_cost, hdd_cost, total_cost
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        target_date, vm['id'], vm['client_id'],
        config['cpu_cores'], config['ram_gb'],
        config.get('nvme1_gb', 0), config.get('nvme2_gb', 0),
        config.get('nvme3_gb', 0), config.get('nvme4_gb', 0),
        config.get('nvme5_gb', 0), config.get('hdd_gb', 0),
        prices['cpu_price_per_core'], prices['ram_price_per_gb'],
        prices['nvme_price_per_gb'], prices['hdd_price_per_gb'],
        costs['cpu_cost'], costs['ram_cost'], costs['nvme_cost'],
        costs['hdd_cost'], costs['total_cost']
    ))
    
    return costs['total_cost']


def main():
    """Основная функция скрипта"""
    logger.info("=" * 60)
    logger.info("Запуск скрипта ежедневного расчёта биллинга")
    
    # Парсим аргументы
    args = parse_arguments()
    target_date = get_target_date(args)
    
    logger.info(f"Параметры запуска: дата={target_date}, force={args.force}, dry_run={args.dry_run}")
    
    # Подключаемся к БД
    try:
        conn = get_connection()
        logger.info("Подключение к базе данных установлено")
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        sys.exit(1)
    
    try:
        # Проверяем существующие записи
        has_records, count = check_existing_records(conn, target_date)
        
        if has_records:
            if not args.force:
                logger.warning(f"Записи за {target_date} уже существуют ({count} шт.)")
                logger.warning("Используйте --force для принудительной перезаписи")
                return
            elif not args.dry_run:
                logger.info(f"Найдены существующие записи за {target_date}, удаляем...")
                delete_existing_records(conn, target_date)
            else:
                logger.info(f"[DRY RUN] Будет удалено {count} существующих записей за {target_date}")
        
        # Получаем активные серверы
        servers = get_active_servers_on_date(conn, target_date)
        
        if not servers:
            logger.info(f"Нет активных серверов на {target_date}")
            return
        
        # Получаем цены
        prices = get_prices_on_date(conn, target_date)
        if not prices:
            logger.error("Невозможно продолжить: цены не найдены")
            return
        
        # Обрабатываем каждый сервер
        processed = 0
        skipped = 0
        total_sum = Decimal('0')
        
        for vm in servers:
            # Получаем конфигурацию
            config = get_config_on_date(conn, vm['id'], target_date)
            if not config:
                logger.warning(f"Пропускаем VM {vm['id']}: конфигурация не найдена")
                skipped += 1
                continue
            
            # Рассчитываем стоимости
            costs = calculate_costs(config, prices)
            
            if args.dry_run:
                logger.info(f"[DRY RUN] VM {vm['id']} (client {vm['client_id']}): "
                          f"CPU={config['cpu_cores']}, RAM={config['ram_gb']}, "
                          f"NVMe={costs['nvme_total']}, HDD={config.get('hdd_gb', 0)}, "
                          f"сумма={costs['total_cost']}")
                processed += 1
                total_sum += costs['total_cost']
            else:
                total = insert_billing_record(conn, vm, config, prices, costs, target_date)
                total_sum += total
                processed += 1
                
                if processed % 10 == 0:
                    logger.info(f"Обработано серверов: {processed}")
        
        if not args.dry_run:
            conn.commit()
            logger.info(f"Создано записей: {processed}")
            if skipped > 0:
                logger.warning(f"Пропущено серверов: {skipped}")
            logger.info(f"Общая сумма за {target_date}: {total_sum:.2f}")
        else:
            logger.info(f"[DRY RUN] Будет создано записей: {processed}")
            if skipped > 0:
                logger.info(f"[DRY RUN] Будет пропущено серверов: {skipped}")
            logger.info(f"[DRY RUN] Общая сумма составит: {total_sum:.2f}")
        
        logger.info("Расчёт завершён успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении расчёта: {e}")
        if not args.dry_run:
            conn.rollback()
        raise
    finally:
        conn.close()
        logger.info("Соединение с БД закрыто")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()