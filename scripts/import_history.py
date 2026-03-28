#!/usr/bin/env python3
"""
Скрипт для импорта исторических данных из CSV-файла.
Поддерживает dry-run, force, skip-existing режимы.
"""

import sys
import os
import argparse
import csv
from datetime import datetime, date
from collections import defaultdict
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.append(str(Path(__file__).parent.parent))

from config.database import get_connection
from models.client import Client
from models.virtual_server import VirtualServer
from models.daily_billing import DailyBilling
from models.vm_status import VMStatus
from utils.logger import get_logger

logger = get_logger('ImportHistory')


def parse_date(date_str: str) -> date:
    """Парсит дату из строки YYYY-MM-DD"""
    try:
        return datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f"Неверный формат даты: {date_str}. Ожидается YYYY-MM-DD")


def get_or_create_client(cursor, client_name: str, dry_run: bool) -> int:
    """Получить ID клиента или создать нового"""
    cursor.execute("SELECT id FROM clients WHERE name = %s", (client_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    if dry_run:
        logger.info(f"  [DRY-RUN] Будет создан клиент: {client_name}")
        return -1
    
    client_id = Client.create(cursor, client_name)
    logger.info(f"  Создан новый клиент: {client_name} (ID: {client_id})")
    return client_id


def get_or_create_server(cursor, client_id: int, server_name: str, first_date: date, last_date: date, dry_run: bool) -> int:
    """Получить ID сервера или создать новый"""
    cursor.execute(
        "SELECT id, start_date, stop_date FROM virtual_servers WHERE client_id = %s AND name = %s",
        (client_id, server_name)
    )
    row = cursor.fetchone()
    if row:
        server_id = row[0]
        # Обновляем даты, если нужно
        if row[1] is None or row[1] > first_date:
            if not dry_run:
                cursor.execute(
                    "UPDATE virtual_servers SET start_date = %s WHERE id = %s",
                    (first_date, server_id)
                )
                logger.debug(f"  Обновлена start_date сервера {server_name}: {first_date}")
        return server_id
    
    if dry_run:
        logger.info(f"  [DRY-RUN] Будет создан сервер: {server_name} для клиента ID {client_id}")
        return -1
    
    # Получаем статус "active"
    active_status_id = VMStatus.get_status_id_by_code(cursor, 'active')
    if not active_status_id:
        cursor.execute("SELECT id FROM vm_statuses WHERE code = 'active'")
        row = cursor.fetchone()
        active_status_id = row[0] if row else 1
    
    server_dict = {
        'name': server_name,
        'client_id': client_id,
        'physical_server_id': 1,  # Временный хост, можно изменить позже
        'status_id': active_status_id,
        'purpose': 'imported',
        'os': 'imported',
        'cpu_cores': 1,  # Временное значение
        'ram_gb': 1,
        'nvme1_gb': 0,
        'nvme2_gb': 0,
        'nvme3_gb': 0,
        'nvme4_gb': 0,
        'nvme5_gb': 0,
        'hdd_gb': 0,
        'start_date': first_date,
        'stop_date': last_date if last_date < date.today() else None
    }
    
    server_id = VirtualServer.create(cursor, **server_dict)
    logger.info(f"  Создан новый сервер: {server_name} (ID: {server_id})")
    return server_id


def row_exists(cursor, server_id: int, billing_date: date) -> bool:
    """Проверяет, существует ли запись в daily_billing"""
    cursor.execute(
        "SELECT id FROM daily_billing WHERE vm_id = %s AND billing_date = %s",
        (server_id, billing_date)
    )
    return cursor.fetchone() is not None


def delete_existing(cursor, server_id: int, billing_date: date) -> None:
    """Удаляет существующую запись в daily_billing"""
    cursor.execute(
        "DELETE FROM daily_billing WHERE vm_id = %s AND billing_date = %s",
        (server_id, billing_date)
    )


def insert_daily_billing(cursor, row_data: dict, dry_run: bool) -> bool:
    """Вставляет запись в daily_billing"""
    if dry_run:
        return True
    
    try:
        cursor.execute("""
            INSERT INTO daily_billing 
            (billing_date, vm_id, client_id, cpu_cores, ram_gb, 
             nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb,
             cpu_price, ram_price, nvme_price, hdd_price,
             cpu_cost, ram_cost, nvme_cost, hdd_cost, total_cost)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row_data['date'],
            row_data['server_id'],
            row_data['client_id'],
            row_data['cpu_cores'],
            row_data['ram_gb'],
            row_data.get('nvme1_gb', 0),
            row_data.get('nvme2_gb', 0),
            row_data.get('nvme3_gb', 0),
            row_data.get('nvme4_gb', 0),
            row_data.get('nvme5_gb', 0),
            row_data.get('hdd_gb', 0),
            row_data['price_cpu'],
            row_data['price_ram'],
            row_data['price_nvme'],
            row_data['price_hdd'],
            row_data['cpu_cost'],
            row_data['ram_cost'],
            row_data['nvme_cost'],
            row_data['hdd_cost'],
            row_data['total_cost']
        ))
        return True
    except Exception as e:
        logger.error(f"Ошибка вставки: {e}")
        return False


def validate_row(row: dict, row_num: int) -> dict:
    """Валидирует и преобразует строку CSV"""
    errors = []
    
    # Обязательные поля
    required = ['date', 'server_name', 'client_name', 'cpu_cores', 'ram_gb',
                'price_cpu', 'price_ram', 'price_nvme', 'price_hdd',
                'cpu_cost', 'ram_cost', 'nvme_cost', 'hdd_cost', 'total_cost']
    
    for field in required:
        if field not in row or not row[field]:
            errors.append(f"Отсутствует поле: {field}")
    
    if errors:
        raise ValueError(f"Строка {row_num}: {', '.join(errors)}")
    
    # Парсим дату
    try:
        billing_date = parse_date(row['date'])
    except ValueError as e:
        raise ValueError(f"Строка {row_num}: {e}")
    
    # Преобразуем числовые поля
    result = {
        'date': billing_date,
        'server_name': row['server_name'].strip(),
        'client_name': row['client_name'].strip(),
        'cpu_cores': int(row['cpu_cores']),
        'ram_gb': int(row['ram_gb']),
        'nvme1_gb': int(row.get('nvme1_gb', 0)),
        'nvme2_gb': int(row.get('nvme2_gb', 0)),
        'nvme3_gb': int(row.get('nvme3_gb', 0)),
        'nvme4_gb': int(row.get('nvme4_gb', 0)),
        'nvme5_gb': int(row.get('nvme5_gb', 0)),
        'hdd_gb': int(row.get('hdd_gb', 0)),
        'price_cpu': float(row['price_cpu']),
        'price_ram': float(row['price_ram']),
        'price_nvme': float(row['price_nvme']),
        'price_hdd': float(row['price_hdd']),
        'cpu_cost': float(row['cpu_cost']),
        'ram_cost': float(row['ram_cost']),
        'nvme_cost': float(row['nvme_cost']),
        'hdd_cost': float(row['hdd_cost']),
        'total_cost': float(row['total_cost'])
    }
    
    return result


def analyze_csv(filepath: str):
    """Анализирует CSV и возвращает статистику"""
    stats = {
        'total_rows': 0,
        'min_date': None,
        'max_date': None,
        'clients': set(),
        'servers': set(),
        'sample_rows': []
    }
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            stats['total_rows'] += 1
            try:
                validated = validate_row(row, i + 2)
                stats['clients'].add(validated['client_name'])
                stats['servers'].add(f"{validated['client_name']}|{validated['server_name']}")
                if stats['min_date'] is None or validated['date'] < stats['min_date']:
                    stats['min_date'] = validated['date']
                if stats['max_date'] is None or validated['date'] > stats['max_date']:
                    stats['max_date'] = validated['date']
                if len(stats['sample_rows']) < 5:
                    stats['sample_rows'].append(validated)
            except ValueError as e:
                logger.warning(f"Ошибка в строке {i+2}: {e}")
    
    return stats


def import_csv(filepath: str, dry_run: bool, force: bool, skip_existing: bool):
    """Основная функция импорта"""
    logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Начало импорта из файла: {filepath}")
    
    # Анализ CSV
    logger.info("Анализ CSV-файла...")
    stats = analyze_csv(filepath)
    
    logger.info("=" * 50)
    logger.info("СТАТИСТИКА CSV:")
    logger.info(f"  Всего строк: {stats['total_rows']}")
    logger.info(f"  Диапазон дат: {stats['min_date']} — {stats['max_date']}")
    logger.info(f"  Уникальных клиентов: {len(stats['clients'])}")
    logger.info(f"  Уникальных серверов: {len(stats['servers'])}")
    logger.info("  Пример первых 5 строк:")
    for row in stats['sample_rows']:
        logger.info(f"    {row['date']} | {row['client_name']} | {row['server_name']} | {row['total_cost']:.2f}")
    logger.info("=" * 50)
    
    if dry_run:
        logger.info("Режим DRY-RUN: изменения не будут внесены в БД")
        return
    
    # Реальный импорт
    conn = get_connection()
    cursor = conn.cursor()
    
    # Словари для кэширования ID
    client_cache = {}
    server_cache = {}
    server_dates = defaultdict(lambda: {'first': None, 'last': None})
    
    # Первый проход: собираем даты для серверов
    logger.info("Проход 1/2: Сбор дат для серверов...")
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            try:
                validated = validate_row(row, i + 2)
                key = f"{validated['client_name']}|{validated['server_name']}"
                if server_dates[key]['first'] is None or validated['date'] < server_dates[key]['first']:
                    server_dates[key]['first'] = validated['date']
                if server_dates[key]['last'] is None or validated['date'] > server_dates[key]['last']:
                    server_dates[key]['last'] = validated['date']
            except ValueError as e:
                logger.warning(f"Пропуск строки {i+2}: {e}")
    
    # Второй проход: создаём клиентов и серверы
    logger.info("Проход 2/2: Импорт данных...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        total_inserted = 0
        total_skipped = 0
        
        for i, row in enumerate(reader):
            try:
                validated = validate_row(row, i + 2)
                key = f"{validated['client_name']}|{validated['server_name']}"
                
                # Получаем или создаём клиента
                if validated['client_name'] not in client_cache:
                    client_id = get_or_create_client(cursor, validated['client_name'], dry_run)
                    client_cache[validated['client_name']] = client_id
                else:
                    client_id = client_cache[validated['client_name']]
                
                if client_id == -1:
                    continue  # dry-run
                
                # Получаем или создаём сервер
                if key not in server_cache:
                    first_date = server_dates[key]['first']
                    last_date = server_dates[key]['last']
                    server_id = get_or_create_server(cursor, client_id, validated['server_name'], 
                                                      first_date, last_date, dry_run)
                    server_cache[key] = server_id
                else:
                    server_id = server_cache[key]
                
                if server_id == -1:
                    continue  # dry-run
                
                validated['client_id'] = client_id
                validated['server_id'] = server_id
                
                # Проверяем существование записи
                exists = row_exists(cursor, server_id, validated['date'])
                
                if exists and skip_existing:
                    logger.debug(f"Пропуск: сервер {validated['server_name']}, дата {validated['date']} (уже существует)")
                    total_skipped += 1
                    continue
                elif exists and force:
                    delete_existing(cursor, server_id, validated['date'])
                    if insert_daily_billing(cursor, validated, dry_run):
                        total_inserted += 1
                elif exists:
                    logger.warning(f"Запись существует: сервер {validated['server_name']}, дата {validated['date']}. "
                                   f"Используйте --force для перезаписи или --skip-existing для пропуска")
                    total_skipped += 1
                else:
                    if insert_daily_billing(cursor, validated, dry_run):
                        total_inserted += 1
                
                # Логирование прогресса
                if (i + 1) % 1000 == 0:
                    logger.info(f"  Обработано {i+1} строк...")
                    conn.commit()
                
            except ValueError as e:
                logger.error(f"Ошибка в строке {i+2}: {e}")
                continue
            except Exception as e:
                logger.error(f"Неожиданная ошибка в строке {i+2}: {e}")
                continue
        
        conn.commit()
    
    logger.info("=" * 50)
    logger.info("ИМПОРТ ЗАВЕРШЁН")
    logger.info(f"  Вставлено записей: {total_inserted}")
    logger.info(f"  Пропущено записей: {total_skipped}")
    logger.info(f"  Создано клиентов: {len(client_cache)}")
    logger.info(f"  Создано серверов: {len(server_cache)}")
    logger.info("=" * 50)
    
    cursor.close()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Импорт исторических данных из CSV')
    parser.add_argument('--csv', required=True, help='Путь к CSV-файлу')
    parser.add_argument('--dry-run', action='store_true', help='Режим проверки без внесения изменений')
    parser.add_argument('--force', action='store_true', help='Перезаписывать существующие записи')
    parser.add_argument('--skip-existing', action='store_true', help='Пропускать существующие записи')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv):
        logger.error(f"Файл не найден: {args.csv}")
        sys.exit(1)
    
    if args.force and args.skip_existing:
        logger.error("Нельзя использовать --force и --skip-existing одновременно")
        sys.exit(1)
    
    import_csv(args.csv, args.dry_run, args.force, args.skip_existing)


if __name__ == '__main__':
    main()
