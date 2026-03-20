"""
Routes for Price management.
"""

from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from mysql.connector import MySQLConnection

from api.dependencies import get_db
from api.schemas import PriceCreate, PriceResponse
from models.resource_price import ResourcePrice

router = APIRouter()


def check_date_overlap(db: MySQLConnection, effective_from: date, exclude_id: int = None) -> bool:
    """Check if price with given effective_from already exists."""
    cursor = db.cursor()
    
    if exclude_id:
        query = "SELECT id FROM resource_prices WHERE effective_from = %s AND id != %s"
        cursor.execute(query, (effective_from, exclude_id))
    else:
        query = "SELECT id FROM resource_prices WHERE effective_from = %s"
        cursor.execute(query, (effective_from,))
    
    result = cursor.fetchone()
    cursor.close()
    return result is not None


@router.get("/", response_model=List[PriceResponse])
async def get_prices(db: MySQLConnection = Depends(get_db)):
    """Get all price records."""
    prices = ResourcePrice.find_all(db)
    return prices


@router.get("/current", response_model=PriceResponse)
async def get_current_price(db: MySQLConnection = Depends(get_db)):
    """Get current price (effective_from <= today, order by effective_from desc limit 1)."""
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM resource_prices 
        WHERE effective_from <= CURDATE() 
        ORDER BY effective_from DESC 
        LIMIT 1
    """)
    row = cursor.fetchone()
    cursor.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="No price found for current date")
    
    return PriceResponse(**row)


@router.get("/{date_str}", response_model=PriceResponse)
async def get_price_by_date(date_str: date, db: MySQLConnection = Depends(get_db)):
    """Get price on specific date (effective_from <= date, order by effective_from desc limit 1)."""
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM resource_prices 
        WHERE effective_from <= %s 
        ORDER BY effective_from DESC 
        LIMIT 1
    """, (date_str,))
    row = cursor.fetchone()
    cursor.close()
    
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No price found for date {date_str}"
        )
    
    return PriceResponse(**row)


@router.post("/", response_model=PriceResponse, status_code=201)
async def create_price(
    price_data: PriceCreate,
    db: MySQLConnection = Depends(get_db)
):
    """Create a new price record. Rejects if date already exists."""
    # Check for overlapping date
    if check_date_overlap(db, price_data.effective_from):
        raise HTTPException(
            status_code=400,
            detail=f"Price with effective_from {price_data.effective_from} already exists"
        )
    
    price = ResourcePrice(
        effective_from=price_data.effective_from,
        cpu_price_per_core=price_data.cpu_price_per_core,
        ram_price_per_gb=price_data.ram_price_per_gb,
        nvme_price_per_gb=price_data.nvme_price_per_gb,
        hdd_price_per_gb=price_data.hdd_price_per_gb,
    )
    price.save(db)
    return price