"""
Routes for Virtual Server management.
"""

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from mysql.connector import MySQLConnection

from api.dependencies import get_db
from api.schemas import ServerCreate, ServerResponse, ServerUpdate, ConfigHistoryEntry
from models.virtual_server import VirtualServer
from models.vm_config_history import VMConfigHistory

router = APIRouter()


def get_current_config_history(vm_id: int, db: MySQLConnection) -> List[ConfigHistoryEntry]:
    """Get config history entries for a VM."""
    history = VMConfigHistory.find_by_vm_id(db, vm_id)
    return [ConfigHistoryEntry.model_validate(h) for h in history]


def resources_changed(server: VirtualServer, update_data: ServerUpdate) -> bool:
    """Check if resource-related fields have changed."""
    resource_fields = [
        'cpu_cores', 'ram_gb', 'nvme1_gb', 'nvme2_gb', 'nvme3_gb',
        'nvme4_gb', 'nvme5_gb', 'hdd_gb'
    ]
    
    for field in resource_fields:
        new_value = getattr(update_data, field, None)
        if new_value is not None and getattr(server, field) != new_value:
            return True
    return False


@router.get("/", response_model=List[ServerResponse])
async def get_servers(
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    status: Optional[str] = Query(None, description="Filter by status (active/draft/deleted)"),
    db: MySQLConnection = Depends(get_db)
):
    """Get all servers with optional filters."""
    cursor = db.cursor(dictionary=True)
    
    query = "SELECT * FROM virtual_servers WHERE 1=1"
    params = []
    
    if client_id:
        query += " AND client_id = %s"
        params.append(client_id)
    
    if status:
        query += " AND status = %s"
        params.append(status)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    
    servers = []
    for row in rows:
        server = VirtualServer(**row)
        history = get_current_config_history(server.id, db)
        response = ServerResponse.model_validate(server)
        response.config_history = history
        servers.append(response)
    
    return servers


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(server_id: int, db: MySQLConnection = Depends(get_db)):
    """Get server by ID with config history."""
    server = VirtualServer.find_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    history = get_current_config_history(server.id, db)
    response = ServerResponse.model_validate(server)
    response.config_history = history
    return response


@router.post("/", response_model=ServerResponse, status_code=201)
async def create_server(
    server_data: ServerCreate,
    db: MySQLConnection = Depends(get_db)
):
    """Create a new server with draft status."""
    # Check if client exists
    cursor = db.cursor()
    cursor.execute("SELECT id FROM clients WHERE id = %s", (server_data.client_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="Client not found")
    cursor.close()
    
    # Create server with draft status
    server = VirtualServer(
        name=server_data.name,
        client_id=server_data.client_id,
        physical_server_id=server_data.physical_server_id,
        status='draft',  # Always start as draft
        purpose=server_data.purpose,
        os=server_data.os,
        cpu_cores=server_data.cpu_cores,
        ram_gb=server_data.ram_gb,
        nvme1_gb=server_data.nvme1_gb,
        nvme2_gb=server_data.nvme2_gb or 0,
        nvme3_gb=server_data.nvme3_gb or 0,
        nvme4_gb=server_data.nvme4_gb or 0,
        nvme5_gb=server_data.nvme5_gb or 0,
        hdd_gb=server_data.hdd_gb,
        ip_address=server_data.ip_address,
        ip_port=server_data.ip_port,
        domain_address=server_data.domain_address,
        domain_port=server_data.domain_port,
    )
    server.save(db)
    
    history = get_current_config_history(server.id, db)
    response = ServerResponse.model_validate(server)
    response.config_history = history
    return response


@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: int,
    server_data: ServerUpdate,
    db: MySQLConnection = Depends(get_db)
):
    """Update server configuration. If server is active and resources changed, create history entry."""
    server = VirtualServer.find_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Check if resources changed and server is active
    resources_changed_flag = resources_changed(server, server_data)
    was_active = server.status == 'active'
    
    # Create history entry if active and resources changed
    if was_active and resources_changed_flag:
        # Get current effective_from (today)
        effective_from = date.today()
        
        history_entry = VMConfigHistory(
            vm_id=server.id,
            effective_from=effective_from,
            cpu_cores=server.cpu_cores,
            ram_gb=server.ram_gb,
            nvme1_gb=server.nvme1_gb,
            nvme2_gb=server.nvme2_gb,
            nvme3_gb=server.nvme3_gb,
            nvme4_gb=server.nvme4_gb,
            nvme5_gb=server.nvme5_gb,
            hdd_gb=server.hdd_gb,
        )
        history_entry.save(db)
    
    # Update server fields
    update_fields = [
        'name', 'purpose', 'os', 'cpu_cores', 'ram_gb',
        'nvme1_gb', 'nvme2_gb', 'nvme3_gb', 'nvme4_gb', 'nvme5_gb', 'hdd_gb',
        'ip_address', 'ip_port', 'domain_address', 'domain_port'
    ]
    
    for field in update_fields:
        new_value = getattr(server_data, field, None)
        if new_value is not None:
            setattr(server, field, new_value)
    
    server.save(db)
    
    history = get_current_config_history(server.id, db)
    response = ServerResponse.model_validate(server)
    response.config_history = history
    return response


@router.delete("/{server_id}", status_code=204)
async def delete_server(server_id: int, db: MySQLConnection = Depends(get_db)):
    """Delete server by ID."""
    server = VirtualServer.find_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server.delete(db)
    return None


@router.post("/{server_id}/activate", response_model=ServerResponse)
async def activate_server(server_id: int, db: MySQLConnection = Depends(get_db)):
    """Activate server. Sets status to active and start_date to today."""
    server = VirtualServer.find_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if server.status == 'active':
        raise HTTPException(status_code=400, detail="Server is already active")
    
    server.status = 'active'
    server.start_date = date.today()
    server.stop_date = None
    server.save(db)
    
    history = get_current_config_history(server.id, db)
    response = ServerResponse.model_validate(server)
    response.config_history = history
    return response


@router.post("/{server_id}/deactivate", response_model=ServerResponse)
async def deactivate_server(server_id: int, db: MySQLConnection = Depends(get_db)):
    """Deactivate server. Sets status to deleted and stop_date to today."""
    server = VirtualServer.find_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if server.status == 'deleted':
        raise HTTPException(status_code=400, detail="Server is already deleted")
    
    server.status = 'deleted'
    server.stop_date = date.today()
    server.save(db)
    
    history = get_current_config_history(server.id, db)
    response = ServerResponse.model_validate(server)
    response.config_history = history
    return response