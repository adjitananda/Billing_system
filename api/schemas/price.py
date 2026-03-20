"""
Pydantic schemas for Price endpoints.
"""

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class PriceCreate(BaseModel):
    """Schema for creating a new price record."""
    effective_from: date
    cpu_price_per_core: Decimal
    ram_price_per_gb: Decimal
    nvme_price_per_gb: Decimal
    hdd_price_per_gb: Decimal


class PriceResponse(BaseModel):
    """Schema for price response."""
    id: int
    effective_from: date
    cpu_price_per_core: Decimal
    ram_price_per_gb: Decimal
    nvme_price_per_gb: Decimal
    hdd_price_per_gb: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)