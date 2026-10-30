"""Initial HarvestGuard schema; reviewed bootstrap migration."""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sku", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("unit_cost", sa.Float(), nullable=False),
        sa.Column("reorder_level", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_items_id", "inventory_items", ["id"])
    op.create_index("ix_inventory_items_sku", "inventory_items", ["sku"], unique=True)
    op.create_index("ix_inventory_items_name", "inventory_items", ["name"])
    op.create_index("ix_inventory_items_category", "inventory_items", ["category"])
    op.create_table(
        "waste_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("item_name", sa.String(length=120), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("unit_cost", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_waste_records_id", "waste_records", ["id"])
    op.create_index("ix_waste_records_recorded_at", "waste_records", ["recorded_at"])

def downgrade():
    op.drop_index("ix_waste_records_recorded_at", table_name="waste_records")
    op.drop_index("ix_waste_records_id", table_name="waste_records")
    op.drop_table("waste_records")
    op.drop_index("ix_inventory_items_category", table_name="inventory_items")
    op.drop_index("ix_inventory_items_name", table_name="inventory_items")
    op.drop_index("ix_inventory_items_sku", table_name="inventory_items")
    op.drop_index("ix_inventory_items_id", table_name="inventory_items")
    op.drop_table("inventory_items")
