# api/schemas/report.py
"""
Pydantic схемы для отчетов биллинговой системы.
"""

from pydantic import BaseModel
from datetime import date
from typing import List, Optional
from decimal import Decimal


class Period(BaseModel):
    """Период отчета."""
    start: date
    end: date


class ClientServerReport(BaseModel):
    """Информация о сервере в отчете клиента."""
    server_id: int
    server_name: str
    days: int
    amount: Decimal


class DailyBreakdownItem(BaseModel):
    """Дневная разбивка стоимости."""
    date: date
    amount: Decimal


class ClientReport(BaseModel):
    """Отчет по клиенту."""
    client_id: int
    client_name: str
    period: Period
    total_amount: Decimal
    servers: List[ClientServerReport]
    daily_breakdown: Optional[List[DailyBreakdownItem]] = None


class ClientSummary(BaseModel):
    """Сводка по клиенту в общем отчете."""
    client_id: int
    client_name: str
    amount: Decimal
    server_count: int


class MonthSummary(BaseModel):
    """Сводка по месяцу."""
    month: str
    amount: Decimal


class SummaryReport(BaseModel):
    """Сводный отчет по всем клиентам (группировка по клиентам)."""
    period: Period
    total: Decimal
    clients: List[ClientSummary]


class MonthlySummaryReport(BaseModel):
    """Сводный отчет по месяцам."""
    period: Period
    total: Decimal
    months: List[MonthSummary]


class PhysicalServerResources(BaseModel):
    """Ресурсы физического сервера (абсолютные значения)."""
    cores: int
    ram_gb: int
    nvme_gb: int
    sata_gb: int


class UsagePercent(BaseModel):
    """Проценты использования."""
    cores: float
    ram_gb: float
    nvme_gb: float
    sata_gb: float


class PhysicalServerUsage(BaseModel):
    """Использование физического сервера."""
    server_id: int
    server_name: str
    total: PhysicalServerResources
    used: PhysicalServerResources
    usage_percent: UsagePercent


class DatacenterReport(BaseModel):
    """Отчет по загрузке дата-центра."""
    date: date
    physical_servers: List[PhysicalServerUsage]
    total_usage: UsagePercent


class DailyBreakdownDetail(BaseModel):
    """Детальная дневная разбивка для отчета по серверу."""
    date: date
    cpu_cores: int
    ram_gb: int
    nvme_gb: int
    sata_gb: int
    cost: Decimal


class ConfigChangeItem(BaseModel):
    """Элемент истории изменений конфигурации."""
    effective_from: date
    cpu_cores: int
    ram_gb: int
    nvme_gb: int
    sata_gb: int


class ServerHistoryReport(BaseModel):
    """Отчет по истории стоимости сервера."""
    server_id: int
    server_name: str
    client_id: int
    client_name: str
    period: Period
    total_amount: Decimal
    days: int
    daily_breakdown: List[DailyBreakdownDetail]
    config_changes: List[ConfigChangeItem]