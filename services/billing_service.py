# services/billing_service.py
"""
Сервисный слой для биллинговой системы.
Содержит общую логику расчётов, используемую как в API, так и в скриптах.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Any
from mysql.connector import connection


def get_active_servers_on_date(
    conn: connection.MySQLConnection, target_date: str
) -> List[Dict[str, Any]]:
    """
    Возвращает список активных серверов на указаную дату.
    Активными считаются серверы со статусом 'active',
    у которых start_date <= target_date и (stop_date IS NULL OR stop_date > target_date).
    """
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT vs.* FROM virtual_servers vs
        JOIN vm_statuses s ON vs.status_id = s.id
        WHERE s.code = 'active'
          AND vs.start_date <= %s
          AND (vs.stop_date IS NULL OR vs.stop_date > %s)
    """, (target_date, target_date))
    return cursor.fetchall()


def get_config_on_date(
    conn: connection.MySQLConnection, vm_id: int, target_date: str
) -> Optional[Dict[str, Any]]:
    """
    Возвращает конфигурацию сервера на указанную дату.
    Сначала ищет в vm_config_history (effective_from <= target_date),
    если не найдено — берёт из virtual_servers.
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
        return config

    # Берём из основной таблицы
    cursor.execute(
        "SELECT * FROM virtual_servers WHERE id = %s",
        (vm_id,)
    )
    return cursor.fetchone()


def get_prices_on_date(
    conn: connection.MySQLConnection, target_date: str
) -> Optional[Dict[str, Any]]:
    """
    Возвращает цены на указанную дату.
    Берёт последнюю запись из resource_prices с effective_from <= target_date.
    """
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM resource_prices
        WHERE effective_from <= %s
        ORDER BY effective_from DESC LIMIT 1
    """, (target_date,))
    return cursor.fetchone()


def get_total_nvme(config: Dict[str, Any]) -> int:
    """Возвращает сумму всех NVMe дисков из конфигурации."""
    total = 0
    for i in range(1, 6):
        total += config.get(f'nvme{i}_gb', 0)
    return total


def calculate_server_cost(
    config: Dict[str, Any], prices: Dict[str, Any]
) -> Dict[str, Decimal]:
    """
    Рассчитывает стоимость сервера на основе конфигурации и цен.
    Возвращает словарь с ключами:
        cpu_cost, ram_cost, nvme_cost, hdd_cost, total_cost, nvme_total
    """
    nvme_total = get_total_nvme(config)

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
        'nvme_total': nvme_total,
    }

def calculate_server_cost_with_custom_prices(
    conn: connection.MySQLConnection,
    server_id: int,
    target_date: str,
    custom_prices: Dict[str, float]
) -> float:
    """
    Рассчитывает стоимость сервера с кастомными ценами.
    
    Args:
        conn: Соединение с БД
        server_id: ID виртуального сервера
        target_date: Дата расчета (строка YYYY-MM-DD)
        custom_prices: Словарь с ценами {'cpu': float, 'ram': float, 'nvme': float, 'hdd': float}
    
    Returns:
        float: Итоговая стоимость сервера в рублях (округлено до 2 знаков)
    """
    # Получаем конфигурацию сервера на указанную дату
    config = get_config_on_date(conn, server_id, target_date)
    
    if not config:
        return 0.0
    
    # Получаем сумму NVMe дисков
    nvme_total = get_total_nvme(config)
    
    # Рассчитываем стоимость по кастомным ценам
    cpu_cost = config.get('cpu_cores', 0) * custom_prices.get('cpu', 0)
    ram_cost = config.get('ram_gb', 0) * custom_prices.get('ram', 0)
    nvme_cost = nvme_total * custom_prices.get('nvme', 0)
    hdd_cost = config.get('hdd_gb', 0) * custom_prices.get('hdd', 0)
    
    total_cost = cpu_cost + ram_cost + nvme_cost + hdd_cost
    
    return round(float(total_cost), 2)
