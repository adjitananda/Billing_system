from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from datetime import date

from models.physical_server import PhysicalServer
from models.virtual_server import VirtualServer
from api.schemas.physical_server import PhysicalServerCreate, PhysicalServerUpdate, PhysicalServerResponse

router = APIRouter()

@router.get("/", response_model=List[PhysicalServerResponse])
async def list_physical_servers(skip: int = 0, limit: int = 100):
    """Список всех физических серверов"""
    servers = PhysicalServer.get_all(limit=limit, offset=skip)
    
    result = []
    for server in servers:
        # Считаем количество VM на хосте
        vms = VirtualServer.get_by_physical_server(server['id'])
        vm_count = len(vms)
        
        used_cores = sum(vm.get('cpu_cores', 0) for vm in vms)
        used_ram = sum(vm.get('ram_gb', 0) for vm in vms)
        
        usage_percent = 0
        if server['total_cores'] > 0:
            usage_percent = round((used_cores / server['total_cores']) * 100)
        
        result.append({
            "id": server['id'],
            "name": server['name'],
            "total_cores": server['total_cores'],
            "total_ram_gb": server['total_ram_gb'],
            "total_nvme_gb": server['total_nvme_gb'],
            "total_sata_gb": server['total_sata_gb'],
            "used_cores": used_cores,
            "used_ram_gb": used_ram,
            "usage_percent": usage_percent,
            "vm_count": vm_count
        })
    
    return result

@router.post("/", response_model=PhysicalServerResponse, status_code=status.HTTP_201_CREATED)
async def create_physical_server(server: PhysicalServerCreate):
    """Создать новый физический сервер"""
    data = {
        "name": server.name,
        "total_cores": server.total_cores,
        "total_ram_gb": server.total_ram_gb,
        "total_nvme_gb": server.total_nvme_gb,
        "total_sata_gb": server.total_sata_gb
    }
    server_id = PhysicalServer.create(data)
    created = PhysicalServer.get_by_id(server_id)
    
    return {
        "id": created['id'],
        "name": created['name'],
        "total_cores": created['total_cores'],
        "total_ram_gb": created['total_ram_gb'],
        "total_nvme_gb": created['total_nvme_gb'],
        "total_sata_gb": created['total_sata_gb'],
        "used_cores": 0,
        "used_ram_gb": 0,
        "usage_percent": 0,
        "vm_count": 0
    }

@router.get("/{server_id}", response_model=PhysicalServerResponse)
async def get_physical_server(server_id: int):
    """Получить физический сервер по ID"""
    server = PhysicalServer.get_by_id(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Physical server not found")
    
    vms = VirtualServer.get_by_physical_server(server_id)
    used_cores = sum(vm.get('cpu_cores', 0) for vm in vms)
    used_ram = sum(vm.get('ram_gb', 0) for vm in vms)
    vm_count = len(vms)
    
    usage_percent = 0
    if server['total_cores'] > 0:
        usage_percent = round((used_cores / server['total_cores']) * 100)
    
    return {
        "id": server['id'],
        "name": server['name'],
        "total_cores": server['total_cores'],
        "total_ram_gb": server['total_ram_gb'],
        "total_nvme_gb": server['total_nvme_gb'],
        "total_sata_gb": server['total_sata_gb'],
        "used_cores": used_cores,
        "used_ram_gb": used_ram,
        "usage_percent": usage_percent,
        "vm_count": vm_count
    }

@router.put("/{server_id}", response_model=PhysicalServerResponse)
async def update_physical_server(server_id: int, server_update: PhysicalServerUpdate):
    print(f"UPDATE physical server {server_id}: {server_update.dict()}")
    """Обновить физический сервер"""
    server = PhysicalServer.get_by_id(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Physical server not found")
    
    update_data = server_update.dict(exclude_unset=True)
    if update_data:
        PhysicalServer.update(server_id, update_data)
    
    updated = PhysicalServer.get_by_id(server_id)
    vms = VirtualServer.get_by_physical_server(server_id)
    used_cores = sum(vm.get('cpu_cores', 0) for vm in vms)
    used_ram = sum(vm.get('ram_gb', 0) for vm in vms)
    vm_count = len(vms)
    
    usage_percent = 0
    if updated['total_cores'] > 0:
        usage_percent = round((used_cores / updated['total_cores']) * 100)
    
    return {
        "id": updated['id'],
        "name": updated['name'],
        "total_cores": updated['total_cores'],
        "total_ram_gb": updated['total_ram_gb'],
        "total_nvme_gb": updated['total_nvme_gb'],
        "total_sata_gb": updated['total_sata_gb'],
        "used_cores": used_cores,
        "used_ram_gb": used_ram,
        "usage_percent": usage_percent,
        "vm_count": vm_count
    }

@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_physical_server(server_id: int):
    """Удалить физический сервер (только если нет VM)"""
    server = PhysicalServer.get_by_id(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Physical server not found")
    
    vms = VirtualServer.get_by_physical_server(server_id)
    active_vms = [vm for vm in vms if vm.get('status') != 'deleted']
    if active_vms:
        raise HTTPException(status_code=400, detail="Cannot delete physical server with active VMs")
    
    PhysicalServer.delete(server_id)
