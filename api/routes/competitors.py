# billing_system/api/routes/competitors.py
"""
Маршруты для управления конкурентами
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, Any

from api.dependencies import get_db
from models.competitor import Competitor
from models.competitor_price import CompetitorPrice

router = APIRouter(prefix="/api/competitors", tags=["Конкуренты"])
templates = Jinja2Templates(directory="templates")


# Pydantic модели
class CompetitorPrices(BaseModel):
    cpu: float = 0
    ram: float = 0
    nvme: float = 0
    hdd: float = 0


class CompetitorCreate(BaseModel):
    name: str
    website: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0
    prices: CompetitorPrices


class CompetitorUpdate(BaseModel):
    name: str
    website: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0
    prices: CompetitorPrices


class CompetitorResponse(BaseModel):
    id: int
    name: str
    website: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool
    sort_order: int
    prices: CompetitorPrices


# Веб-страницы
@router.get("/", response_class=HTMLResponse)
async def competitors_page(request: Request):
    """Страница списка конкурентов"""
    return templates.TemplateResponse("competitors/index.html", {"request": request})


@router.get("/add", response_class=HTMLResponse)
async def add_competitor_page(request: Request):
    """Страница добавления конкурента"""
    return templates.TemplateResponse("competitors/form.html", {"request": request, "competitor": None})


@router.get("/{competitor_id}/edit", response_class=HTMLResponse)
async def edit_competitor_page(request: Request, competitor_id: int):
    """Страница редактирования конкурента"""
    return templates.TemplateResponse("competitors/form.html", {"request": request, "competitor_id": competitor_id})


# API эндпоинты
@router.get("", response_model=list[Dict[str, Any]])
async def get_competitors(conn=Depends(get_db)):
    """Получить список всех конкурентов с ценами"""
    cursor = conn.cursor(dictionary=True)
    
    try:
        competitors = Competitor.get_all(cursor)
        result = []
        
        for comp in competitors:
            prices = CompetitorPrice.get_by_competitor_id(cursor, comp['id'])
            result.append({
                "id": comp['id'],
                "name": comp['name'],
                "website": comp.get('website'),
                "logo_url": comp.get('logo_url'),
                "is_active": bool(comp['is_active']),
                "sort_order": comp['sort_order'],
                "prices": {
                    "cpu": float(prices['cpu_price']) if prices else 0,
                    "ram": float(prices['ram_price']) if prices else 0,
                    "nvme": float(prices['nvme_price']) if prices else 0,
                    "hdd": float(prices['hdd_price']) if prices else 0
                }
            })
        
        return result
    finally:
        cursor.close()


@router.get("/{competitor_id}", response_model=Dict[str, Any])
async def get_competitor(competitor_id: int, conn=Depends(get_db)):
    """Получить конкурента по ID с ценами"""
    cursor = conn.cursor(dictionary=True)
    
    try:
        competitor = Competitor.get_by_id(cursor, competitor_id)
        if not competitor:
            raise HTTPException(status_code=404, detail="Competitor not found")
        
        prices = CompetitorPrice.get_by_competitor_id(cursor, competitor_id)
        
        return {
            "id": competitor['id'],
            "name": competitor['name'],
            "website": competitor.get('website'),
            "logo_url": competitor.get('logo_url'),
            "is_active": bool(competitor['is_active']),
            "sort_order": competitor['sort_order'],
            "prices": {
                "cpu": float(prices['cpu_price']) if prices else 0,
                "ram": float(prices['ram_price']) if prices else 0,
                "nvme": float(prices['nvme_price']) if prices else 0,
                "hdd": float(prices['hdd_price']) if prices else 0
            }
        }
    finally:
        cursor.close()


@router.post("", response_model=Dict[str, int])
async def create_competitor(data: CompetitorCreate, conn=Depends(get_db)):
    """Создать нового конкурента"""
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Проверка уникальности имени
        cursor.execute("SELECT id FROM competitors WHERE name = %s", (data.name,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Competitor with this name already exists")
        
        # Создаём конкурента
        comp_id = Competitor.create(cursor, {
            'name': data.name,
            'website': data.website,
            'logo_url': data.logo_url,
            'is_active': data.is_active,
            'sort_order': data.sort_order
        })
        
        # Добавляем цены
        CompetitorPrice.upsert(cursor, comp_id, {
            'cpu': data.prices.cpu,
            'ram': data.prices.ram,
            'nvme': data.prices.nvme,
            'hdd': data.prices.hdd
        })
        
        conn.commit()
        return {"id": comp_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()


@router.put("/{competitor_id}")
async def update_competitor(competitor_id: int, data: CompetitorUpdate, conn=Depends(get_db)):
    """Обновить конкурента"""
    cursor = conn.cursor(dictionary=True)
    
    try:
        competitor = Competitor.get_by_id(cursor, competitor_id)
        if not competitor:
            raise HTTPException(status_code=404, detail="Competitor not found")
        
        # Проверка уникальности имени
        cursor.execute("SELECT id FROM competitors WHERE name = %s AND id != %s", (data.name, competitor_id))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Competitor with this name already exists")
        
        Competitor.update(cursor, competitor_id, {
            'name': data.name,
            'website': data.website,
            'logo_url': data.logo_url,
            'is_active': data.is_active,
            'sort_order': data.sort_order
        })
        
        CompetitorPrice.upsert(cursor, competitor_id, {
            'cpu': data.prices.cpu,
            'ram': data.prices.ram,
            'nvme': data.prices.nvme,
            'hdd': data.prices.hdd
        })
        
        conn.commit()
        return {"message": "Updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()


@router.delete("/{competitor_id}")
async def delete_competitor(competitor_id: int, conn=Depends(get_db)):
    """Удалить конкурента"""
    cursor = conn.cursor(dictionary=True)
    
    try:
        competitor = Competitor.get_by_id(cursor, competitor_id)
        if not competitor:
            raise HTTPException(status_code=404, detail="Competitor not found")
        
        Competitor.delete(cursor, competitor_id)
        conn.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
