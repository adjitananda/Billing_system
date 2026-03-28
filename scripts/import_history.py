#!/usr/bin/env python3
"""
Импорт исторических данных для биллинговой системы.
"""

import argparse
import csv
import sys
import os
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Any
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import get_connection
from utils.logger import get_logger

logger = get_logger('import_history')


class HistoryImporter:
    
    def __init__(self, dry_run=False, force=False, clean_all=False):
        self.dry_run = dry_run
        self.force = force
        self.clean_all = clean_all
        self.conn = None
        self.cursor = None
        self.next_id = -1
        
        self.stats = {
            'events_processed': 0,
            'clients_created': 0,
            'clients_existing': 0,
            'hosts_existing': 0,
            'servers_activated': 0,
            'servers_deactivated': 0,
            'servers_changed': 0,
            'daily_billing_created': 0,
            'price_records': 0,
            'total_cost': 0.0
        }
        
        self.clients_cache = {}
        self.hosts_cache = {}
        self.servers_cache = {}
        self.prices_cache = {}
        self.status_cache = {}
        
    def connect(self):
        self.conn = get_connection()
        self.cursor = self.conn.cursor(dictionary=True)
        self.cursor.execute("SELECT id, code FROM vm_statuses")
        for row in self.cursor.fetchall():
            self.status_cache[row['code']] = row['id']
        logger.info(f"Загружено статусов: {len(self.status_cache)}")
        
    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            
    def begin_transaction(self):
        if not self.dry_run and not self.conn.in_transaction:
            self.conn.start_transaction()
            
    def commit(self):
        if not self.dry_run and self.conn.in_transaction:
            self.conn.commit()
            
    def rollback(self):
        if not self.dry_run and self.conn.in_transaction:
            self.conn.rollback()
            
    def clear_all_data(self):
        if self.dry_run:
            logger.info("DRY-RUN: Будет выполнена очистка всех данных")
            return
        logger.info("Очистка всех данных...")
        tables = ['daily_billing', 'vm_config_history', 'virtual_servers', 'clients']
        for table in tables:
            try:
                self.cursor.execute(f"DELETE FROM {table}")
                logger.info(f"  Очищена таблица {table}: {self.cursor.rowcount} записей")
            except Exception as e:
                logger.error(f"  Ошибка очистки {table}: {e}")
        self.commit()
        
    def clear_billing_and_history(self):
        if self.dry_run:
            logger.info("DRY-RUN: Будет выполнена очистка daily_billing и vm_config_history")
            return
        logger.info("Очистка daily_billing и vm_config_history (--force)...")
        self.cursor.execute("DELETE FROM daily_billing")
        logger.info(f"  Очищена daily_billing: {self.cursor.rowcount} записей")
        self.cursor.execute("DELETE FROM vm_config_history")
        logger.info(f"  Очищена vm_config_history: {self.cursor.rowcount} записей")
        self.commit()
        
    def load_clients(self):
        self.cursor.execute("SELECT id, name FROM clients")
        for row in self.cursor.fetchall():
            self.clients_cache[row['name']] = row['id']
            
    def load_hosts(self):
        self.cursor.execute("SELECT id, name FROM physical_servers")
        for row in self.cursor.fetchall():
            self.hosts_cache[row['name']] = row['id']
        logger.info(f"Загружено хостов: {len(self.hosts_cache)}")
            
    def load_servers(self):
        self.cursor.execute("""
            SELECT id, client_id, name as server_name, start_date, stop_date,
                   cpu_cores, ram_gb, nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb,
                   purpose, os, ip_address
            FROM virtual_servers
        """)
        for row in self.cursor.fetchall():
            key = (row['client_id'], row['server_name'])
            self.servers_cache[key] = row
            
    def get_or_create_client(self, name: str) -> int:
        if name in self.clients_cache:
            self.stats['clients_existing'] += 1
            return self.clients_cache[name]
        if self.dry_run:
            logger.info(f"DRY-RUN: Будет создан клиент: {name}")
            self.stats['clients_created'] += 1
            client_id = self.next_id
            self.next_id -= 1
            self.clients_cache[name] = client_id
            return client_id
        self.cursor.execute("INSERT INTO clients (name) VALUES (%s)", (name,))
        client_id = self.cursor.lastrowid
        self.clients_cache[name] = client_id
        self.stats['clients_created'] += 1
        logger.info(f"Создан клиент: {name} (ID: {client_id})")
        return client_id
        
    def get_host_id(self, name: str) -> int:
        if name in self.hosts_cache:
            self.stats['hosts_existing'] += 1
            return self.hosts_cache[name]
        logger.error(f"Хост '{name}' не найден в БД.")
        sys.exit(1)
        
    def get_or_create_server(self, client_id: int, server_name: str, event_date: date, 
                             config: Dict[str, Any]) -> int:
        key = (client_id, server_name)
        if key in self.servers_cache:
            return self.servers_cache[key]['id']
        if self.dry_run:
            logger.info(f"DRY-RUN: Будет создан сервер: {server_name}")
            self.stats['servers_activated'] += 1
            server_id = self.next_id
            self.next_id -= 1
            self.servers_cache[key] = {
                'id': server_id, 'client_id': client_id, 'server_name': server_name,
                'start_date': event_date, 'stop_date': None, **config
            }
            return server_id
        active_status_id = self.status_cache.get('active', 1)
        self.cursor.execute("""
            INSERT INTO virtual_servers (
                name, client_id, physical_server_id, status_id,
                purpose, os, ip_address,
                start_date,
                cpu_cores, ram_gb,
                nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            server_name, client_id, config['physical_server_id'], active_status_id,
            config.get('purpose', ''), config.get('os', ''), config.get('ip_address', ''),
            event_date,
            config.get('cpu_cores', 0), config.get('ram_gb', 0),
            config.get('nvme1_gb', 0), config.get('nvme2_gb', 0),
            config.get('nvme3_gb', 0), config.get('nvme4_gb', 0),
            config.get('nvme5_gb', 0), config.get('hdd_gb', 0)
        ))
        server_id = self.cursor.lastrowid
        self.servers_cache[key] = {
            'id': server_id, 'client_id': client_id, 'server_name': server_name,
            'start_date': event_date, 'stop_date': None, **config
        }
        self.stats['servers_activated'] += 1
        logger.info(f"Создан сервер: {server_name} (ID: {server_id})")
        return server_id
        
    def update_server_config(self, server_id: int, config: Dict[str, Any], event_date: date):
        if self.dry_run:
            logger.info(f"DRY-RUN: Будет изменена конфигурация сервера {server_id}")
            self.stats['servers_changed'] += 1
            return
        self.cursor.execute("""
            INSERT INTO vm_config_history (
                vm_id, effective_from, cpu_cores, ram_gb,
                nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (server_id, event_date,
              config.get('cpu_cores', 0), config.get('ram_gb', 0),
              config.get('nvme1_gb', 0), config.get('nvme2_gb', 0),
              config.get('nvme3_gb', 0), config.get('nvme4_gb', 0),
              config.get('nvme5_gb', 0), config.get('hdd_gb', 0)))
        self.cursor.execute("""
            UPDATE virtual_servers
            SET cpu_cores = %s, ram_gb = %s,
                nvme1_gb = %s, nvme2_gb = %s, nvme3_gb = %s,
                nvme4_gb = %s, nvme5_gb = %s, hdd_gb = %s
            WHERE id = %s
        """, (config.get('cpu_cores', 0), config.get('ram_gb', 0),
              config.get('nvme1_gb', 0), config.get('nvme2_gb', 0),
              config.get('nvme3_gb', 0), config.get('nvme4_gb', 0),
              config.get('nvme5_gb', 0), config.get('hdd_gb', 0), server_id))
        self.stats['servers_changed'] += 1
        logger.info(f"Изменена конфигурация сервера {server_id} с {event_date}")
        
    def deactivate_server(self, server_id: int, event_date: date):
        if self.dry_run:
            logger.info(f"DRY-RUN: Будет деактивирован сервер {server_id}")
            self.stats['servers_deactivated'] += 1
            return
        deleted_status_id = self.status_cache.get('deleted', 4)
        self.cursor.execute("""
            UPDATE virtual_servers SET status_id = %s, stop_date = %s WHERE id = %s
        """, (deleted_status_id, event_date, server_id))
        self.stats['servers_deactivated'] += 1
        logger.info(f"Деактивирован сервер {server_id} с {event_date}")
        
    def load_prices(self, prices_file: str):
        logger.info(f"Загрузка цен из файла: {prices_file}")
        if not os.path.exists(prices_file):
            logger.error(f"Файл не найден: {prices_file}")
            return 0
        with open(prices_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                effective_from = datetime.strptime(row['effective_from'], '%Y-%m-%d').date()
                self.cursor.execute("SELECT id FROM resource_prices WHERE effective_from = %s", (effective_from,))
                exists = self.cursor.fetchone()
                if exists and not self.force:
                    logger.warning(f"Цена на {effective_from} уже существует, пропускаем")
                    continue
                if self.dry_run:
                    logger.info(f"DRY-RUN: Будет загружена цена на {effective_from}")
                    count += 1
                    continue
                if exists and self.force:
                    self.cursor.execute("""
                        UPDATE resource_prices SET cpu_price_per_core=%s, ram_price_per_gb=%s,
                            nvme_price_per_gb=%s, hdd_price_per_gb=%s WHERE effective_from=%s
                    """, (float(row['cpu_price_per_core']), float(row['ram_price_per_gb']),
                          float(row['nvme_price_per_gb']), float(row['hdd_price_per_gb']), effective_from))
                else:
                    self.cursor.execute("""
                        INSERT INTO resource_prices (effective_from, cpu_price_per_core, ram_price_per_gb,
                            nvme_price_per_gb, hdd_price_per_gb) VALUES (%s, %s, %s, %s, %s)
                    """, (effective_from, float(row['cpu_price_per_core']), float(row['ram_price_per_gb']),
                          float(row['nvme_price_per_gb']), float(row['hdd_price_per_gb'])))
                count += 1
        self.stats['price_records'] = count
        logger.info(f"Загружено цен: {count}")
        return count
        
    def get_price_for_date(self, target_date: date) -> Optional[Dict]:
        if target_date in self.prices_cache:
            return self.prices_cache[target_date]
        self.cursor.execute("""
            SELECT * FROM resource_prices WHERE effective_from <= %s ORDER BY effective_from DESC LIMIT 1
        """, (target_date,))
        price = self.cursor.fetchone()
        if price:
            self.prices_cache[target_date] = price
        return price
        
    def calculate_cost(self, config: Dict, price: Dict) -> Dict:
        cpu_cost = config.get('cpu_cores', 0) * float(price['cpu_price_per_core'])
        ram_cost = config.get('ram_gb', 0) * float(price['ram_price_per_gb'])
        nvme_total = sum([config.get(f'nvme{i}_gb', 0) for i in range(1, 6)])
        nvme_cost = nvme_total * float(price['nvme_price_per_gb'])
        hdd_cost = config.get('hdd_gb', 0) * float(price['hdd_price_per_gb'])
        total = cpu_cost + ram_cost + nvme_cost + hdd_cost
        return {'cpu': round(cpu_cost, 2), 'ram': round(ram_cost, 2),
                'nvme': round(nvme_cost, 2), 'hdd': round(hdd_cost, 2),
                'total': round(total, 2)}
        
    def generate_daily_billing(self):
        logger.info("Генерация ежедневных биллинговых записей...")
        self.cursor.execute("""
            SELECT id, client_id, name as server_name, start_date, stop_date,
                   cpu_cores, ram_gb, nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb
            FROM virtual_servers
        """)
        servers = self.cursor.fetchall()
        logger.info(f"Найдено серверов для обработки: {len(servers)}")
        for server in servers:
            start_date = server['start_date']
            end_date = server['stop_date'] or date.today()
            if not start_date:
                continue
            self.cursor.execute("""
                SELECT effective_from, cpu_cores, ram_gb, nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb
                FROM vm_config_history WHERE vm_id = %s ORDER BY effective_from ASC
            """, (server['id'],))
            config_changes = self.cursor.fetchall()
            current_date = start_date
            current_config = {k: server[k] for k in ['cpu_cores', 'ram_gb', 'nvme1_gb', 'nvme2_gb',
                'nvme3_gb', 'nvme4_gb', 'nvme5_gb', 'hdd_gb']}
            periods = []
            for change in config_changes:
                change_date = change['effective_from']
                if change_date > current_date:
                    periods.append({'start': current_date, 'end': change_date - timedelta(days=1),
                                    'config': current_config.copy()})
                    current_date = change_date
                current_config = {k: change[k] for k in ['cpu_cores', 'ram_gb', 'nvme1_gb', 'nvme2_gb',
                    'nvme3_gb', 'nvme4_gb', 'nvme5_gb', 'hdd_gb']}
                current_date = change_date
            if current_date <= end_date:
                periods.append({'start': current_date, 'end': end_date, 'config': current_config.copy()})
            for period in periods:
                current_day = period['start']
                while current_day <= period['end']:
                    price = self.get_price_for_date(current_day)
                    if not price:
                        current_day += timedelta(days=1)
                        continue
                    cost = self.calculate_cost(period['config'], price)
                    if self.dry_run:
                        self.stats['daily_billing_created'] += 1
                        self.stats['total_cost'] += cost['total']
                    else:
                        self.cursor.execute("SELECT id FROM daily_billing WHERE vm_id=%s AND billing_date=%s",
                                           (server['id'], current_day))
                        exists = self.cursor.fetchone()
                        if exists and self.force:
                            self.cursor.execute("""
                                UPDATE daily_billing SET cpu_cost=%s, ram_cost=%s, nvme_cost=%s, hdd_cost=%s, total_cost=%s
                                WHERE vm_id=%s AND billing_date=%s
                            """, (cost['cpu'], cost['ram'], cost['nvme'], cost['hdd'], cost['total'],
                                  server['id'], current_day))
                        elif not exists:
                            self.cursor.execute("""
                                INSERT INTO daily_billing (billing_date, vm_id, client_id, cpu_cores, ram_gb,
                                    nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb,
                                    cpu_price, ram_price, nvme_price, hdd_price,
                                    cpu_cost, ram_cost, nvme_cost, hdd_cost, total_cost)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (current_day, server['id'], server['client_id'],
                                  period['config']['cpu_cores'], period['config']['ram_gb'],
                                  period['config']['nvme1_gb'], period['config']['nvme2_gb'],
                                  period['config']['nvme3_gb'], period['config']['nvme4_gb'],
                                  period['config']['nvme5_gb'], period['config']['hdd_gb'],
                                  price['cpu_price_per_core'], price['ram_price_per_gb'],
                                  price['nvme_price_per_gb'], price['hdd_price_per_gb'],
                                  cost['cpu'], cost['ram'], cost['nvme'], cost['hdd'], cost['total']))
                            self.stats['daily_billing_created'] += 1
                            self.stats['total_cost'] += cost['total']
                    current_day += timedelta(days=1)
        logger.info(f"Сгенерировано записей: {self.stats['daily_billing_created']}, сумма: {self.stats['total_cost']:.2f}")
        
    def process_events(self, events_file: str):
        logger.info(f"Загрузка событий из файла: {events_file}")
        if not os.path.exists(events_file):
            logger.error(f"Файл не найден: {events_file}")
            return
        events = []
        with open(events_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row['date'] = datetime.strptime(row['date'], '%Y-%m-%d').date()
                for field in ['cpu_cores', 'ram_gb', 'nvme1_gb', 'nvme2_gb', 
                             'nvme3_gb', 'nvme4_gb', 'nvme5_gb', 'hdd_gb']:
                    if row.get(field) and row[field].strip():
                        try:
                            row[field] = int(row[field])
                        except:
                            row[field] = 0
                    else:
                        row[field] = 0
                events.append(row)
        events.sort(key=lambda x: x['date'])
        logger.info(f"Загружено событий: {len(events)}")
        
        if self.force and not self.dry_run:
            self.clear_billing_and_history()
        
        self.load_clients()
        self.load_hosts()
        self.load_servers()
        
        for event in events:
            logger.info(f"Обработка: {event['date']} {event['event']} {event['server_name']}")
            client_id = self.get_or_create_client(event['client_name'])
            host_id = self.get_host_id(event['physical_server_name'])
            config = {
                'physical_server_id': host_id,
                'purpose': event.get('purpose', ''),
                'os': event.get('os', ''),
                'ip_address': event.get('IP-adress', ''),
                'cpu_cores': event['cpu_cores'],
                'ram_gb': event['ram_gb'],
                'nvme1_gb': event['nvme1_gb'],
                'nvme2_gb': event['nvme2_gb'],
                'nvme3_gb': event['nvme3_gb'],
                'nvme4_gb': event['nvme4_gb'],
                'nvme5_gb': event['nvme5_gb'],
                'hdd_gb': event['hdd_gb']
            }
            if event['event'] == 'activate':
                self.get_or_create_server(client_id, event['server_name'], event['date'], config)
            elif event['event'] == 'change':
                key = (client_id, event['server_name'])
                if key in self.servers_cache:
                    self.update_server_config(self.servers_cache[key]['id'], config, event['date'])
                else:
                    logger.warning(f"Сервер {event['server_name']} не найден")
            elif event['event'] == 'deactivate':
                key = (client_id, event['server_name'])
                if key in self.servers_cache:
                    self.deactivate_server(self.servers_cache[key]['id'], event['date'])
                else:
                    logger.warning(f"Сервер {event['server_name']} не найден")
            self.stats['events_processed'] += 1
        if not self.dry_run:
            self.generate_daily_billing()
        else:
            logger.info("DRY-RUN: Пропуск генерации ежедневных записей")
            
    def print_statistics(self):
        print("\n" + "="*50)
        print("СТАТИСТИКА ИМПОРТА")
        print("="*50)
        print(f"Обработано событий: {self.stats['events_processed']}")
        print(f"Клиенты: создано {self.stats['clients_created']}, существовало {self.stats['clients_existing']}")
        print(f"Хосты: использовано {self.stats['hosts_existing']}")
        print(f"Серверы: активировано {self.stats['servers_activated']}, "
              f"деактивировано {self.stats['servers_deactivated']}, "
              f"изменено {self.stats['servers_changed']}")
        print(f"Ежедневные записи: {self.stats['daily_billing_created']}")
        print(f"Загружено цен: {self.stats['price_records']}")
        print(f"Общая сумма: {self.stats['total_cost']:.2f}")
        print("="*50)
        if self.dry_run:
            print("\n*** DRY-RUN: Изменения не были применены ***")
            
def main():
    parser = argparse.ArgumentParser(description='Импорт исторических данных')
    parser.add_argument('--events', help='Путь к CSV-файлу с событиями')
    parser.add_argument('--prices', help='Путь к CSV-файлу с ценами')
    parser.add_argument('--dry-run', action='store_true', help='Только показать, что будет сделано')
    parser.add_argument('--force', action='store_true', help='Перезаписывать существующие данные')
    parser.add_argument('--clean-all', action='store_true', help='Очистить все данные перед импортом')
    args = parser.parse_args()
    if not args.events and not args.prices:
        parser.print_help()
        print("\nОшибка: нужно указать хотя бы один из параметров --events или --prices")
        sys.exit(1)
    importer = HistoryImporter(dry_run=args.dry_run, force=args.force, clean_all=args.clean_all)
    try:
        importer.connect()
        
        if args.clean_all:
            importer.begin_transaction()
            try:
                importer.clear_all_data()
                importer.commit()
            except Exception as e:
                importer.rollback()
                logger.error(f"Ошибка очистки: {e}")
                raise
                
        if args.prices:
            importer.begin_transaction()
            try:
                importer.load_prices(args.prices)
                importer.commit()
            except Exception as e:
                importer.rollback()
                logger.error(f"Ошибка загрузки цен: {e}")
                raise
                
        if args.events:
            importer.begin_transaction()
            try:
                importer.process_events(args.events)
                importer.commit()
            except Exception as e:
                importer.rollback()
                logger.error(f"Ошибка обработки событий: {e}")
                raise
                
        importer.print_statistics()
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        raise
    finally:
        importer.close()
        
if __name__ == '__main__':
    main()
