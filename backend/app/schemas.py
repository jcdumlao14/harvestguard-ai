from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, computed_field

class ItemCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=30)
    expiry_date: date | None = None
    unit_cost: float = Field(ge=0)
    reorder_level: float = Field(default=0, ge=0)

class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=60)
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    expiry_date: date | None = None
    unit_cost: float | None = Field(default=None, ge=0)
    reorder_level: float | None = Field(default=None, ge=0)

class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category: str
    quantity: float
    unit: str
    expiry_date: date | None
    unit_cost: float
    reorder_level: float
    created_at: datetime

    @computed_field
    @property
    def stock_value(self) -> float:
        return round(self.quantity * self.unit_cost, 2)

    @computed_field
    @property
    def status(self) -> str:
        if self.quantity <= self.reorder_level:
            return "low_stock"
        if self.expiry_date is not None:
            days = (self.expiry_date - date.today()).days
            if days < 0:
                return "expired"
            if days <= 3:
                return "expiring"
        return "healthy"

class WasteCreate(BaseModel):
    item_id: int | None = None
    item_name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=30)
    unit_cost: float = Field(ge=0)
    reason: str = Field(min_length=1, max_length=120)

class WasteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int | None
    item_name: str
    quantity: float
    unit: str
    unit_cost: float
    reason: str
    recorded_at: datetime

    @computed_field
    @property
    def total_cost(self) -> float:
        return round(self.quantity * self.unit_cost, 2)
