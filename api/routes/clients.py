"""
Routes for Client management.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from mysql.connector import MySQLConnection

from api.dependencies import get_db
from api.schemas import ClientCreate, ClientResponse, ClientUpdate
from models.client import Client

router = APIRouter()


@router.get("/", response_model=List[ClientResponse])
async def get_clients(db: MySQLConnection = Depends(get_db)):
    """Get all clients."""
    clients = Client.find_all(db)
    return clients


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, db: MySQLConnection = Depends(get_db)):
    """Get client by ID."""
    client = Client.find_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(
    client_data: ClientCreate,
    db: MySQLConnection = Depends(get_db)
):
    """Create a new client."""
    client = Client(name=client_data.name)
    client.save(db)
    return client


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    client_data: ClientUpdate,
    db: MySQLConnection = Depends(get_db)
):
    """Update client by ID."""
    client = Client.find_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Update only provided fields
    if client_data.name is not None:
        client.name = client_data.name
    
    client.save(db)
    return client


@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: int, db: MySQLConnection = Depends(get_db)):
    """Delete client by ID (only if no servers exist)."""
    client = Client.find_by_id(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if client has any servers
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT COUNT(*) as count FROM virtual_servers WHERE client_id = %s",
        (client_id,)
    )
    result = cursor.fetchone()
    cursor.close()
    
    if result and result["count"] > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete client with existing servers"
        )
    
    client.delete(db)
    return None