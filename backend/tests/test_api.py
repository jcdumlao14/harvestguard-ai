from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def setup_function():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

def sample_item(**overrides):
    data = {
        "sku": "HG-TEST-001",
        "name": "Test milk",
        "category": "Dairy",
        "quantity": 10,
        "unit": "cartons",
        "expiry_date": (date.today() + timedelta(days=2)).isoformat(),
        "unit_cost": 50,
        "reorder_level": 2,
    }
    data.update(overrides)
    return data

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_create_and_list_inventory():
    created = client.post("/api/inventory", json=sample_item())
    assert created.status_code == 201
    body = created.json()
    assert body["stock_value"] == 500
    assert body["status"] == "expiring"

    listed = client.get("/api/inventory")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

def test_duplicate_sku_returns_conflict():
    assert client.post("/api/inventory", json=sample_item()).status_code == 201
    duplicate = client.post("/api/inventory", json=sample_item(name="Another milk"))
    assert duplicate.status_code == 409

def test_patch_inventory():
    created = client.post("/api/inventory", json=sample_item())
    item_id = created.json()["id"]
    response = client.patch(f"/api/inventory/{item_id}", json={"quantity": 1})
    assert response.status_code == 200
    assert response.json()["quantity"] == 1
    assert response.json()["status"] == "low_stock"

def test_expiry_and_low_stock_alerts():
    client.post("/api/inventory", json=sample_item())
    assert len(client.get("/api/alerts/expiry").json()) == 1
    assert len(client.get("/api/alerts/low-stock").json()) == 0

def test_waste_record_reduces_inventory():
    created = client.post("/api/inventory", json=sample_item())
    item_id = created.json()["id"]
    response = client.post("/api/waste", json={
        "item_id": item_id,
        "item_name": "Test milk",
        "quantity": 2,
        "unit": "cartons",
        "unit_cost": 50,
        "reason": "Expired",
    })
    assert response.status_code == 201
    assert response.json()["total_cost"] == 100
    item = client.get(f"/api/inventory/{item_id}").json()
    assert item["quantity"] == 8

def test_waste_cannot_exceed_available_stock():
    created = client.post("/api/inventory", json=sample_item())
    item_id = created.json()["id"]
    response = client.post("/api/waste", json={
        "item_id": item_id,
        "item_name": "Test milk",
        "quantity": 11,
        "unit": "cartons",
        "unit_cost": 50,
        "reason": "Expired",
    })
    assert response.status_code == 422

def test_analytics_summary_uses_database_records():
    client.post("/api/inventory", json=sample_item())
    response = client.get("/api/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["item_count"] == 1
    assert data["inventory_value"] == 500
    assert data["data_source"] == "database"
