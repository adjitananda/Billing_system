from pydantic import BaseModel
from typing import Optional

class PhysicalServerBase(BaseModel):
    name: str
    total_cores: int
    total_ram_gb: int
    total_nvme_gb: int
    total_sata_gb: int

class PhysicalServerCreate(PhysicalServerBase):
    pass

class PhysicalServerUpdate(BaseModel):
    name: Optional[str] = None
    total_cores: Optional[int] = None
    total_ram_gb: Optional[int] = None
    total_nvme_gb: Optional[int] = None
    total_sata_gb: Optional[int] = None

class PhysicalServerResponse(PhysicalServerBase):
    id: int
    used_cores: int = 0
    used_ram_gb: int = 0
    usage_percent: int = 0
    vm_count: int = 0
    
    class Config:
        from_attributes = True
