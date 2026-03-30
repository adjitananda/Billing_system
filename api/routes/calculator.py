"""
API для калькулятора "what-if" анализа цен.
"""

from typing import List, Dict, Any, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from mysql.connector import MySQLConnection
from pydantic import BaseModel

from api.dependencies import get_db
from services.billing_service import (
    get_active_servers_on_date,
    get_config_on_date,
    get_prices_on_date,
    calculate_server_cost,
    calculate_server_cost_with_custom_prices
)

router = APIRouter()


class CalculateRequest(BaseModel):
    calculation_type: str  # "all_clients", "client", "server"
    client_id: Optional[int] = None
    server_id: Optional[int] = None
    custom_prices: Dict[str, float]  # {"cpu": float, "ram": float, "nvme": float, "hdd": float}
    markup_percent: float = 20.0


class ServerResult(BaseModel):
    server_id: int
    server_name: str
    current_daily: float
    current_monthly: float
    calculated_daily: float
    calculated_monthly: float
    markedup_daily: float
    markedup_monthly: float


class ClientResult(BaseModel):
    client_id: int
    client_name: str
    servers: List[ServerResult]
    client_current_daily: float
    client_current_monthly: float
    client_calculated_daily: float
    client_calculated_monthly: float
    client_markedup_daily: float
    client_markedup_monthly: float


def get_client_name(db: MySQLConnection, client_id: int) -> str:
    """Получить имя клиента по ID."""
    cursor = db.cursor()
    cursor.execute("SELECT name FROM clients WHERE id = %s", (client_id,))
    row = cursor.fetchone()
    cursor.close()
    return row[0] if row else f"Клиент #{client_id}"


@router.post("/calculate", response_model=List[ClientResult])
async def calculate(request: CalculateRequest, db: MySQLConnection = Depends(get_db)):
    """
    Рассчитывает стоимость для выбранных объектов с кастомными ценами.
    """
    # Валидация
    if request.calculation_type == "client" and not request.client_id:
        raise HTTPException(status_code=400, detail="client_id required for client calculation")
    if request.calculation_type == "server" and not request.server_id:
        raise HTTPException(status_code=400, detail="server_id required for server calculation")
    
    today = date.today().isoformat()
    
    # Получаем все активные серверы
    all_active_servers = get_active_servers_on_date(db, today)
    
    # Фильтруем по типу расчета
    if request.calculation_type == "all_clients":
        servers_to_calc = all_active_servers
    elif request.calculation_type == "client":
        servers_to_calc = [s for s in all_active_servers if s.get("client_id") == request.client_id]
        if not servers_to_calc:
            raise HTTPException(status_code=404, detail=f"No active servers for client {request.client_id}")
    else:  # server
        servers_to_calc = [s for s in all_active_servers if s.get("id") == request.server_id]
        if not servers_to_calc:
            raise HTTPException(status_code=404, detail=f"Server {request.server_id} not found or not active")
    
    # Получаем текущие цены для расчета current
    current_prices = get_prices_on_date(db, today)
    if not current_prices:
        raise HTTPException(status_code=500, detail="No prices found for current date")
    
    # Группируем по клиентам
    clients_data: Dict[int, Dict] = {}
    
    for server in servers_to_calc:
        server_id = server["id"]
        server_name = server["name"]
        client_id = server["client_id"]
        
        # Получаем конфигурацию
        config = get_config_on_date(db, server_id, today)
        if not config:
            continue
        
        # Текущая стоимость
        current_cost_dict = calculate_server_cost(config, current_prices)
        current_daily = float(current_cost_dict["total_cost"])
        current_monthly = current_daily * 31
        
        # Расчётная стоимость с кастомными ценами
        calculated_daily = calculate_server_cost_with_custom_prices(db, server_id, today, request.custom_prices)
        calculated_monthly = calculated_daily * 31
        
        # С наценкой
        markedup_daily = calculated_daily * (1 + request.markup_percent / 100)
        markedup_monthly = markedup_daily * 31
        
        # Создаем результат для сервера
        server_result = {
            "server_id": server_id,
            "server_name": server_name,
            "current_daily": round(current_daily, 2),
            "current_monthly": round(current_monthly, 2),
            "calculated_daily": round(calculated_daily, 2),
            "calculated_monthly": round(calculated_monthly, 2),
            "markedup_daily": round(markedup_daily, 2),
            "markedup_monthly": round(markedup_monthly, 2)
        }
        
        # Добавляем в группу клиента
        if client_id not in clients_data:
            clients_data[client_id] = {
                "client_id": client_id,
                "client_name": get_client_name(db, client_id),
                "servers": [],
                "client_current_daily": 0,
                "client_current_monthly": 0,
                "client_calculated_daily": 0,
                "client_calculated_monthly": 0,
                "client_markedup_daily": 0,
                "client_markedup_monthly": 0
            }
        
        clients_data[client_id]["servers"].append(server_result)
        clients_data[client_id]["client_current_daily"] += server_result["current_daily"]
        clients_data[client_id]["client_current_monthly"] += server_result["current_monthly"]
        clients_data[client_id]["client_calculated_daily"] += server_result["calculated_daily"]
        clients_data[client_id]["client_calculated_monthly"] += server_result["calculated_monthly"]
        clients_data[client_id]["client_markedup_daily"] += server_result["markedup_daily"]
        clients_data[client_id]["client_markedup_monthly"] += server_result["markedup_monthly"]
    
    # Округляем суммы клиентов
    for client in clients_data.values():
        client["client_current_daily"] = round(client["client_current_daily"], 2)
        client["client_current_monthly"] = round(client["client_current_monthly"], 2)
        client["client_calculated_daily"] = round(client["client_calculated_daily"], 2)
        client["client_calculated_monthly"] = round(client["client_calculated_monthly"], 2)
        client["client_markedup_daily"] = round(client["client_markedup_daily"], 2)
        client["client_markedup_monthly"] = round(client["client_markedup_monthly"], 2)
    
    return list(clients_data.values())
