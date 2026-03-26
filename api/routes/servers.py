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
from models.vm_status import VMStatus

router = APIRouter()


def get_status_id(db: MySQLConnection, status_code: str) -> int:
    """Get status ID by code."""
    cursor = db.cursor()
    status_id = VMStatus.get_status_id_by_code(cursor, status_code)
    cursor.close()
    if not status_id:
        raise HTTPException(status_code=500, detail=f"Status '{status_code}' not found in database")
    return status_id


def get_config_history(vm_id: int, db: MySQLConnection) -> List[ConfigHistoryEntry]:
    """Get config history entries for a VM."""
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, effective_from, cpu_cores, ram_gb, 
               nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb
        FROM vm_config_history 
        WHERE vm_id = %s 
        ORDER BY effective_from DESC
    """, (vm_id,))
    rows = cursor.fetchall()
    cursor.close()
    
    history = []
    for row in rows:
        history.append(ConfigHistoryEntry(
            id=row['id'],
            effective_from=row['effective_from'],
            cpu_cores=row['cpu_cores'],
            ram_gb=row['ram_gb'],
            nvme1_gb=row['nvme1_gb'],
            nvme2_gb=row['nvme2_gb'],
            nvme3_gb=row['nvme3_gb'],
            nvme4_gb=row['nvme4_gb'],
            nvme5_gb=row['nvme5_gb'],
            hdd_gb=row['hdd_gb']
        ))
    return history


def get_server_dict(cursor, server_id: int) -> dict:
    """Get server as dictionary."""
    # Используем dictionary=True для курсора, чтобы сразу получить словарь
    if not hasattr(cursor, '_dictionary') or not cursor._dictionary:
        # Если курсор не словарный, создаем временный словарный курсор
        db = cursor._connection
        dict_cursor = db.cursor(dictionary=True)
        dict_cursor.execute("""
            SELECT id, name, client_id, physical_server_id, status_id,
                   purpose, os, cpu_cores, ram_gb,
                   nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb,
                   ip_address, ip_port, domain_address, domain_port,
                   start_date, stop_date, created_at, updated_at
            FROM virtual_servers WHERE id = %s
        """, (server_id,))
        row = dict_cursor.fetchone()
        dict_cursor.close()
        return row
    
    cursor.execute("""
        SELECT id, name, client_id, physical_server_id, status_id,
               purpose, os, cpu_cores, ram_gb,
               nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb,
               ip_address, ip_port, domain_address, domain_port,
               start_date, stop_date, created_at, updated_at
        FROM virtual_servers WHERE id = %s
    """, (server_id,))
    row = cursor.fetchone()
    if not row:
        return None
    
    # Если row уже словарь, возвращаем его
    if isinstance(row, dict):
        return row
    
    # Иначе преобразуем кортеж в словарь
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def get_status_code_by_id(cursor, status_id: int) -> str:
    """Get status code by ID."""
    cursor.execute("SELECT code FROM vm_statuses WHERE id = %s", (status_id,))
    row = cursor.fetchone()
    if not row:
        return None
    # row может быть кортежем или словарём
    if isinstance(row, dict):
        return row.get('code')
    return row[0]


def calculate_daily_cost(db: MySQLConnection, server: dict) -> float:
    """Calculate daily cost for a server based on current prices."""
    # Debug print
    print(f"DEBUG: server type: {type(server)}")
    print(f"DEBUG: server keys: {server.keys() if hasattr(server, 'keys') else 'no keys'}")
    
    cursor = db.cursor(dictionary=True)
    
    # Get current prices
    cursor.execute("""
        SELECT cpu_price_per_core, ram_price_per_gb, nvme_price_per_gb, hdd_price_per_gb
        FROM resource_prices 
        WHERE effective_from <= CURDATE() 
        ORDER BY effective_from DESC 
        LIMIT 1
    """)
    prices = cursor.fetchone()
    cursor.close()
    
    if not prices:
        return 0.0
    
    # Convert Decimal to float
    cpu_price = float(prices['cpu_price_per_core'])
    ram_price = float(prices['ram_price_per_gb'])
    nvme_price = float(prices['nvme_price_per_gb'])
    hdd_price = float(prices['hdd_price_per_gb'])
    
    # Convert values to int/float
    cpu_cores = int(server.get('cpu_cores', 0))
    ram_gb = int(server.get('ram_gb', 0))
    hdd_gb = int(server.get('hdd_gb', 0))
    
    # Calculate total NVMe
    nvme_total = (int(server.get('nvme1_gb', 0)) + int(server.get('nvme2_gb', 0)) + 
                  int(server.get('nvme3_gb', 0)) + int(server.get('nvme4_gb', 0)) + 
                  int(server.get('nvme5_gb', 0)))
    
    cost = (cpu_cores * cpu_price +
            ram_gb * ram_price +
            nvme_total * nvme_price +
            hdd_gb * hdd_price)
    
    return round(cost, 2)


def build_server_response(cursor, row: dict, db: MySQLConnection) -> ServerResponse:
    """Build ServerResponse with daily cost."""
    status_code = get_status_code_by_id(cursor, row['status_id'])
    
    # Calculate daily cost
    daily_cost = calculate_daily_cost(db, row)
    
    return ServerResponse(
        id=row['id'],
        name=row['name'],
        client_id=row['client_id'],
        physical_server_id=row['physical_server_id'],
        status=status_code,
        purpose=row['purpose'],
        os=row['os'],
        cpu_cores=row['cpu_cores'],
        ram_gb=row['ram_gb'],
        nvme1_gb=row['nvme1_gb'],
        nvme2_gb=row['nvme2_gb'],
        nvme3_gb=row['nvme3_gb'],
        nvme4_gb=row['nvme4_gb'],
        nvme5_gb=row['nvme5_gb'],
        hdd_gb=row['hdd_gb'],
        ip_address=row['ip_address'],
        ip_port=row['ip_port'],
        domain_address=row['domain_address'],
        domain_port=row['domain_port'],
        start_date=row['start_date'],
        stop_date=row['stop_date'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        daily_cost=daily_cost,
        config_history=get_config_history(row['id'], db)
    )


@router.get("/", response_model=List[ServerResponse])
async def get_servers(
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    status: Optional[str] = Query(None, description="Filter by status (active/draft/deleted)"),
    db: MySQLConnection = Depends(get_db)
):
    """Get all servers with optional filters."""
    cursor = db.cursor(dictionary=True)
    
    query = """
        SELECT id, name, client_id, physical_server_id, status_id,
               purpose, os, cpu_cores, ram_gb,
               nvme1_gb, nvme2_gb, nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb,
               ip_address, ip_port, domain_address, domain_port,
               start_date, stop_date, created_at, updated_at
        FROM virtual_servers WHERE 1=1
    """
    params = []
    
    if client_id:
        query += " AND client_id = %s"
        params.append(client_id)
    
    if status:
        status_id = get_status_id(db, status)
        query += " AND status_id = %s"
        params.append(status_id)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    servers = []
    for row in rows:
        servers.append(build_server_response(cursor, row, db))
    
    cursor.close()
    return servers


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(server_id: int, db: MySQLConnection = Depends(get_db)):
    """Get server by ID with config history."""
    cursor = db.cursor(dictionary=True)
    row = get_server_dict(cursor, server_id)
    
    if not row:
        cursor.close()
        raise HTTPException(status_code=404, detail="Server not found")
    
    response = build_server_response(cursor, row, db)
    cursor.close()
    return response


@router.post("/", response_model=ServerResponse, status_code=201)
async def create_server(
    server_data: ServerCreate,
    db: MySQLConnection = Depends(get_db)
):
    """Create a new server with draft status."""
    cursor = db.cursor(dictionary=True)
    
    # Check if client exists
    cursor.execute("SELECT id FROM clients WHERE id = %s", (server_data.client_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Check if physical server exists
    cursor.execute("SELECT id FROM physical_servers WHERE id = %s", (server_data.physical_server_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="Physical server not found")
    
    # Get draft status ID
    draft_status_id = get_status_id(db, VMStatus.DRAFT)
    
    # Prepare data for creation
    server_dict = {
        'name': server_data.name,
        'client_id': server_data.client_id,
        'physical_server_id': server_data.physical_server_id,
        'status_id': draft_status_id,
        'purpose': server_data.purpose,
        'os': server_data.os,
        'cpu_cores': server_data.cpu_cores,
        'ram_gb': server_data.ram_gb,
        'nvme1_gb': server_data.nvme1_gb,
        'nvme2_gb': server_data.nvme2_gb or 0,
        'nvme3_gb': server_data.nvme3_gb or 0,
        'nvme4_gb': server_data.nvme4_gb or 0,
        'nvme5_gb': server_data.nvme5_gb or 0,
        'hdd_gb': server_data.hdd_gb,
        'ip_address': server_data.ip_address,
        'ip_port': server_data.ip_port,
        'domain_address': server_data.domain_address,
        'domain_port': server_data.domain_port,
    }
    
    try:
        server_id = VirtualServer.create(cursor, **server_dict)
        db.commit()
        
        # Fetch created server
        row = get_server_dict(cursor, server_id)
        response = build_server_response(cursor, row, db)
        cursor.close()
        return response
    except Exception as e:
        db.rollback()
        cursor.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: int,
    server_data: ServerUpdate,
    db: MySQLConnection = Depends(get_db)
):
    """Update server configuration."""
    cursor = db.cursor(dictionary=True)
    
    # Check if server exists and get current status
    row = get_server_dict(cursor, server_id)
    if not row:
        cursor.close()
        raise HTTPException(status_code=404, detail="Server not found")
    
    current_status_code = get_status_code_by_id(cursor, row['status_id'])
    
    # If server is active and resources changed, create history entry
    if current_status_code == VMStatus.ACTIVE:
        resource_fields = ['cpu_cores', 'ram_gb', 'nvme1_gb', 'nvme2_gb', 
                          'nvme3_gb', 'nvme4_gb', 'nvme5_gb', 'hdd_gb']
        changed = False
        for field in resource_fields:
            new_val = getattr(server_data, field, None)
            if new_val is not None and row[field] != new_val:
                changed = True
                break
        
        if changed:
            history_cursor = db.cursor()
            history_cursor.execute("""
                INSERT INTO vm_config_history 
                (vm_id, effective_from, cpu_cores, ram_gb, nvme1_gb, nvme2_gb, 
                 nvme3_gb, nvme4_gb, nvme5_gb, hdd_gb)
                VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s, %s, %s)
            """, (server_id, row['cpu_cores'], row['ram_gb'], row['nvme1_gb'],
                  row['nvme2_gb'], row['nvme3_gb'], row['nvme4_gb'], 
                  row['nvme5_gb'], row['hdd_gb']))
            history_cursor.close()
    
    # Build update query dynamically
    update_fields = []
    values = []
    
    for field in ['name', 'purpose', 'os', 'cpu_cores', 'ram_gb',
                  'nvme1_gb', 'nvme2_gb', 'nvme3_gb', 'nvme4_gb', 'nvme5_gb', 'hdd_gb',
                  'ip_address', 'ip_port', 'domain_address', 'domain_port']:
        new_val = getattr(server_data, field, None)
        if new_val is not None:
            update_fields.append(f"{field} = %s")
            values.append(new_val)
    
    if update_fields:
        values.append(server_id)
        query = f"UPDATE virtual_servers SET {', '.join(update_fields)} WHERE id = %s"
        cursor.execute(query, values)
        db.commit()
    
    # Fetch updated server
    row = get_server_dict(cursor, server_id)
    response = build_server_response(cursor, row, db)
    cursor.close()
    return response


@router.delete("/{server_id}", status_code=204)
async def delete_server(server_id: int, db: MySQLConnection = Depends(get_db)):
    """Delete server by ID."""
    cursor = db.cursor()
    
    cursor.execute("SELECT id FROM virtual_servers WHERE id = %s", (server_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="Server not found")
    
    try:
        cursor.execute("DELETE FROM virtual_servers WHERE id = %s", (server_id,))
        db.commit()
    except Exception as e:
        db.rollback()
        cursor.close()
        raise HTTPException(status_code=500, detail=str(e))
    
    cursor.close()
    return None


@router.post("/{server_id}/activate", response_model=ServerResponse)
async def activate_server(server_id: int, db: MySQLConnection = Depends(get_db)):
    """Activate server. Sets status to active and start_date to today."""
    cursor = db.cursor(dictionary=True)
    
    row = get_server_dict(cursor, server_id)
    if not row:
        cursor.close()
        raise HTTPException(status_code=404, detail="Server not found")
    
    current_status_code = get_status_code_by_id(cursor, row['status_id'])
    
    if current_status_code == VMStatus.ACTIVE:
        cursor.close()
        raise HTTPException(status_code=400, detail="Server is already active")
    
    active_status_id = get_status_id(db, VMStatus.ACTIVE)
    
    try:
        cursor.execute("""
            UPDATE virtual_servers 
            SET status_id = %s, start_date = CURDATE(), stop_date = NULL
            WHERE id = %s
        """, (active_status_id, server_id))
        db.commit()
    except Exception as e:
        db.rollback()
        cursor.close()
        raise HTTPException(status_code=500, detail=str(e))
    
    row = get_server_dict(cursor, server_id)
    response = build_server_response(cursor, row, db)
    cursor.close()
    return response


@router.post("/{server_id}/deactivate", response_model=ServerResponse)
async def deactivate_server(server_id: int, db: MySQLConnection = Depends(get_db)):
    """Deactivate server. Sets status to deleted and stop_date to today."""
    cursor = db.cursor(dictionary=True)
    
    row = get_server_dict(cursor, server_id)
    if not row:
        cursor.close()
        raise HTTPException(status_code=404, detail="Server not found")
    
    current_status_code = get_status_code_by_id(cursor, row['status_id'])
    
    if current_status_code == VMStatus.DELETED:
        cursor.close()
        raise HTTPException(status_code=400, detail="Server is already deleted")
    
    deleted_status_id = get_status_id(db, VMStatus.DELETED)
    
    try:
        cursor.execute("""
            UPDATE virtual_servers 
            SET status_id = %s, stop_date = CURDATE()
            WHERE id = %s
        """, (deleted_status_id, server_id))
        db.commit()
    except Exception as e:
        db.rollback()
        cursor.close()
        raise HTTPException(status_code=500, detail=str(e))
    
    row = get_server_dict(cursor, server_id)
    response = build_server_response(cursor, row, db)
    cursor.close()
    return response
