# billing_system/api/routes/quotes.py
"""
Маршруты для коммерческого предложения (КП)
FastAPI версия
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import date
from mysql.connector import Error

from api.dependencies import get_db

router = APIRouter(tags=["Коммерческое предложение"])


class CustomPrices(BaseModel):
    cpu: float
    ram: float
    nvme: float
    hdd: float


class MarkupPercent(BaseModel):
    cpu: float = 30.0
    ram: float = 38.0
    nvme: float = 0.0
    hdd: float = 20.0


class GenerateQuoteRequest(BaseModel):
    custom_prices: CustomPrices
    markup_percent: MarkupPercent


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
    markup_percent: MarkupPercent
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
    custom_prices = request.custom_prices
    markup = request.markup_percent
    
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
            cpu_cores = server['cpu']
            ram_gb = server['ram']
            nvme_gb = server['nvme_disk']
            hdd_gb = server['hdd_disk']
            
            # Расчёт стоимости каждого компонента с индивидуальной наценкой
            cost_cpu = cpu_cores * custom_prices.cpu * (1 + markup.cpu / 100)
            cost_ram = ram_gb * custom_prices.ram * (1 + markup.ram / 100)
            cost_nvme = nvme_gb * custom_prices.nvme * (1 + markup.nvme / 100)
            cost_hdd = hdd_gb * custom_prices.hdd * (1 + markup.hdd / 100)
            
            price_per_day = cost_cpu + cost_ram + cost_nvme + cost_hdd
            price_per_30_days = price_per_day * 30
            
            server_data = ServerQuoteItem(
                server_id=server['id'],
                server_name=server['name'],
                cpu=cpu_cores,
                ram=ram_gb,
                nvme_disk=nvme_gb,
                hdd_disk=hdd_gb,
                price_per_day=round(price_per_day, 2),
                price_per_30_days=round(price_per_30_days, 2)
            )
            servers_data.append(server_data)
            
            totals['cpu'] += cpu_cores
            totals['ram'] += ram_gb
            totals['nvme'] += nvme_gb
            totals['hdd'] += hdd_gb
            totals['price_per_day'] += price_per_day
            totals['price_per_30_days'] += price_per_30_days
        
        totals['price_per_day'] = round(totals['price_per_day'], 2)
        totals['price_per_30_days'] = round(totals['price_per_30_days'], 2)
        
        response = GenerateQuoteResponse(
            client_id=client['id'],
            client_name=client['name'],
            date=today_str,
            markup_percent=markup,
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

# ========== КОНКУРЕНТЫ ==========

class CompetitorQuoteServer(BaseModel):
    server_id: int
    server_name: str
    cpu: int
    ram: int
    nvme_disk: int
    hdd_disk: int
    price_per_day: float
    price_per_30_days: float


class CompetitorQuoteTotals(BaseModel):
    cpu: int
    ram: int
    nvme: int
    hdd: int
    price_per_day: float
    price_per_30_days: float


class CompetitorQuoteResponse(BaseModel):
    competitor_id: int
    competitor_name: str
    website: Optional[str] = None
    servers: List[CompetitorQuoteServer]
    totals: CompetitorQuoteTotals


@router.get("/clients/{client_id}/competitor-quotes", response_model=List[CompetitorQuoteResponse])
async def get_competitor_quotes(client_id: int, conn=Depends(get_db)):
    """
    Получить расчёты КП для всех активных конкурентов
    """
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Проверяем существование клиента
        cursor.execute("SELECT id, name FROM clients WHERE id = %s", (client_id,))
        client = cursor.fetchone()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Получаем активные серверы клиента
        cursor.execute("""
            SELECT id, name, cpu_cores as cpu, ram_gb as ram, 
                   (nvme1_gb + nvme2_gb + nvme3_gb + nvme4_gb + nvme5_gb) as nvme_disk,
                   hdd_gb as hdd_disk
            FROM virtual_servers
            WHERE client_id = %s AND status_id = 1
        """, (client_id,))
        servers = cursor.fetchall()
        
        if not servers:
            return []
        
        # Получаем активных конкурентов
        cursor.execute("""
            SELECT c.id, c.name, c.website, 
                   cp.cpu_price, cp.ram_price, cp.nvme_price, cp.hdd_price
            FROM competitors c
            LEFT JOIN competitor_prices cp ON c.id = cp.competitor_id
            WHERE c.is_active = TRUE
            ORDER BY c.sort_order ASC, c.name ASC
        """)
        competitors = cursor.fetchall()
        
        results = []
        
        for comp in competitors:
            servers_data = []
            totals = {
                'cpu': 0,
                'ram': 0,
                'nvme': 0,
                'hdd': 0,
                'price_per_day': 0.0,
                'price_per_30_days': 0.0
            }
            
            comp_prices = {
                'cpu': float(comp.get('cpu_price', 0) or 0),
                'ram': float(comp.get('ram_price', 0) or 0),
                'nvme': float(comp.get('nvme_price', 0) or 0),
                'hdd': float(comp.get('hdd_price', 0) or 0)
            }
            
            for server in servers:
                cpu_cores = server['cpu']
                ram_gb = server['ram']
                nvme_gb = server['nvme_disk']
                hdd_gb = server['hdd_disk']
                
                # Расчёт без наценок
                price_per_day = (cpu_cores * comp_prices['cpu'] +
                                ram_gb * comp_prices['ram'] +
                                nvme_gb * comp_prices['nvme'] +
                                hdd_gb * comp_prices['hdd'])
                price_per_30_days = price_per_day * 30
                
                server_data = CompetitorQuoteServer(
                    server_id=server['id'],
                    server_name=server['name'],
                    cpu=cpu_cores,
                    ram=ram_gb,
                    nvme_disk=nvme_gb,
                    hdd_disk=hdd_gb,
                    price_per_day=round(price_per_day, 2),
                    price_per_30_days=round(price_per_30_days, 2)
                )
                servers_data.append(server_data)
                
                totals['cpu'] += cpu_cores
                totals['ram'] += ram_gb
                totals['nvme'] += nvme_gb
                totals['hdd'] += hdd_gb
                totals['price_per_day'] += price_per_day
                totals['price_per_30_days'] += price_per_30_days
            
            totals['price_per_day'] = round(totals['price_per_day'], 2)
            totals['price_per_30_days'] = round(totals['price_per_30_days'], 2)
            
            results.append(CompetitorQuoteResponse(
                competitor_id=comp['id'],
                competitor_name=comp['name'],
                website=comp.get('website'),
                servers=servers_data,
                totals=CompetitorQuoteTotals(**totals)
            ))
        
        return results
        
    except HTTPException:
        raise
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    finally:
        cursor.close()
