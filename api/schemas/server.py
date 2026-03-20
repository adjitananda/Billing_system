"""
Pydantic schemas for Server endpoints.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ServerCreate(BaseModel):
    """Schema for creating a new server."""
    name: str
    client_id: int
    physical_server_id: int
    purpose: str
    os: str
    cpu_cores: int
    ram_gb: int
    nvme1_gb: int
    nvme2_gb: int | None = 0
    nvme3_gb: int | None = 0
    nvme4_gb: int | None = 0
    nvme5_gb: int | None = 0
    hdd_gb: int
    ip_address: str | None = None
    ip_port: int | None = None
    domain_address: str | None = None
    domain_port: int | None = None


class ServerUpdate(BaseModel):
    """Schema for updating a server."""
    name: str | None = None
    purpose: str | None = None
    os: str | None = None
    cpu_cores: int | None = None
    ram_gb: int | None = None
    nvme1_gb: int | None = None
    nvme2_gb: int | None = None
    nvme3_gb: int | None = None
    nvme4_gb: int | None = None
    nvme5_gb: int | None = None
    hdd_gb: int | None = None
    ip_address: str | None = None
    ip_port: int | None = None
    domain_address: str | None = None
    domain_port: int | None = None


class ConfigHistoryEntry(BaseModel):
    """Schema for VM config history entry."""
    id: int
    effective_from: date
    cpu_cores: int
    ram_gb: int
    nvme1_gb: int
    nvme2_gb: int
    nvme3_gb: int
    nvme4_gb: int
    nvme5_gb: int
    hdd_gb: int

    model_config = ConfigDict(from_attributes=True)


class ServerResponse(BaseModel):
    """Schema for server response with config history."""
    id: int
    name: str
    client_id: int
    physical_server_id: int
    status: str
    purpose: str
    os: str
    cpu_cores: int
    ram_gb: int
    nvme1_gb: int
    nvme2_gb: int
    nvme3_gb: int
    nvme4_gb: int
    nvme5_gb: int
    hdd_gb: int
    ip_address: str | None
    ip_port: int | None
    domain_address: str | None
    domain_port: int | None
    start_date: date | None
    stop_date: date | None
    created_at: datetime
    updated_at: datetime
    config_history: list[ConfigHistoryEntry] = []

    model_config = ConfigDict(from_attributes=True)