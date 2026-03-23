# api/routes/reports.py
"""
Маршруты для отчетов биллинговой системы.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar

from config.database import get_connection
from services.billing_service import (
    get_config_on_date,
    get_prices_on_date,
    calculate_server_cost
)
from api.schemas.report import (
    ClientReport,
    ClientServerReport,
    DailyBreakdownItem,
    SummaryReport,
    MonthlySummaryReport,
    ClientSummary,
    MonthSummary,
    DatacenterReport,
    PhysicalServerResources,
    PhysicalServerUsage,
    UsagePercent,
    ServerHistoryReport,
    DailyBreakdownDetail,
    ConfigChangeItem,
    Period
)

router = APIRouter()


def get_current_month_period() -> tuple:
    """Возвращает (start_date, end_date) для текущего месяца."""
    today = date.today()
    start_date = date(today.year, today.month, 1)
    # Последний день месяца
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_date = date(today.year, today.month, last_day)
    return start_date, end_date


def validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> tuple:
    """Валидирует и возвращает период. Если не указан - текущий месяц."""
    if not start_date and not end_date:
        return get_current_month_period()
    
    if not start_date:
        # Если нет start_date, берем начало текущего месяца
        start_date, _ = get_current_month_period()
    
    if not end_date:
        end_date = date.today()
    
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date не может быть позже end_date")
    
    return start_date, end_date


@router.get("/client/{client_id}", response_model=ClientReport)
async def get_client_report(
    client_id: int,
    start_date: Optional[date] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    detailed: bool = Query(False, description="Вернуть дневную разбивку")
):
    """
    Отчет по стоимости услуг клиента за период.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Валидируем период
        period_start, period_end = validate_date_range(start_date, end_date)
        
        # Получаем информацию о клиенте
        cursor.execute(
            "SELECT id, name FROM clients WHERE id = %s",
            (client_id,)
        )
        client = cursor.fetchone()
        if not client:
            raise HTTPException(status_code=404, detail=f"Клиент с id {client_id} не найден")
        
        # Получаем агрегированные данные по серверам
        cursor.execute("""
            SELECT 
                db.vm_id as server_id,
                vs.name as server_name,
                COUNT(*) as days,
                SUM(db.total_cost) as amount
            FROM daily_billing db
            JOIN virtual_servers vs ON db.vm_id = vs.id
            WHERE db.client_id = %s 
              AND db.billing_date BETWEEN %s AND %s
            GROUP BY db.vm_id, vs.name
            ORDER BY amount DESC
        """, (client_id, period_start, period_end))
        
        servers_data = cursor.fetchall()
        
        servers = [
            ClientServerReport(
                server_id=row['server_id'],
                server_name=row['server_name'],
                days=row['days'],
                amount=Decimal(str(row['amount']))
            )
            for row in servers_data
        ]
        
        total_amount = sum(s.amount for s in servers)
        
        # Дневная разбивка (если запрошена)
        daily_breakdown = None
        if detailed:
            cursor.execute("""
                SELECT 
                    billing_date as date,
                    SUM(total_cost) as amount
                FROM daily_billing
                WHERE client_id = %s 
                  AND billing_date BETWEEN %s AND %s
                GROUP BY billing_date
                ORDER BY billing_date
            """, (client_id, period_start, period_end))
            
            daily_data = cursor.fetchall()
            daily_breakdown = [
                DailyBreakdownItem(
                    date=row['date'],
                    amount=Decimal(str(row['amount']))
                )
                for row in daily_data
            ]
        
        return ClientReport(
            client_id=client_id,
            client_name=client['name'],
            period=Period(start=period_start, end=period_end),
            total_amount=total_amount,
            servers=servers,
            daily_breakdown=daily_breakdown
        )
        
    finally:
        cursor.close()
        conn.close()


@router.get("/summary")
async def get_summary_report(
    start_date: Optional[date] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    group_by: str = Query("client", description="Группировка: client или month")
):
    """
    Сводный отчет по всем клиентам за период.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        period_start, period_end = validate_date_range(start_date, end_date)
        
        # Группировка по клиентам
        if group_by == "client":
            cursor.execute("""
                SELECT 
                    db.client_id,
                    c.name as client_name,
                    COUNT(DISTINCT db.vm_id) as server_count,
                    SUM(db.total_cost) as amount
                FROM daily_billing db
                JOIN clients c ON db.client_id = c.id
                WHERE db.billing_date BETWEEN %s AND %s
                GROUP BY db.client_id, c.name
                ORDER BY amount DESC
            """, (period_start, period_end))
            
            clients_data = cursor.fetchall()
            total = sum(Decimal(str(row['amount'])) for row in clients_data)
            
            clients = [
                ClientSummary(
                    client_id=row['client_id'],
                    client_name=row['client_name'],
                    amount=Decimal(str(row['amount'])),
                    server_count=row['server_count']
                )
                for row in clients_data
            ]
            
            return SummaryReport(
                period=Period(start=period_start, end=period_end),
                total=total,
                clients=clients
            )
        
        # Группировка по месяцам
        elif group_by == "month":
            cursor.execute("""
                SELECT 
                    DATE_FORMAT(db.billing_date, '%Y-%m') as month,
                    SUM(db.total_cost) as amount
                FROM daily_billing db
                WHERE db.billing_date BETWEEN %s AND %s
                GROUP BY DATE_FORMAT(db.billing_date, '%Y-%m')
                ORDER BY month
            """, (period_start, period_end))
            
            months_data = cursor.fetchall()
            total = sum(Decimal(str(row['amount'])) for row in months_data)
            
            months = [
                MonthSummary(
                    month=row['month'],
                    amount=Decimal(str(row['amount']))
                )
                for row in months_data
            ]
            
            return MonthlySummaryReport(
                period=Period(start=period_start, end=period_end),
                total=total,
                months=months
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Некорректное значение group_by: {group_by}. Допустимо: client, month"
            )
            
    finally:
        cursor.close()
        conn.close()


@router.get("/datacenter", response_model=DatacenterReport)
async def get_datacenter_report(
    date_param: Optional[date] = Query(None, alias="date", description="Дата среза (YYYY-MM-DD), по умолчанию сегодня")
):
    """
    Отчет по загрузке дата-центра на указанную дату.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        target_date = date_param or date.today()
        
        # Получаем использованные ресурсы из daily_billing
        cursor.execute("""
            SELECT 
                SUM(cpu_cores) as used_cores,
                SUM(ram_gb) as used_ram,
                SUM(nvme1_gb + nvme2_gb + nvme3_gb + nvme4_gb + nvme5_gb) as used_nvme,
                SUM(hdd_gb) as used_hdd
            FROM daily_billing
            WHERE billing_date = %s
        """, (target_date,))
        
        used_resources = cursor.fetchone() or {}
        
        # Получаем физические серверы
        cursor.execute("""
            SELECT id, name, total_cores, total_ram_gb, total_nvme_gb, total_sata_gb
            FROM physical_servers
        """)
        
        physical_servers = cursor.fetchall()
        
        if not physical_servers:
            return DatacenterReport(
                date=target_date,
                physical_servers=[],
                total_usage=UsagePercent(
                    cores=0,
                    ram_gb=0,
                    nvme_gb=0,
                    sata_gb=0
                )
            )
        
        # Суммируем общие ресурсы
        total_resources = {
            'cores': sum(ps['total_cores'] for ps in physical_servers),
            'ram_gb': sum(ps['total_ram_gb'] for ps in physical_servers),
            'nvme_gb': sum(ps['total_nvme_gb'] for ps in physical_servers),
            'sata_gb': sum(ps['total_sata_gb'] for ps in physical_servers)
        }
        
        # Использованные ресурсы
        used = {
            'cores': used_resources.get('used_cores', 0) or 0,
            'ram_gb': used_resources.get('used_ram', 0) or 0,
            'nvme_gb': used_resources.get('used_nvme', 0) or 0,
            'sata_gb': used_resources.get('used_hdd', 0) or 0
        }
        
        # Рассчитываем проценты использования для каждого физического сервера
        physical_servers_list = []
        
        for ps in physical_servers:
            cores_percent = (used['cores'] / total_resources['cores'] * 100) if total_resources['cores'] > 0 else 0
            ram_percent = (used['ram_gb'] / total_resources['ram_gb'] * 100) if total_resources['ram_gb'] > 0 else 0
            nvme_percent = (used['nvme_gb'] / total_resources['nvme_gb'] * 100) if total_resources['nvme_gb'] > 0 else 0
            sata_percent = (used['sata_gb'] / total_resources['sata_gb'] * 100) if total_resources['sata_gb'] > 0 else 0
            
            physical_servers_list.append(
                PhysicalServerUsage(
                    server_id=ps['id'],
                    server_name=ps['name'],
                    total=PhysicalServerResources(
                        cores=ps['total_cores'],
                        ram_gb=ps['total_ram_gb'],
                        nvme_gb=ps['total_nvme_gb'],
                        sata_gb=ps['total_sata_gb']
                    ),
                    used=PhysicalServerResources(
                        cores=int(ps['total_cores'] * cores_percent / 100),
                        ram_gb=int(ps['total_ram_gb'] * ram_percent / 100),
                        nvme_gb=int(ps['total_nvme_gb'] * nvme_percent / 100),
                        sata_gb=int(ps['total_sata_gb'] * sata_percent / 100)
                    ),
                    usage_percent=UsagePercent(
                        cores=round(cores_percent, 1),
                        ram_gb=round(ram_percent, 1),
                        nvme_gb=round(nvme_percent, 1),
                        sata_gb=round(sata_percent, 1)
                    )
                )
            )
        
        # Общие проценты использования
        total_usage = UsagePercent(
            cores=round((used['cores'] / total_resources['cores'] * 100), 1) if total_resources['cores'] > 0 else 0,
            ram_gb=round((used['ram_gb'] / total_resources['ram_gb'] * 100), 1) if total_resources['ram_gb'] > 0 else 0,
            nvme_gb=round((used['nvme_gb'] / total_resources['nvme_gb'] * 100), 1) if total_resources['nvme_gb'] > 0 else 0,
            sata_gb=round((used['sata_gb'] / total_resources['sata_gb'] * 100), 1) if total_resources['sata_gb'] > 0 else 0
        )
        
        return DatacenterReport(
            date=target_date,
            physical_servers=physical_servers_list,
            total_usage=total_usage
        )
        
    finally:
        cursor.close()
        conn.close()


@router.get("/server/{server_id}", response_model=ServerHistoryReport)
async def get_server_history_report(
    server_id: int,
    start_date: Optional[date] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Конец периода (YYYY-MM-DD)")
):
    """
    Отчет по истории стоимости конкретного сервера.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        period_start, period_end = validate_date_range(start_date, end_date)
        
        # Получаем информацию о сервере и клиенте
        cursor.execute("""
            SELECT vs.id, vs.name, vs.client_id, c.name as client_name
            FROM virtual_servers vs
            JOIN clients c ON vs.client_id = c.id
            WHERE vs.id = %s
        """, (server_id,))
        
        server = cursor.fetchone()
        if not server:
            raise HTTPException(status_code=404, detail=f"Сервер с id {server_id} не найден")
        
        # Получаем дневную разбивку из daily_billing
        cursor.execute("""
            SELECT 
                billing_date as date,
                cpu_cores,
                ram_gb,
                nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb,
                hdd_gb as sata_gb,
                total_cost as cost
            FROM daily_billing
            WHERE vm_id = %s 
              AND billing_date BETWEEN %s AND %s
            ORDER BY billing_date
        """, (server_id, period_start, period_end))
        
        daily_data = cursor.fetchall()
        
        # Если нет данных в daily_billing, пробуем рассчитать вручную
        if not daily_data:
            # Генерируем даты периода
            current_date = period_start
            daily_breakdown = []
            total_amount = Decimal('0')
            
            while current_date <= period_end:
                config = get_config_on_date(conn, server_id, current_date.isoformat())
                if config:
                    prices = get_prices_on_date(conn, current_date.isoformat())
                    if prices:
                        costs = calculate_server_cost(config, prices)
                        nvme_total = costs['nvme_total']
                        daily_breakdown.append(
                            DailyBreakdownDetail(
                                date=current_date,
                                cpu_cores=config['cpu_cores'],
                                ram_gb=config['ram_gb'],
                                nvme_gb=nvme_total,
                                sata_gb=config.get('hdd_gb', 0),
                                cost=costs['total_cost']
                            )
                        )
                        total_amount += costs['total_cost']
                current_date += timedelta(days=1)
            
            days = len(daily_breakdown)
        else:
            # Формируем из существующих данных
            daily_breakdown = []
            total_amount = Decimal('0')
            
            for row in daily_data:
                nvme_total = sum(row.get(f'nvme{i}_gb', 0) for i in range(1, 6))
                daily_breakdown.append(
                    DailyBreakdownDetail(
                        date=row['date'],
                        cpu_cores=row['cpu_cores'],
                        ram_gb=row['ram_gb'],
                        nvme_gb=nvme_total,
                        sata_gb=row['sata_gb'],
                        cost=Decimal(str(row['cost']))
                    )
                )
                total_amount += Decimal(str(row['cost']))
            
            days = len(daily_breakdown)
        
        # Получаем историю изменений конфигурации
        cursor.execute("""
            SELECT 
                effective_from,
                cpu_cores,
                ram_gb,
                nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb,
                hdd_gb as sata_gb
            FROM vm_config_history
            WHERE vm_id = %s 
              AND effective_from BETWEEN %s AND %s
            ORDER BY effective_from
        """, (server_id, period_start, period_end))
        
        config_history = cursor.fetchall()
        
        # Также добавляем начальную конфигурацию из virtual_servers, если она попадает в период
        cursor.execute("""
            SELECT start_date as effective_from, cpu_cores, ram_gb,
                   nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb,
                   hdd_gb as sata_gb
            FROM virtual_servers
            WHERE id = %s AND start_date BETWEEN %s AND %s
        """, (server_id, period_start, period_end))
        
        initial_config = cursor.fetchone()
        
        config_changes = []
        if initial_config:
            nvme_total = sum(initial_config.get(f'nvme{i}_gb', 0) for i in range(1, 6))
            config_changes.append(
                ConfigChangeItem(
                    effective_from=initial_config['effective_from'],
                    cpu_cores=initial_config['cpu_cores'],
                    ram_gb=initial_config['ram_gb'],
                    nvme_gb=nvme_total,
                    sata_gb=initial_config.get('sata_gb', 0)
                )
            )
        
        for row in config_history:
            nvme_total = sum(row.get(f'nvme{i}_gb', 0) for i in range(1, 6))
            config_changes.append(
                ConfigChangeItem(
                    effective_from=row['effective_from'],
                    cpu_cores=row['cpu_cores'],
                    ram_gb=row['ram_gb'],
                    nvme_gb=nvme_total,
                    sata_gb=row.get('sata_gb', 0)
                )
            )
        
        return ServerHistoryReport(
            server_id=server_id,
            server_name=server['name'],
            client_id=server['client_id'],
            client_name=server['client_name'],
            period=Period(start=period_start, end=period_end),
            total_amount=total_amount,
            days=days,
            daily_breakdown=daily_breakdown,
            config_changes=config_changes
        )
        
    finally:
        cursor.close()
        conn.close()