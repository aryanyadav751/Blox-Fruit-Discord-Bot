"""
Tests for core/database.py:
- SQLite persistence across restarts
- Sequential Order ID generation (BFS-1001, BFS-1002)
- Order creation with 50/50 and One-Time Full plans
- Upfront and balance payment recording
- Audit log entry verification
- Cancellation and rejection reasons
"""

import pytest
from pathlib import Path
from core.database import Database


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    db_file = tmp_path / "test_blox_fruits.db"
    return Database(db_path=db_file)


def test_order_id_generation(temp_db: Database):
    id1 = temp_db.get_next_order_id_sync()
    id2 = temp_db.get_next_order_id_sync()
    id3 = temp_db.get_next_order_id_sync()

    assert id1 == "BFS-1001"
    assert id2 == "BFS-1002"
    assert id3 == "BFS-1003"


@pytest.mark.asyncio
async def test_order_creation_50_50(temp_db: Database):
    order_id = await temp_db.get_next_order_id()
    order = await temp_db.create_order(
        order_id=order_id,
        customer_id=123456789,
        customer_tag="Player#0001",
        roblox_username="RobloxHero",
        category_id="bosses",
        service_id="boss_dough_king",
        service_name="Dough King",
        total_price_m=75.0,
        payment_plan="SPLIT_50_50",
        initial_payment_required_m=37.5,
        balance_remaining_m=37.5,
        payment_methods='["FRUITS", "GAMEPASSES"]',
        proposed_items="Mammoth + 2x Mastery (~40M)",
        customer_availability="EST Evenings",
        status="PENDING_ACCEPTANCE",
    )

    assert order is not None
    assert order["order_id"] == "BFS-1001"
    assert order["total_price_m"] == 75.0
    assert order["payment_plan"] == "SPLIT_50_50"
    assert order["initial_payment_required_m"] == 37.5
    assert order["balance_remaining_m"] == 37.5
    assert order["initial_payment_paid_m"] == 0.0
    assert order["balance_paid_m"] == 0.0
    assert order["status"] == "PENDING_ACCEPTANCE"

    # Verify audit log was created
    audits = await temp_db.get_order_audits(order_id)
    assert len(audits) >= 1
    assert audits[0]["action"] == "ORDER_CREATED"


@pytest.mark.asyncio
async def test_payment_recording_upfront_and_balance(temp_db: Database):
    order_id = await temp_db.get_next_order_id()
    await temp_db.create_order(
        order_id=order_id,
        customer_id=123456789,
        customer_tag="Player#0001",
        roblox_username="RobloxHero",
        category_id="swords",
        service_id="sword_ttk",
        service_name="True Triple Katana (TTK)",
        total_price_m=150.0,
        payment_plan="SPLIT_50_50",
        initial_payment_required_m=75.0,
        balance_remaining_m=75.0,
        payment_methods='["FRUITS"]',
        proposed_items="Dragon + Dough (~110M)",
        customer_availability="UTC+0",
    )

    # 1. Staff records upfront payment
    updated = await temp_db.record_payment(
        order_id=order_id,
        payment_stage="UPFRONT",
        items_received="1x Physical Dragon, 1x Dough",
        credited_value_m=75.0,
        staff_id=987654321,
        staff_tag="StaffMaster#9999",
        notes="Trade completed in 2nd sea cafe",
    )

    assert updated["initial_payment_paid_m"] == 75.0
    assert updated["status"] == "UPFRONT_VERIFIED"

    # 2. Staff records balance payment
    updated2 = await temp_db.record_payment(
        order_id=order_id,
        payment_stage="BALANCE",
        items_received="1x Leopard, 1x Venom",
        credited_value_m=75.0,
        staff_id=987654321,
        staff_tag="StaffMaster#9999",
        notes="Final balance received",
    )

    assert updated2["balance_paid_m"] == 75.0
    assert updated2["status"] == "PAID_AND_CLOSED"

    # Check payments table
    payments = await temp_db.get_order_payments(order_id)
    assert len(payments) == 2
    assert payments[0]["payment_stage"] == "UPFRONT"
    assert payments[0]["credited_value_m"] == 75.0
    assert payments[1]["payment_stage"] == "BALANCE"
    assert payments[1]["credited_value_m"] == 75.0


@pytest.mark.asyncio
async def test_order_cancellation(temp_db: Database):
    order_id = await temp_db.get_next_order_id()
    await temp_db.create_order(
        order_id=order_id,
        customer_id=123,
        customer_tag="Test#1",
        roblox_username="TestRBLX",
        category_id="trials",
        service_id="trials_1",
        service_name="1 Trial",
        total_price_m=45.0,
        payment_plan="FULL_UPFRONT",
        initial_payment_required_m=45.0,
        balance_remaining_m=0.0,
        payment_methods='["FRUITS"]',
        proposed_items="Dough + adds",
        customer_availability="Anytime",
    )

    cancelled = await temp_db.cancel_order(
        order_id=order_id,
        actor_id=999,
        actor_tag="StaffAdmin#1111",
        reason="Customer did not meet trial prerequisites (missing V3 race).",
    )

    assert cancelled["status"] == "REJECTED" or cancelled["status"] == "CANCELLED"
    assert "missing V3 race" in cancelled["cancellation_reason"]


def test_persistence_across_restart(tmp_path: Path):
    """Ensure data is loaded after recreating the Database instance."""
    db_file = tmp_path / "persistence_test.db"
    db1 = Database(db_path=db_file)
    id1 = db1.get_next_order_id_sync()
    assert id1 == "BFS-1001"

    # Create new instance pointing to same file
    db2 = Database(db_path=db_file)
    id2 = db2.get_next_order_id_sync()
    assert id2 == "BFS-1002"
