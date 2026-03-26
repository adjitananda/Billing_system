from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional

class PriceBase(BaseModel):
    effective_from: date = Field(..., description="Дата начала действия цен")
    cpu_price_per_core: float = Field(..., description="Цена за ядро CPU в день", ge=0)
    ram_price_per_gb: float = Field(..., description="Цена за ГБ RAM в день", ge=0)
    nvme_price_per_gb: float = Field(..., description="Цена за ГБ NVMe в день", ge=0)
    hdd_price_per_gb: float = Field(..., description="Цена за ГБ HDD в день", ge=0)


class PriceCreate(PriceBase):
    pass


class PriceResponse(PriceBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
