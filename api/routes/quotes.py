# billing_system/api/routes/quotes.py
"""
Маршруты для коммерческого предложения (КП)
FastAPI версия
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict
from datetime import date
from mysql.connector import Error

from api.dependencies import get_db
from services.billing_service import calculate_server_cost_with_custom_prices

router = APIRouter(tags=["Коммерческое предложение"])


class CustomPrices(BaseModel):
    cpu: float
    ram: float
    nvme: float
    hdd: float


class GenerateQuoteRequest(BaseModel):
    custom_prices: CustomPrices
    markup_percent: float = 20.0


class ServerQuoteItem(BaseModel):
    server_id: int
    server_name: str
    cpu: int
    ram: int
    nvme_disk: int
    hdd_disk: int
    price_per_day: float
    price_per_30_days: float


class TotalsQuote(BaseModel):
    cpu: int
    ram: int
    nvme: int
    hdd: int
    price_per_day: float
    price_per_30_days: float


class GenerateQuoteResponse(BaseModel):
    client_id: int
    client_name: str
    date: str
    markup_percent: float
    servers: List[ServerQuoteItem]
    totals: TotalsQuote


class CurrentPricesResponse(BaseModel):
    cpu: float
    ram: float
    nvme: float
    hdd: float


@router.get("/current-prices", response_model=CurrentPricesResponse)
async def get_current_prices(conn=Depends(get_db)):
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT cpu_price_per_core, ram_price_per_gb, nvme_price_per_gb, hdd_price_per_gb
            FROM resource_prices
            WHERE effective_from <= CURDATE()
            ORDER BY effective_from DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if row:
            prices = {
                'cpu': float(row['cpu_price_per_core']),
                'ram': float(row['ram_price_per_gb']),
                'nvme': float(row['nvme_price_per_gb']),
                'hdd': float(row['hdd_price_per_gb'])
            }
        else:
            prices = {'cpu': 0.0, 'ram': 0.0, 'nvme': 0.0, 'hdd': 0.0}
        
        return CurrentPricesResponse(**prices)
        
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()


@router.post("/clients/{client_id}/generate-quote", response_model=GenerateQuoteResponse)
async def generate_quote(client_id: int, request: GenerateQuoteRequest, conn=Depends(get_db)):
    custom_prices_dict: Dict[str, float] = {
        'cpu': request.custom_prices.cpu,
        'ram': request.custom_prices.ram,
        'nvme': request.custom_prices.nvme,
        'hdd': request.custom_prices.hdd
    }
    markup_percent = request.markup_percent
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id, name FROM clients WHERE id = %s", (client_id,))
        client = cursor.fetchone()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        cursor.execute("""
            SELECT id, name, cpu_cores as cpu, ram_gb as ram, 
                   (nvme1_gb + nvme2_gb + nvme3_gb + nvme4_gb + nvme5_gb) as nvme_disk,
                   hdd_gb as hdd_disk
            FROM virtual_servers
            WHERE client_id = %s AND status_id = 1
        """, (client_id,))
        servers = cursor.fetchall()
        
        if not servers:
            raise HTTPException(status_code=404, detail="No active servers found for this client")
        
        today_str = date.today().isoformat()
        servers_data = []
        totals = {
            'cpu': 0,
            'ram': 0,
            'nvme': 0,
            'hdd': 0,
            'price_per_day': 0.0,
            'price_per_30_days': 0.0
        }
        
        for server in servers:
            server_id = server['id']
            
            base_price_per_day = calculate_server_cost_with_custom_prices(
                conn=conn,
                server_id=server_id,
                target_date=today_str,
                custom_prices=custom_prices_dict
            )
            
            price_per_day = base_price_per_day * (1 + markup_percent / 100)
            price_per_30_days = price_per_day * 30
            
            server_data = ServerQuoteItem(
                server_id=server['id'],
                server_name=server['name'],
                cpu=server['cpu'],
                ram=server['ram'],
                nvme_disk=server['nvme_disk'],
                hdd_disk=server['hdd_disk'],
                price_per_day=round(price_per_day, 2),
                price_per_30_days=round(price_per_30_days, 2)
            )
            servers_data.append(server_data)
            
            totals['cpu'] += server['cpu']
            totals['ram'] += server['ram']
            totals['nvme'] += server['nvme_disk']
            totals['hdd'] += server['hdd_disk']
            totals['price_per_day'] += price_per_day
            totals['price_per_30_days'] += price_per_30_days
        
        totals['price_per_day'] = round(totals['price_per_day'], 2)
        totals['price_per_30_days'] = round(totals['price_per_30_days'], 2)
        
        response = GenerateQuoteResponse(
            client_id=client['id'],
            client_name=client['name'],
            date=today_str,
            markup_percent=markup_percent,
            servers=servers_data,
            totals=TotalsQuote(**totals)
        )
        
        return response
        
    except HTTPException:
        raise
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    finally:
        cursor.close()
