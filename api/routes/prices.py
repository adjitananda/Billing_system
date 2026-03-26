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


def is_price_used_in_billing(db: MySQLConnection, price_id: int) -> bool:
    """Check if price is used in billing records."""
    cursor = db.cursor()
    # Проверяем, есть ли записи биллинга, созданные в период действия этой цены
    cursor.execute("""
        SELECT COUNT(*) FROM daily_billing db
        JOIN resource_prices p ON db.billing_date >= p.effective_from
        WHERE p.id = %s AND db.billing_date < (
            SELECT MIN(effective_from) FROM resource_prices WHERE effective_from > p.effective_from
        )
    """, (price_id,))
    count = cursor.fetchone()[0]
    cursor.close()
    return count > 0


@router.get("/", response_model=List[PriceResponse])
async def get_prices(db: MySQLConnection = Depends(get_db)):
    """Get all price records."""
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, effective_from, cpu_price_per_core, ram_price_per_gb, 
               nvme_price_per_gb, hdd_price_per_gb, created_at 
        FROM resource_prices 
        ORDER BY effective_from DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    
    # Convert Decimal to float for JSON serialization
    for row in rows:
        for key in ['cpu_price_per_core', 'ram_price_per_gb', 'nvme_price_per_gb', 'hdd_price_per_gb']:
            if row.get(key) is not None:
                row[key] = float(row[key])
    
    return rows


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
    
    # Convert Decimal to float
    for key in ['cpu_price_per_core', 'ram_price_per_gb', 'nvme_price_per_gb', 'hdd_price_per_gb']:
        if row.get(key) is not None:
            row[key] = float(row[key])
    
    return PriceResponse(**row)


@router.get("/by-id/{price_id}", response_model=PriceResponse)
async def get_price_by_id(price_id: int, db: MySQLConnection = Depends(get_db)):
    """Get price by ID."""
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM resource_prices WHERE id = %s", (price_id,))
    row = cursor.fetchone()
    cursor.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Price not found")
    
    # Convert Decimal to float
    for key in ['cpu_price_per_core', 'ram_price_per_gb', 'nvme_price_per_gb', 'hdd_price_per_gb']:
        if row.get(key) is not None:
            row[key] = float(row[key])
    
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
    
    # Convert Decimal to float
    for key in ['cpu_price_per_core', 'ram_price_per_gb', 'nvme_price_per_gb', 'hdd_price_per_gb']:
        if row.get(key) is not None:
            row[key] = float(row[key])
    
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
    
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO resource_prices 
        (effective_from, cpu_price_per_core, ram_price_per_gb, nvme_price_per_gb, hdd_price_per_gb)
        VALUES (%s, %s, %s, %s, %s)
    """, (price_data.effective_from, price_data.cpu_price_per_core, 
          price_data.ram_price_per_gb, price_data.nvme_price_per_gb, 
          price_data.hdd_price_per_gb))
    db.commit()
    price_id = cursor.lastrowid
    cursor.close()
    
    # Fetch created record
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM resource_prices WHERE id = %s", (price_id,))
    row = cursor.fetchone()
    cursor.close()
    
    # Convert Decimal to float
    for key in ['cpu_price_per_core', 'ram_price_per_gb', 'nvme_price_per_gb', 'hdd_price_per_gb']:
        if row.get(key) is not None:
            row[key] = float(row[key])
    
    return PriceResponse(**row)


@router.put("/{price_id}", response_model=PriceResponse)
async def update_price(
    price_id: int,
    price_data: PriceCreate,
    db: MySQLConnection = Depends(get_db)
):
    """Update price by ID (only if not used in billing)."""
    cursor = db.cursor(dictionary=True)
    
    # Check if price exists
    cursor.execute("SELECT id, effective_from FROM resource_prices WHERE id = %s", (price_id,))
    price = cursor.fetchone()
    if not price:
        cursor.close()
        raise HTTPException(status_code=404, detail="Price not found")
    
    # Check if this price is used in billing
    if is_price_used_in_billing(db, price_id):
        cursor.close()
        raise HTTPException(status_code=400, detail="Cannot edit price that is already used in billing")
    
    # Update price
    cursor.execute("""
        UPDATE resource_prices 
        SET effective_from = %s, cpu_price_per_core = %s, ram_price_per_gb = %s,
            nvme_price_per_gb = %s, hdd_price_per_gb = %s
        WHERE id = %s
    """, (price_data.effective_from, price_data.cpu_price_per_core,
          price_data.ram_price_per_gb, price_data.nvme_price_per_gb,
          price_data.hdd_price_per_gb, price_id))
    db.commit()
    
    # Fetch updated price
    cursor.execute("SELECT * FROM resource_prices WHERE id = %s", (price_id,))
    row = cursor.fetchone()
    cursor.close()
    
    # Convert Decimal to float
    for key in ['cpu_price_per_core', 'ram_price_per_gb', 'nvme_price_per_gb', 'hdd_price_per_gb']:
        if row.get(key) is not None:
            row[key] = float(row[key])
    
    return PriceResponse(**row)


@router.delete("/{price_id}", status_code=204)
async def delete_price(
    price_id: int,
    db: MySQLConnection = Depends(get_db)
):
    """Delete price by ID (only if not used in billing)."""
    cursor = db.cursor(dictionary=True)
    
    # Check if price exists
    cursor.execute("SELECT id FROM resource_prices WHERE id = %s", (price_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="Price not found")
    
    # Check if this price is used in billing
    if is_price_used_in_billing(db, price_id):
        cursor.close()
        raise HTTPException(status_code=400, detail="Cannot delete price that is already used in billing")
    
    cursor.execute("DELETE FROM resource_prices WHERE id = %s", (price_id,))
    db.commit()
    cursor.close()
    return None
