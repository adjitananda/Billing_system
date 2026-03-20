#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для заполнения БД тестовыми данными.
Запуск: python scripts/seed.py

Порядок заполнения (с учетом внешних ключей):
1. clients
2. physical_servers
3. vm_statuses (уже есть из insert_default_data)
4. virtual_servers
5. resource_prices (дополнительные записи)
6. vm_config_history
7. daily_billing
"""

import sys
import random
from datetime import datetime, timedelta
from decimal import Decimal

# Добавляем путь к корню проекта для импорта модулей
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from config.database import get_connection
from models.client import Client
from models.physical_server import PhysicalServer
from models.vm_status import VMStatus
from models.virtual_server import VirtualServer
from models.vm_config_history import VMConfigHistory
from models.resource_price import ResourcePrice
from models.daily_billing import DailyBilling
from utils.logger import get_logger

logger = get_logger('Seed')

# Константы для генерации данных
NUM_CLIENTS = 7
NUM_PHYSICAL_SERVERS = 4
NUM_VIRTUAL_SERVERS = 20
START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 3, 31)

# Списки для хранения созданных ID
client_ids = []
physical_server_ids = []
status_ids = {}
virtual_server_ids = []
resource_price_ids = []


def confirm_cleanup():
    """Запрашивает подтверждение на очистку базы данных."""
    print("\n" + "="*60)
    print("⚠️  ВНИМАНИЕ! Все существующие тестовые данные будут удалены!")
    print("="*60)
    response = input("Продолжить? (y/n): ").lower().strip()
    return response == 'y' or response == 'yes'


def cleanup_database(cursor):
    """
    Очищает все таблицы в правильном порядке (с учетом внешних ключей).
    Порядок: зависимые таблицы удаляются первыми.
    """
    logger.warning("Очистка существующих данных...")
    
    tables_in_order = [
        'daily_billing',
        'vm_config_history',
        'virtual_servers',
        'resource_prices',
        'vm_statuses',
        'physical_servers',
        'clients'
    ]
    
    # Отключаем проверку внешних ключей
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    
    for table in tables_in_order:
        logger.info(f"Очистка таблицы {table}...")
        cursor.execute(f"DELETE FROM {table}")
    
    # Включаем обратно проверку внешних ключей
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    
    logger.info("✅ Очистка завершена")


def seed_clients(cursor):
    """Создает тестовых клиентов."""
    logger.info("="*50)
    logger.info("Создание клиентов...")
    
    client_names = [
        "ООО Ромашка",
        "ИП Иванов А.А.",
        "ООО ТехноСервис",
        "ЗАО МедиаГрупп",
        "АО ФинансТраст",
        "ООО Облачные решения",
        "ИП Петрова Е.В.",
    ]
    
    count = 0
    for name in client_names[:NUM_CLIENTS]:
        try:
            client_id = Client.create(cursor, name=name)
            if client_id:
                client_ids.append(client_id)
                count += 1
                logger.debug(f"  Создан клиент: {name} (ID: {client_id})")
        except Exception as e:
            logger.error(f"Ошибка при создании клиента {name}: {e}")
    
    logger.info(f"✅ Создано клиентов: {count}")
    return count


def seed_physical_servers(cursor):
    """Создает тестовые физические серверы."""
    logger.info("="*50)
    logger.info("Создание физических серверов...")
    
    servers_data = [
        {"name": "Host-01", "cores": 32, "ram": 128, "nvme": 2000, "sata": 4000},
        {"name": "Host-02", "cores": 48, "ram": 256, "nvme": 4000, "sata": 8000},
        {"name": "Host-03", "cores": 24, "ram": 64, "nvme": 1000, "sata": 2000},
        {"name": "Host-04", "cores": 40, "ram": 192, "nvme": 3000, "sata": 6000}
    ]
    
    count = 0
    for server in servers_data[:NUM_PHYSICAL_SERVERS]:
        try:
            server_id = PhysicalServer.create(
                cursor,
                name=server["name"],
                total_cores=server["cores"],
                total_ram_gb=server["ram"],
                total_nvme_gb=server["nvme"],
                total_sata_gb=server["sata"],
                notes=f"Физический сервер для тестирования"
            )
            if server_id:
                physical_server_ids.append(server_id)
                count += 1
                logger.debug(f"  Создан сервер: {server['name']}")
        except Exception as e:
            logger.error(f"Ошибка при создании сервера {server['name']}: {e}")
    
    logger.info(f"✅ Создано физических серверов: {count}")
    return count


def get_status_ids(cursor):
    """Получает ID статусов из базы данных."""
    global status_ids
    
    try:
        statuses = VMStatus.get_all_statuses(cursor)
        for status in statuses:
            status_ids[status['code']] = status['id']
        logger.debug(f"Получены ID статусов: {status_ids}")
    except Exception as e:
        logger.error(f"Ошибка при получении статусов: {e}")

def ensure_statuses(cursor):
    """Гарантирует наличие статусов в базе данных."""
    logger.info("Проверка наличия статусов ВМ...")
    
    # Проверяем, есть ли статусы
    cursor.execute("SELECT COUNT(*) FROM vm_statuses")
    count = cursor.fetchone()[0]
    
    if count == 0:
        logger.info("Статусы не найдены, создаем...")
        from models.vm_status import VMStatus
        VMStatus.insert_default_data(cursor)
    
    # Получаем ID статусов
    get_status_ids(cursor)

def random_date(start, end):
    """Генерирует случайную дату между start и end."""
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + timedelta(days=random_days)


def seed_virtual_servers(cursor):
    """Создает тестовые виртуальные серверы."""
    logger.info("="*50)
    logger.info("Создание виртуальных серверов...")
    
    if not client_ids or not physical_server_ids or not status_ids:
        logger.error("Не хватает данных для создания виртуальных серверов")
        return 0
    
    # Возможные назначения и ОС
    purposes = ["AD", "FS", "APP", "TS", "Router", "DB", "Web", "Mail", "Backup", "Monitoring"]
    os_list = ["Ubuntu 22.04", "Ubuntu 20.04", "Debian 12", "CentOS 9", "Windows Server 2022", "Windows Server 2019"]
    
    count = 0
    
    for i in range(NUM_VIRTUAL_SERVERS):
        try:
            # Выбираем случайные ID
            client_id = random.choice(client_ids)
            physical_server_id = random.choice(physical_server_ids)
            
            # Статус с весами: active - 60%, draft - 20%, deleted - 20%
            status_choice = random.choices(
                ['active', 'draft', 'deleted'],
                weights=[60, 20, 20]
            )[0]
            status_id = status_ids[status_choice]
            
            # Генерируем даты
            created_date = random_date(START_DATE, END_DATE - timedelta(days=30))
            
            if status_choice == 'draft':
                # Для черновиков start_date в будущем
                start_date = random_date(END_DATE + timedelta(days=1), END_DATE + timedelta(days=60))
                stop_date = None
            else:
                start_date = created_date
                if status_choice == 'deleted':
                    # Для удаленных - stop_date через 1-60 дней после start_date
                    days_active = random.randint(1, 60)
                    stop_date = start_date + timedelta(days=days_active)
                    if stop_date > END_DATE:
                        stop_date = END_DATE
                else:
                    # Для активных - stop_date None
                    stop_date = None
            
            # Генерируем ресурсы
            cpu_cores = random.choice([2, 4, 8, 12, 16])
            ram_gb = random.choice([4, 8, 16, 32, 64])
            
            # NVME диски (0-3 диска)
            nvme_config = {
                'nvme1_gb': random.choice([0, 100, 200, 500]) if random.random() > 0.3 else 0,
                'nvme2_gb': random.choice([0, 100, 200, 500]) if random.random() > 0.6 else 0,
                'nvme3_gb': random.choice([0, 100, 200]) if random.random() > 0.8 else 0,
                'nvme4_gb': 0,
                'nvme5_gb': 0
            }
            
            hdd_gb = random.choice([0, 500, 1000, 2000]) if random.random() > 0.4 else 0
            
            # Генерируем IP и домен
            ip_address = f"10.0.{random.randint(1, 254)}.{random.randint(1, 254)}"
            domain_address = f"vm{random.randint(100, 999)}.test.local" if random.random() > 0.5 else None
            
            # Создаем сервер
            server_id = VirtualServer.create(
                cursor,
                name=f"vm-{i+1:03d}",
                client_id=client_id,
                physical_server_id=physical_server_id,
                status_id=status_id,
                purpose=random.choice(purposes),
                os=random.choice(os_list),
                ip_address=ip_address,
                ip_port=22,
                domain_address=domain_address,
                domain_port=443 if domain_address else None,
                cpu_cores=cpu_cores,
                ram_gb=ram_gb,
                nvme1_gb=nvme_config['nvme1_gb'],
                nvme2_gb=nvme_config['nvme2_gb'],
                nvme3_gb=nvme_config['nvme3_gb'],
                nvme4_gb=0,
                nvme5_gb=0,
                hdd_gb=hdd_gb,
                start_date=start_date.date() if start_date else None,
                stop_date=stop_date.date() if stop_date else None
            )
            
            if server_id:
                virtual_server_ids.append({
                    'id': server_id,
                    'client_id': client_id,
                    'status': status_choice,
                    'start_date': start_date,
                    'stop_date': stop_date,
                    'cpu_cores': cpu_cores,
                    'ram_gb': ram_gb,
                    'nvme_config': nvme_config,
                    'hdd_gb': hdd_gb
                })
                count += 1
                
                if i < 5:  # Логируем первые 5 для примера
                    status_ru = "Активен" if status_choice == 'active' else "Черновик" if status_choice == 'draft' else "Удален"
                    logger.debug(f"  Создана ВМ: vm-{i+1:03d} ({status_ru}, {cpu_cores} ядер, {ram_gb} GB RAM)")
                    
        except Exception as e:
            logger.error(f"Ошибка при создании ВМ {i+1}: {e}")
    
    logger.info(f"✅ Создано виртуальных серверов: {count}")
    return count


def seed_resource_prices(cursor):
    """Добавляет дополнительные записи цен на ресурсы."""
    logger.info("="*50)
    logger.info("Создание дополнительных записей цен...")
    
    price_changes = [
        {
            'date': datetime(2025, 2, 1).date(),
            'cpu': Decimal('55.0000'),
            'ram': Decimal('11.0000'),
            'nvme': Decimal('0.5500'),
            'hdd': Decimal('0.2750')
        },
        {
            'date': datetime(2025, 3, 1).date(),
            'cpu': Decimal('55.0000'),
            'ram': Decimal('11.0000'),
            'nvme': Decimal('0.4500'),
            'hdd': Decimal('0.2000')
        }
    ]
    
    count = 0
    for price in price_changes:
        try:
            # Проверяем, нет ли уже записи на эту дату
            cursor.execute(
                "SELECT id FROM resource_prices WHERE effective_from = %s",
                (price['date'],)
            )
            if cursor.fetchone():
                logger.debug(f"  Цены на {price['date']} уже существуют, пропускаем")
                continue
            
            price_id = ResourcePrice.create(
                cursor,
                effective_from=price['date'],
                cpu_price=price['cpu'],
                ram_price=price['ram'],
                nvme_price=price['nvme'],
                hdd_price=price['hdd']
            )
            if price_id:
                resource_price_ids.append(price_id)
                count += 1
                logger.debug(f"  Добавлены цены на {price['date']}")
        except Exception as e:
            logger.error(f"Ошибка при создании цен на {price['date']}: {e}")
    
    logger.info(f"✅ Добавлено записей цен: {count}")
    return count


def seed_vm_config_history(cursor):
    """Создает историю изменений конфигураций для части серверов."""
    logger.info("="*50)
    logger.info("Создание истории изменений конфигураций...")
    
    if not virtual_server_ids:
        logger.warning("Нет виртуальных серверов для создания истории")
        return 0
    
    # Выбираем 5-7 серверов для истории (активные или удаленные)
    history_candidates = [
        v for v in virtual_server_ids 
        if v['status'] in ['active', 'deleted'] and v['start_date'] < END_DATE
    ]
    
    if not history_candidates:
        logger.warning("Нет подходящих серверов для истории")
        return 0
    
    selected_servers = random.sample(
        history_candidates, 
        min(7, len(history_candidates))
    )
    
    count = 0
    for server in selected_servers:
        try:
            # Определяем период для изменений
            start = server['start_date']
            end = server['stop_date'] if server['stop_date'] else END_DATE
            
            if (end - start).days < 30:
                # Сервер живет меньше месяца - одно изменение
                num_changes = 1
            else:
                # 1-3 изменения
                num_changes = random.randint(1, 3)
            
            current_config = {
                'cpu_cores': server['cpu_cores'],
                'ram_gb': server['ram_gb'],
                'nvme1_gb': server['nvme_config']['nvme1_gb'],
                'nvme2_gb': server['nvme_config']['nvme2_gb'],
                'nvme3_gb': server['nvme_config']['nvme3_gb'],
                'nvme4_gb': 0,
                'nvme5_gb': 0,
                'hdd_gb': server['hdd_gb']
            }
            
            for change_num in range(num_changes):
                # Дата изменения (не ранее чем через 7 дней после старта)
                min_change_date = start + timedelta(days=7)
                max_change_date = end - timedelta(days=7)
                
                if min_change_date >= max_change_date:
                    continue
                
                change_date = random_date(min_change_date, max_change_date)
                
                # Модифицируем конфигурацию
                new_config = current_config.copy()
                
                # Что меняем?
                change_type = random.choice(['cpu', 'ram', 'nvme', 'hdd', 'multiple'])
                
                if change_type == 'cpu' or change_type == 'multiple':
                    new_config['cpu_cores'] = current_config['cpu_cores'] + random.choice([2, 4])
                
                if change_type == 'ram' or change_type == 'multiple':
                    new_config['ram_gb'] = current_config['ram_gb'] + random.choice([8, 16])
                
                if change_type == 'nvme' or change_type == 'multiple':
                    # Добавляем NVME диск
                    for i in range(1, 4):
                        if new_config[f'nvme{i}_gb'] == 0 and random.random() > 0.3:
                            new_config[f'nvme{i}_gb'] = random.choice([100, 200, 500])
                            break
                
                if change_type == 'hdd' or change_type == 'multiple':
                    if new_config['hdd_gb'] == 0:
                        new_config['hdd_gb'] = random.choice([500, 1000])
                    else:
                        new_config['hdd_gb'] += random.choice([500, 1000])
                
                # СОЗДАЕМ ЗАПИСЬ ИСТОРИИ
                history_id = VMConfigHistory.save_config_snapshot(
                    cursor,
                    vm_id=server['id'],
                    effective_from=change_date.date()
                )
                
                if history_id:
                    count += 1
                    current_config = new_config
                    logger.debug(f"  ВМ {server['id']}: изменение {change_num+1} на {change_date.date()}")
            
        except Exception as e:
            logger.error(f"Ошибка при создании истории для ВМ {server['id']}: {e}")
    
    logger.info(f"✅ Создано записей истории: {count}")
    return count


def get_config_at_date(server, target_date, cursor):
    """
    Определяет конфигурацию сервера на указанную дату.
    Учитывает историю изменений.
    """
    try:
        # Ищем запись в истории
        cursor.execute("""
            SELECT cpu_cores, ram_gb, nvme1_gb, nvme2_gb, nvme3_gb, 
                   nvme4_gb, nvme5_gb, hdd_gb
            FROM vm_config_history
            WHERE vm_id = %s AND effective_from <= %s
            ORDER BY effective_from DESC
            LIMIT 1
        """, (server['id'], target_date))
        
        history_row = cursor.fetchone()
        
        if history_row:
            return {
                'cpu_cores': history_row[0],
                'ram_gb': history_row[1],
                'nvme1_gb': history_row[2] or 0,
                'nvme2_gb': history_row[3] or 0,
                'nvme3_gb': history_row[4] or 0,
                'nvme4_gb': history_row[5] or 0,
                'nvme5_gb': history_row[6] or 0,
                'hdd_gb': history_row[7] or 0
            }
        else:
            # Нет истории - берем текущую конфигурацию
            return {
                'cpu_cores': server['cpu_cores'],
                'ram_gb': server['ram_gb'],
                'nvme1_gb': server['nvme_config']['nvme1_gb'],
                'nvme2_gb': server['nvme_config']['nvme2_gb'],
                'nvme3_gb': server['nvme_config']['nvme3_gb'],
                'nvme4_gb': 0,
                'nvme5_gb': 0,
                'hdd_gb': server['hdd_gb']
            }
    except Exception as e:
        logger.error(f"Ошибка при получении конфигурации: {e}")
        return None


def get_prices_at_date(target_date, cursor):
    """Определяет цены на указанную дату."""
    try:
        cursor.execute("""
            SELECT cpu_price_per_core, ram_price_per_gb, 
                   nvme_price_per_gb, hdd_price_per_gb
            FROM resource_prices
            WHERE effective_from <= %s
            ORDER BY effective_from DESC
            LIMIT 1
        """, (target_date,))
        
        row = cursor.fetchone()
        if row:
            return {
                'cpu': row[0],
                'ram': row[1],
                'nvme': row[2],
                'hdd': row[3]
            }
        else:
            logger.error(f"Не найдены цены на {target_date}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении цен: {e}")
        return None


def generate_daily_billing(cursor):
    """Генерирует ежедневные биллинговые записи для активных серверов."""
    logger.info("="*50)
    logger.info("Генерация ежедневного биллинга за январь-март 2025...")
    
    if not virtual_server_ids:
        logger.warning("Нет виртуальных серверов для генерации биллинга")
        return 0
    
    # Фильтруем серверы, которые были активны в период
    active_servers = []
    for server in virtual_server_ids:
        # Черновики не участвуют
        if server['status'] == 'draft':
            continue
        
        # Проверяем пересечение с периодом
        server_end = server['stop_date'] if server['stop_date'] else END_DATE + timedelta(days=365)
        if server['start_date'] <= END_DATE and server_end >= START_DATE:
            active_servers.append(server)
    
    logger.info(f"Найдено серверов для биллинга: {len(active_servers)}")
    
    total_records = 0
    current_date = START_DATE
    
    while current_date <= END_DATE:
        date_str = current_date.strftime('%Y-%m-%d')
        day_records = 0
        
        for server in active_servers:
            # Проверяем, активен ли сервер в этот день
            if server['start_date'].date() > current_date.date():
                continue
            if server['stop_date'] and server['stop_date'].date() < current_date.date():
                continue
            
            # Получаем конфигурацию на этот день
            config = get_config_at_date(server, current_date.date(), cursor)
            if not config:
                continue
            
            # Получаем цены на этот день
            prices = get_prices_at_date(current_date.date(), cursor)
            if not prices:
                continue
            
            try:
                # Вычисляем стоимости
                cpu_cost = config['cpu_cores'] * float(prices['cpu'])
                ram_cost = config['ram_gb'] * float(prices['ram'])
                
                # Суммируем NVME
                nvme_total = (
                    config['nvme1_gb'] + config['nvme2_gb'] + 
                    config['nvme3_gb'] + config['nvme4_gb'] + config['nvme5_gb']
                )
                nvme_cost = nvme_total * float(prices['nvme'])
                
                hdd_cost = config['hdd_gb'] * float(prices['hdd'])
                total_cost = cpu_cost + ram_cost + nvme_cost + hdd_cost
                
                # Прямой SQL-запрос для вставки (без использования модели)
                insert_query = """
                    INSERT INTO daily_billing 
                    (billing_date, vm_id, client_id, 
                     cpu_cores, ram_gb, 
                     nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb,
                     cpu_price, ram_price, nvme_price, hdd_price,
                     cpu_cost, ram_cost, nvme_cost, hdd_cost, total_cost)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                            %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(insert_query, (
                    current_date.date(),
                    server['id'],
                    server['client_id'],
                    config['cpu_cores'],
                    config['ram_gb'],
                    config['nvme1_gb'],
                    config['nvme2_gb'],
                    config['nvme3_gb'],
                    config.get('nvme4_gb', 0),
                    config.get('nvme5_gb', 0),
                    config['hdd_gb'],
                    float(prices['cpu']),
                    float(prices['ram']),
                    float(prices['nvme']),
                    float(prices['hdd']),
                    float(round(cpu_cost, 2)),
                    float(round(ram_cost, 2)),
                    float(round(nvme_cost, 2)),
                    float(round(hdd_cost, 2)),
                    float(round(total_cost, 2))
                ))
                
                day_records += 1
                total_records += 1
                    
            except Exception as e:
                logger.error(f"Ошибка при создании биллинга для ВМ {server['id']} на {date_str}: {e}")
        
        if day_records > 0:
            logger.debug(f"  {date_str}: добавлено {day_records} записей")
        
        current_date += timedelta(days=1)
    
    logger.info(f"✅ Создано записей daily_billing: {total_records}")
    return total_records


def print_statistics(cursor):
    """Выводит статистику по заполненным таблицам."""
    logger.info("="*60)
    logger.info("📊 СТАТИСТИКА ЗАПОЛНЕНИЯ БАЗЫ ДАННЫХ")
    logger.info("="*60)
    
    tables = [
        ('clients', 'Клиенты'),
        ('physical_servers', 'Физические серверы'),
        ('vm_statuses', 'Статусы ВМ'),
        ('virtual_servers', 'Виртуальные серверы'),
        ('vm_config_history', 'История конфигураций'),
        ('resource_prices', 'Цены на ресурсы'),
        ('daily_billing', 'Ежедневный биллинг')
    ]
    
    for table, name in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        logger.info(f"  {name}: {count} записей")
    
    # Дополнительная статистика
    cursor.execute("""
        SELECT s.code, COUNT(*) 
        FROM virtual_servers vs
        JOIN vm_statuses s ON vs.status_id = s.id
        GROUP BY s.code
    """)
    status_stats = cursor.fetchall()
    if status_stats:
        logger.info("  Распределение по статусам:")
        for code, count in status_stats:
            logger.info(f"    - {code}: {count}")
    
    cursor.execute("SELECT COUNT(DISTINCT billing_date) FROM daily_billing")
    days = cursor.fetchone()[0]
    logger.info(f"  Дней с биллингом: {days}")
    
    cursor.execute("SELECT SUM(total_cost) FROM daily_billing")
    total = cursor.fetchone()[0] or 0
    logger.info(f"  Общая сумма биллинга: {total:,.2f}")
    
    logger.info("="*60)


def main():
    """Основная функция скрипта."""
    logger.info("="*60)
    logger.info("🌱 ЗАПОЛНЕНИЕ БАЗЫ ДАННЫХ ТЕСТОВЫМИ ДАННЫМИ")
    logger.info("="*60)
    
    # Запрашиваем подтверждение
    if not confirm_cleanup():
        logger.info("Операция отменена пользователем")
        return
    
    connection = None
    cursor = None
    
    try:
        # Подключаемся к БД
        connection = get_connection()
        cursor = connection.cursor()
        
        # Очищаем существующие данные
        cleanup_database(cursor)
        
        # Заполняем таблицы в правильном порядке
        seed_clients(cursor)
        seed_physical_servers(cursor)
        
        # Убеждаемся, что статусы есть
        ensure_statuses(cursor)
        
        seed_virtual_servers(cursor)
        
        # ВРЕМЕННАЯ ПРОВЕРКА
        logger.info(f"Создано виртуальных серверов: {len(virtual_server_ids)}")
        if virtual_server_ids:
            logger.info(f"Первый сервер: {virtual_server_ids[0]}")
        
        seed_resource_prices(cursor)
        seed_vm_config_history(cursor)
        generate_daily_billing(cursor)
        
        # Сохраняем все изменения
        connection.commit()
        
        # Выводим статистику
        print_statistics(cursor)
        
        logger.info("="*60)
        logger.info("✅ ЗАПОЛНЕНИЕ ТЕСТОВЫМИ ДАННЫМИ УСПЕШНО ЗАВЕРШЕНО")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        if connection:
            connection.rollback()
        sys.exit(1)
        
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logger.debug("Соединение с БД закрыто")


if __name__ == "__main__":
    main()