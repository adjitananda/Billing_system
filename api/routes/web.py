import os
import json
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx
from decimal import Decimal
from config.database import get_connection
from services.billing_service import get_active_servers_on_date, get_config_on_date, get_prices_on_date, calculate_server_cost

router = APIRouter()
templates = Jinja2Templates(directory="templates")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

async def api_request(method: str, endpoint: str, **kwargs):
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    async with httpx.AsyncClient() as client:
        url = f"{API_BASE_URL}{endpoint}"
        response = await client.request(method, url, follow_redirects=True, **kwargs)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        if response.status_code == 204:
            return None
        return response.json()

# ==================== ГЛАВНАЯ ====================
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная панель (dashboard)"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        # Получаем статистику за последние 30 дней
        try:
            summary = await api_request("GET", f"/reports/summary?start_date={start_date}&end_date={end_date}&group_by=day")
            days = [item["date"] for item in summary.get("days", [])]
            amounts = [item["amount"] for item in summary.get("days", [])]
            total_month = summary.get("total", 0)
        except:
            days, amounts, total_month = [], [], 0
        
        # Получаем общую статистику
        try:
            clients = await api_request("GET", "/clients/")
            total_clients = len(clients)
        except:
            total_clients = 0
        
        try:
            servers = await api_request("GET", "/servers/")
            active_servers = len([s for s in servers if s.get("status") == "active"])
            total_servers = len(servers)
        except:
            active_servers, total_servers = 0, 0
        
        # Получаем загрузку ДЦ
        try:
            today = date.today().isoformat()
            dc_report = await api_request("GET", f"/reports/datacenter?date={today}")
            total_usage = 0
            total_servers_count = len(dc_report.get("physical_servers", []))
            for server in dc_report.get("physical_servers", []):
                total_usage += server.get("usage_percent", {}).get("cores", 0)
            dc_load = total_usage / total_servers_count if total_servers_count > 0 else 0
        except:
            dc_load = 0
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "total_month": total_month,
            "active_servers": active_servers,
            "total_servers": total_servers,
            "total_clients": total_clients,
            "dc_load": dc_load,
            "days": days,
            "amounts": amounts
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)}, status_code=500)

@router.get("/clients", response_class=HTMLResponse)
@router.get("/clients", response_class=HTMLResponse)
async def list_clients(request: Request, search: str = ""):
    try:
        clients = await api_request("GET", "/clients/with-monthly-total")
        
        # Добавляем расчет daily_total для каждого клиента
        from decimal import Decimal
        from config.database import get_connection
        from services.billing_service import get_active_servers_on_date, get_config_on_date, get_prices_on_date, calculate_server_cost
        from datetime import date
        
        conn = get_connection()
        today = date.today().isoformat()
        active_servers = get_active_servers_on_date(conn, today)
        prices = get_prices_on_date(conn, today)
        
        # Создаем словарь daily_total по client_id
        daily_totals = {}
        if prices:
            for server in active_servers:
                client_id = server.get('client_id')
                config = get_config_on_date(conn, server['id'], today)
                if config:
                    cost_dict = calculate_server_cost(config, prices)
                    daily_totals[client_id] = daily_totals.get(client_id, 0) + float(cost_dict['total_cost'])
        conn.close()
        
        # Добавляем daily_total к каждому клиенту
        for client in clients:
            client['daily_total'] = daily_totals.get(client['id'], 0.0)
        
        if search:
            clients = [c for c in clients if search.lower() in c.get("name", "").lower()]
        try:
            servers = await api_request("GET", "/servers/")
        except:
            servers = []
        for client in clients:
            client_servers = [s for s in servers if s.get("client_id") == client["id"]]
            client["server_count"] = len(client_servers)
        return templates.TemplateResponse("clients/list.html", {"request": request, "clients": clients, "search": search})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)}, status_code=500)

async def create_client_form(request: Request):
    return templates.TemplateResponse("clients/form.html", {"request": request, "client": None})

@router.post("/clients/create")
async def create_client(request: Request, name: str = Form(...)):
    await api_request("POST", "/clients/", json={"name": name})
    return RedirectResponse(url="/clients", status_code=303)

@router.get("/clients/{client_id}/edit", response_class=HTMLResponse)
async def edit_client_form(request: Request, client_id: int):
    client = await api_request("GET", f"/clients/{client_id}")
    return templates.TemplateResponse("clients/form.html", {"request": request, "client": client})

@router.post("/clients/{client_id}/edit")
async def edit_client(request: Request, client_id: int, name: str = Form(...)):
    await api_request("PUT", f"/clients/{client_id}", json={"name": name})
    return RedirectResponse(url="/clients", status_code=303)

@router.post("/clients/{client_id}/delete")
async def delete_client(request: Request, client_id: int):
    """Удаление клиента"""
    try:
        await api_request("DELETE", f"/clients/{client_id}")
        return RedirectResponse(url="/clients", status_code=303)
    except HTTPException as e:
        if e.status_code == 400 and "Cannot delete client with existing servers" in str(e.detail):
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "error": "Нельзя удалить клиента, у которого есть серверы. Сначала удалите все серверы клиента."},
                status_code=400
            )
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e.detail)}, status_code=e.status_code)

@router.get("/clients/{client_id}", response_class=HTMLResponse)
async def client_detail(request: Request, client_id: int):
    """Карточка клиента"""
    client = await api_request("GET", f"/clients/{client_id}")
    try:
        servers = await api_request("GET", f"/clients/{client_id}/servers")
        
        # Получаем имена хостов для серверов
        try:
            physical_servers = await api_request("GET", "/physical-servers/")
            host_dict = {h["id"]: h["name"] for h in physical_servers}
            for server in servers:
                server["physical_server_name"] = host_dict.get(server.get("physical_server_id"))
        except:
            pass
    except:
        servers = []
    
    # Расчет дневной и месячной стоимости
    daily_cost = 0.0
    try:
        conn = get_connection()
        today = date.today().isoformat()
        
        # Получаем активные серверы на сегодня
        active_servers = get_active_servers_on_date(conn, today)
        # Фильтруем по client_id
        client_servers = [s for s in active_servers if s.get("client_id") == client_id]
        
        if client_servers:
            # Получаем цены на сегодня
            prices = get_prices_on_date(conn, today)
            if prices:
                for server in client_servers:
                    # Получаем конфигурацию на сегодня
                    config = get_config_on_date(conn, server["id"], today)
                    if config:
                        cost_dict = calculate_server_cost(config, prices)
                        daily_cost += float(cost_dict["total_cost"])
        conn.close()
    except Exception as e:
        print(f"Error calculating daily cost: {e}")
        daily_cost = 0.0
    
    monthly_cost_approx = daily_cost * 31
    
    return templates.TemplateResponse("clients/detail.html", {
        "request": request,
        "client": client,
        "servers": servers,
        "daily_cost": daily_cost,
        "monthly_cost_approx": monthly_cost_approx
    })

@router.get("/servers", response_class=HTMLResponse)

async def list_servers(request: Request, status: str = "", client_id: str = ""):
    """Список серверов"""
    servers = await api_request("GET", "/servers/")
    
    # Получаем список клиентов для сопоставления ID с именами
    try:
        clients = await api_request("GET", "/clients/")
        client_dict = {c["id"]: c["name"] for c in clients}
    except:
        client_dict = {}
    
    # Получаем список хостов для сопоставления ID с именами
    try:
        physical_servers = await api_request("GET", "/physical-servers/")
        host_dict = {h["id"]: h["name"] for h in physical_servers}
    except:
        host_dict = {}
    
    # Добавляем имена клиентов и хостов к каждому серверу
    for server in servers:
        server["client_name"] = client_dict.get(server.get("client_id"))
        server["physical_server_name"] = host_dict.get(server.get("physical_server_id"))
    
    if status:
        servers = [s for s in servers if s.get("status") == status]
    if client_id and client_id.isdigit():
        servers = [s for s in servers if s.get("client_id") == int(client_id)]
    
    return templates.TemplateResponse("servers/list.html", {
        "request": request, "servers": servers, "status": status, "client_id": client_id, "clients": clients
    })

@router.get("/servers/create", response_class=HTMLResponse)
async def create_server_form(request: Request, client_id: int = None):
    try:
        clients = await api_request("GET", "/clients/")
    except:
        clients = []
    try:
        physical_servers = await api_request("GET", "/physical-servers/")
    except:
        physical_servers = []
    return templates.TemplateResponse("servers/form.html", {
        "request": request, "server": None, "clients": clients, "physical_servers": physical_servers, "client_id": client_id
    })

@router.post("/servers/create")
async def create_server(
    request: Request,
    name: str = Form(...),
    client_id: int = Form(...),
    physical_server_id: int = Form(...),
    purpose: str = Form(...),
    os: str = Form(...),
    cpu_cores: int = Form(...),
    ram_gb: int = Form(...),
    hdd_gb: int = Form(0),
    nvme1_gb: int = Form(0),
    nvme2_gb: int = Form(0),
    nvme3_gb: int = Form(0),
    nvme4_gb: int = Form(0),
    nvme5_gb: int = Form(0)
):
    """Создание сервера"""
    data = {
        "name": name,
        "client_id": client_id,
        "physical_server_id": physical_server_id,
        "purpose": purpose,
        "os": os,
        "cpu_cores": cpu_cores,
        "ram_gb": ram_gb,
        "hdd_gb": hdd_gb,
        "nvme1_gb": nvme1_gb,
        "nvme2_gb": nvme2_gb,
        "nvme3_gb": nvme3_gb,
        "nvme4_gb": nvme4_gb,
        "nvme5_gb": nvme5_gb
    }
    await api_request("POST", "/servers/", json=data)
    return RedirectResponse(url="/servers", status_code=303)

@router.get("/servers/{server_id}", response_class=HTMLResponse)
async def server_detail(request: Request, server_id: int):
    server = await api_request("GET", f"/servers/{server_id}")
    
    # Получаем имя клиента
    try:
        client = await api_request("GET", f"/clients/{server.get('client_id')}")
        server["client_name"] = client.get("name")
    except:
        server["client_name"] = None
    
    # Получаем имя хоста
    try:
        physical_server = await api_request("GET", f"/physical-servers/{server.get('physical_server_id')}")
        server["physical_server_name"] = physical_server.get("name")
    except:
        server["physical_server_name"] = None
    
    return templates.TemplateResponse("servers/detail.html", {"request": request, "server": server})

@router.get("/servers/{server_id}/edit", response_class=HTMLResponse)
async def edit_server_form(request: Request, server_id: int):
    """Форма редактирования сервера"""
    try:
        server = await api_request("GET", f"/servers/{server_id}")
        try:
            physical_servers = await api_request("GET", "/physical-servers/")
        except:
            physical_servers = []
        return templates.TemplateResponse("servers/edit.html", {"request": request, "server": server, "physical_servers": physical_servers})
        return templates.TemplateResponse("servers/edit.html", {"request": request, "server": server})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)}, status_code=500)

@router.post("/servers/{server_id}/edit")
async def edit_server(
    request: Request,
    server_id: int,
    name: str = Form(...),
    physical_server_id: int = Form(...),
    purpose: str = Form(...), ip_address: str = Form(""),
    os: str = Form(...),
    cpu_cores: int = Form(...),
    ram_gb: int = Form(...),
    hdd_gb: int = Form(0),
    nvme1_gb: int = Form(0),
    nvme2_gb: int = Form(0),
    nvme3_gb: int = Form(0),
    nvme4_gb: int = Form(0),
    nvme5_gb: int = Form(0)
):
    """Редактирование сервера"""
    data = {
        "name": name,
        "physical_server_id": physical_server_id,
        "purpose": purpose, "ip_address": ip_address,
        "os": os,
        "cpu_cores": cpu_cores,
        "ram_gb": ram_gb,
        "hdd_gb": hdd_gb,
        "nvme1_gb": nvme1_gb,
        "nvme2_gb": nvme2_gb,
        "nvme3_gb": nvme3_gb,
        "nvme4_gb": nvme4_gb,
        "nvme5_gb": nvme5_gb
    }
    await api_request("PUT", f"/servers/{server_id}", json=data)
    return RedirectResponse(url=f"/servers/{server_id}", status_code=303)


@router.post("/servers/{server_id}/activate")
async def activate_server(request: Request, server_id: int):
    await api_request("POST", f"/servers/{server_id}/activate")
    return RedirectResponse(url=f"/servers/{server_id}", status_code=303)

@router.post("/servers/{server_id}/deactivate")
async def deactivate_server(request: Request, server_id: int):
    await api_request("POST", f"/servers/{server_id}/deactivate")
    return RedirectResponse(url=f"/servers/{server_id}", status_code=303)

@router.post("/servers/{server_id}/delete")
async def delete_server(request: Request, server_id: int):
    await api_request("DELETE", f"/servers/{server_id}")
    return RedirectResponse(url="/servers", status_code=303)

# ==================== ФИЗИЧЕСКИЕ СЕРВЕРЫ ====================
@router.get("/physical-servers", response_class=HTMLResponse)
async def list_physical_servers(request: Request):
    try:
        physical_servers = await api_request("GET", "/physical-servers/")
        return templates.TemplateResponse("physical_servers/list.html", {"request": request, "physical_servers": physical_servers})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)}, status_code=500)

@router.get("/physical-servers/{server_id}", response_class=HTMLResponse)
async def physical_server_detail(request: Request, server_id: int):
    """Страница детального просмотра физического сервера"""
    physical_server = await api_request("GET", f"/physical-servers/{server_id}")
    
    # Получаем список виртуальных серверов на этом хосте
    all_vms = await api_request("GET", "/servers/")
    
    # Получаем список клиентов для сопоставления ID с именами
    try:
        clients = await api_request("GET", "/clients/")
        client_dict = {c["id"]: c["name"] for c in clients}
    except:
        client_dict = {}
    
    # Получаем список хостов для сопоставления ID с именами (для ссылок)
    try:
        physical_servers = await api_request("GET", "/physical-servers/")
        host_dict = {h["id"]: h["name"] for h in physical_servers}
    except:
        host_dict = {}
    
    # Добавляем имена клиентов и хостов к каждому серверу
    for vm in all_vms:
        vm["client_name"] = client_dict.get(vm.get("client_id"))
        vm["physical_server_name"] = host_dict.get(vm.get("physical_server_id"))
    
    vms_on_host = [vm for vm in all_vms if vm.get("physical_server_id") == server_id]
    
    return templates.TemplateResponse(
        "physical_servers/detail.html",
        {"request": request, "physical_server": physical_server, "virtual_servers": vms_on_host}
    )

async def create_physical_server_form(request: Request):
    return templates.TemplateResponse("physical_servers/form.html", {"request": request, "server": None})

@router.post("/physical-servers/create")
async def create_physical_server(request: Request, name: str = Form(...), total_cores: int = Form(...), total_ram_gb: int = Form(...), total_nvme_gb: int = Form(...), total_sata_gb: int = Form(...)):
    data = {"name": name, "total_cores": total_cores, "total_ram_gb": total_ram_gb, "total_nvme_gb": total_nvme_gb, "total_sata_gb": total_sata_gb}
    await api_request("POST", "/physical-servers/", json=data)
    return RedirectResponse(url="/physical-servers", status_code=303)

@router.get("/physical-servers/{server_id}/edit", response_class=HTMLResponse)
async def edit_physical_server_form(request: Request, server_id: int):
    server = await api_request("GET", f"/physical-servers/{server_id}")
    return templates.TemplateResponse("physical_servers/form.html", {"request": request, "server": server})

@router.post("/physical-servers/{server_id}/edit")
async def edit_physical_server(request: Request, server_id: int, name: str = Form(...), total_cores: int = Form(...), total_ram_gb: int = Form(...), total_nvme_gb: int = Form(...), total_sata_gb: int = Form(...)):
    data = {"name": name, "total_cores": total_cores, "total_ram_gb": total_ram_gb, "total_nvme_gb": total_nvme_gb, "total_sata_gb": total_sata_gb}
    await api_request("PUT", f"/physical-servers/{server_id}", json=data)
    return RedirectResponse(url="/physical-servers", status_code=303)

@router.post("/physical-servers/{server_id}/delete")
async def delete_physical_server(request: Request, server_id: int):
    await api_request("DELETE", f"/physical-servers/{server_id}")
    return RedirectResponse(url="/physical-servers", status_code=303)

# ==================== ЗАГЛУШКИ ====================
@router.get("/datacenter", response_class=HTMLResponse)
async def datacenter_page(request: Request):
    """Страница загрузки дата-центра"""
    try:
        today = date.today().isoformat()
        report = await api_request("GET", f"/reports/datacenter?date={today}")
        return templates.TemplateResponse("datacenter.html", {"request": request, "report": report})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)}, status_code=500)

@router.get("/prices", response_class=HTMLResponse)
async def list_prices(request: Request):
    """Список цен на ресурсы"""
    try:
        prices = await api_request("GET", "/prices/")
        today_str = date.today().isoformat()
        return templates.TemplateResponse("prices/list.html", {
            "request": request, 
            "prices": prices,
            "now": today_str
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)}, status_code=500)

@router.get("/prices/create", response_class=HTMLResponse)
async def create_price_form(request: Request):
    """Форма добавления цен"""
    return templates.TemplateResponse("prices/form.html", {"request": request})

@router.post("/prices/create")
async def create_price(
    request: Request,
    effective_from: str = Form(...),
    cpu_price_per_core: float = Form(...),
    ram_price_per_gb: float = Form(...),
    nvme_price_per_gb: float = Form(...),
    hdd_price_per_gb: float = Form(...)
):
    """Создание новых цен"""
    data = {
        "effective_from": effective_from,
        "cpu_price_per_core": cpu_price_per_core,
        "ram_price_per_gb": ram_price_per_gb,
        "nvme_price_per_gb": nvme_price_per_gb,
        "hdd_price_per_gb": hdd_price_per_gb
    }
    await api_request("POST", "/prices/", json=data)
    return RedirectResponse(url="/prices", status_code=303)

@router.get("/prices/{price_id}/edit", response_class=HTMLResponse)
async def edit_price_form(request: Request, price_id: int):
    """Форма редактирования цен"""
    try:
        price = await api_request("GET", f"/prices/by-id/{price_id}")
        return templates.TemplateResponse("prices/edit.html", {"request": request, "price": price})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)}, status_code=500)

@router.post("/prices/{price_id}/edit")
async def edit_price(
    request: Request,
    price_id: int,
    effective_from: str = Form(...),
    cpu_price_per_core: float = Form(...),
    ram_price_per_gb: float = Form(...),
    nvme_price_per_gb: float = Form(...),
    hdd_price_per_gb: float = Form(...)
):
    """Редактирование цен"""
    data = {
        "effective_from": effective_from,
        "cpu_price_per_core": cpu_price_per_core,
        "ram_price_per_gb": ram_price_per_gb,
        "nvme_price_per_gb": nvme_price_per_gb,
        "hdd_price_per_gb": hdd_price_per_gb
    }
    await api_request("PUT", f"/prices/{price_id}", json=data)
    return RedirectResponse(url="/prices", status_code=303)

@router.post("/prices/{price_id}/delete")
async def delete_price(request: Request, price_id: int):
    """Удаление цен"""
    try:
        await api_request("DELETE", f"/prices/{price_id}")
        return RedirectResponse(url="/prices", status_code=303)
    except HTTPException as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e.detail)}, status_code=e.status_code)


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    """Страница отчётов"""
    try:
        clients = await api_request("GET", "/clients/")
        return templates.TemplateResponse("reports/index.html", {"request": request, "clients": clients})
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": str(e)}, status_code=500)

@router.get("/calculator", response_class=HTMLResponse)
async def calculator_page(request: Request):
    """Страница калькулятора what-if анализа цен"""
    from config.database import get_connection
    from services.billing_service import get_prices_on_date
    from datetime import date
    
    # Получаем текущие цены
    conn = get_connection()
    today = date.today().isoformat()
    current_prices = get_prices_on_date(conn, today)
    conn.close()
    
    # Получаем список клиентов для выпадающего списка
    clients = await api_request("GET", "/clients/")
    
    # Преобразуем цены в словарь для шаблона
    prices_dict = {
        "cpu": float(current_prices.get("cpu_price_per_core", 0)) if current_prices else 0,
        "ram": float(current_prices.get("ram_price_per_gb", 0)) if current_prices else 0,
        "nvme": float(current_prices.get("nvme_price_per_gb", 0)) if current_prices else 0,
        "hdd": float(current_prices.get("hdd_price_per_gb", 0)) if current_prices else 0,
    }
    
    return templates.TemplateResponse("calculator/index.html", {
        "request": request,
        "current_prices": prices_dict,
        "clients": clients
    })
