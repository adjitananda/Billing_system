"""
Pydantic schemas for Client endpoints.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ClientCreate(BaseModel):
    """Schema for creating a new client."""
    name: str


class ClientUpdate(BaseModel):
    """Schema for updating a client."""
    name: str | None = None


class ClientResponse(BaseModel):
    """Schema for client response."""
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)