"""
Routes for Client management.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from mysql.connector import MySQLConnection

from api.dependencies import get_db
from api.schemas import ClientCreate, ClientResponse, ClientUpdate

router = APIRouter()


@router.get("/", response_model=List[ClientResponse])
async def get_clients(db: MySQLConnection = Depends(get_db)):
    """Get all clients."""
    cursor = db.cursor()
    cursor.execute("SELECT id, name, created_at, updated_at FROM clients ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    
    clients = []
    for row in rows:
        clients.append(ClientResponse(
            id=row[0],
            name=row[1],
            created_at=row[2],
            updated_at=row[3]
        ))
    return clients


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, db: MySQLConnection = Depends(get_db)):
    """Get client by ID."""
    cursor = db.cursor()
    cursor.execute("SELECT id, name, created_at, updated_at FROM clients WHERE id = %s", (client_id,))
    row = cursor.fetchone()
    cursor.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return ClientResponse(
        id=row[0],
        name=row[1],
        created_at=row[2],
        updated_at=row[3]
    )


@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(
    client_data: ClientCreate,
    db: MySQLConnection = Depends(get_db)
):
    """Create a new client."""
    cursor = db.cursor()
    
    try:
        cursor.execute("INSERT INTO clients (name) VALUES (%s)", (client_data.name,))
        db.commit()
        client_id = cursor.lastrowid
        
        # Fetch created client
        cursor.execute("SELECT id, name, created_at, updated_at FROM clients WHERE id = %s", (client_id,))
        row = cursor.fetchone()
        cursor.close()
        
        return ClientResponse(
            id=row[0],
            name=row[1],
            created_at=row[2],
            updated_at=row[3]
        )
    except Exception as e:
        db.rollback()
        cursor.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    client_data: ClientUpdate,
    db: MySQLConnection = Depends(get_db)
):
    """Update client by ID."""
    cursor = db.cursor()
    
    # Check if client exists
    cursor.execute("SELECT id, name, created_at, updated_at FROM clients WHERE id = %s", (client_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.close()
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Update only if name provided
    if client_data.name is not None:
        try:
            cursor.execute("UPDATE clients SET name = %s WHERE id = %s", (client_data.name, client_id))
            db.commit()
        except Exception as e:
            db.rollback()
            cursor.close()
            raise HTTPException(status_code=500, detail=str(e))
    
    # Fetch updated client
    cursor.execute("SELECT id, name, created_at, updated_at FROM clients WHERE id = %s", (client_id,))
    row = cursor.fetchone()
    cursor.close()
    
    return ClientResponse(
        id=row[0],
        name=row[1],
        created_at=row[2],
        updated_at=row[3]
    )


@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: int, db: MySQLConnection = Depends(get_db)):
    """Delete client by ID (only if no servers exist)."""
    cursor = db.cursor()
    
    # Check if client exists
    cursor.execute("SELECT id FROM clients WHERE id = %s", (client_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if client has any servers
    cursor.execute("SELECT COUNT(*) FROM virtual_servers WHERE client_id = %s", (client_id,))
    count = cursor.fetchone()[0]
    
    if count > 0:
        cursor.close()
        raise HTTPException(
            status_code=400,
            detail="Cannot delete client with existing servers"
        )
    
    # Delete client
    try:
        cursor.execute("DELETE FROM clients WHERE id = %s", (client_id,))
        db.commit()
    except Exception as e:
        db.rollback()
        cursor.close()
        raise HTTPException(status_code=500, detail=str(e))
    
    cursor.close()
    return None