from datetime import date, datetime, time, timedelta, timezone
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import InventoryItem, WasteRecord
from .schemas import ItemCreate, ItemOut, ItemUpdate, WasteCreate, WasteOut

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HarvestGuard AI API",
    description="Inventory, expiry monitoring, and food-waste tracking.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "harvestguard-api"}

@app.get("/api/inventory", response_model=list[ItemOut])
def list_inventory(
    search: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=60),
    db: Session = Depends(get_db),
):
    stmt = select(InventoryItem).order_by(InventoryItem.name)
    if search:
        stmt = stmt.where(InventoryItem.name.ilike(f"%{search}%"))
    if category:
        stmt = stmt.where(InventoryItem.category == category)
    return list(db.scalars(stmt).all())

@app.post("/api/inventory", response_model=ItemOut, status_code=201)
def create_inventory_item(payload: ItemCreate, db: Session = Depends(get_db)):
    item = InventoryItem(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="SKU already exists")
    return item

@app.get("/api/inventory/{item_id}", response_model=ItemOut)
def get_inventory_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item

@app.patch("/api/inventory/{item_id}", response_model=ItemOut)
def update_inventory_item(
    item_id: int, payload: ItemUpdate, db: Session = Depends(get_db)
):
    item = db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item

@app.delete("/api/inventory/{item_id}", status_code=204)
def delete_inventory_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    db.delete(item)
    db.commit()
    return None

@app.get("/api/alerts/expiry", response_model=list[ItemOut])
def expiry_alerts(
    days: int = Query(default=3, ge=0, le=90),
    db: Session = Depends(get_db),
):
    cutoff = date.today() + timedelta(days=days)
    stmt = (
        select(InventoryItem)
        .where(
            InventoryItem.expiry_date.is_not(None),
            InventoryItem.expiry_date <= cutoff,
        )
        .order_by(InventoryItem.expiry_date)
    )
    return list(db.scalars(stmt).all())

@app.get("/api/alerts/low-stock", response_model=list[ItemOut])
def low_stock_alerts(db: Session = Depends(get_db)):
    stmt = (
        select(InventoryItem)
        .where(InventoryItem.quantity <= InventoryItem.reorder_level)
        .order_by(InventoryItem.name)
    )
    return list(db.scalars(stmt).all())

@app.post("/api/waste", response_model=WasteOut, status_code=201)
def create_waste_record(payload: WasteCreate, db: Session = Depends(get_db)):
    if payload.item_id is not None and db.get(InventoryItem, payload.item_id) is None:
        raise HTTPException(status_code=404, detail="Linked inventory item not found")

    record = WasteRecord(**payload.model_dump())
    db.add(record)
    if payload.item_id is not None:
        item = db.get(InventoryItem, payload.item_id)
        if item is not None:
            if payload.quantity > item.quantity:
                raise HTTPException(
                    status_code=422,
                    detail="Waste quantity cannot exceed available inventory",
                )
            item.quantity -= payload.quantity
    db.commit()
    db.refresh(record)
    return record

@app.get("/api/waste", response_model=list[WasteOut])
def list_waste(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(WasteRecord).order_by(WasteRecord.recorded_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())

@app.get("/api/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    today = date.today()
    expiry_cutoff = today + timedelta(days=3)
    inventory = list(db.scalars(select(InventoryItem)).all())
    start_of_week = datetime.combine(
        today - timedelta(days=today.weekday()), time.min, tzinfo=timezone.utc
    )
    waste_cost = db.scalar(
        select(func.coalesce(func.sum(WasteRecord.quantity * WasteRecord.unit_cost), 0))
        .where(WasteRecord.recorded_at >= start_of_week)
    ) or 0

    return {
        "item_count": len(inventory),
        "inventory_value": round(sum(i.quantity * i.unit_cost for i in inventory), 2),
        "expiring_soon_count": sum(
            1 for i in inventory
            if i.expiry_date is not None and today <= i.expiry_date <= expiry_cutoff
        ),
        "expired_count": sum(
            1 for i in inventory
            if i.expiry_date is not None and i.expiry_date < today
        ),
        "low_stock_count": sum(1 for i in inventory if i.quantity <= i.reorder_level),
        "waste_cost_this_week": round(float(waste_cost), 2),
        "currency": "PHP",
        "data_source": "database",
    }
