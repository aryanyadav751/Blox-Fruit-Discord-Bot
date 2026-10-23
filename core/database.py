"""
Blox Fruit Services - SQLite Persistence Engine.
Stores orders, payment verification records, audit history, and configuration.
Features:
- Fixed-point Decimal precision support
- Order state machine transition validation
- Strict payment validation (prevents over-crediting, invalid stages, duplicate payments)
- Transactional integrity and audit logging
"""

import sqlite3
import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from config import Config
from core.calculator import to_decimal, TWOPLACES


# State Machine: Valid Status Transitions
ALLOWED_TRANSITIONS = {
    "PENDING_ACCEPTANCE": ["AWAITING_UPFRONT_PAYMENT", "CANCELLED", "REJECTED"],
    "AWAITING_UPFRONT_PAYMENT": ["UPFRONT_VERIFIED", "CANCELLED", "REJECTED"],
    "UPFRONT_VERIFIED": ["IN_PROGRESS", "CANCELLED"],
    "IN_PROGRESS": ["COMPLETED_AWAITING_BALANCE", "PAID_AND_CLOSED", "CANCELLED"],
    "COMPLETED_AWAITING_BALANCE": ["PAID_AND_CLOSED", "CANCELLED"],
    "PAID_AND_CLOSED": [],
    "CANCELLED": [],
    "REJECTED": [],
}


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self._lock = asyncio.Lock()
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_db(self) -> None:
        """Initializes tables and default sequences if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                customer_tag TEXT NOT NULL,
                roblox_username TEXT NOT NULL,
                category_id TEXT NOT NULL,
                service_id TEXT NOT NULL,
                service_name TEXT NOT NULL,
                total_price_m REAL NOT NULL,
                payment_plan TEXT NOT NULL,
                initial_payment_required_m REAL NOT NULL,
                balance_remaining_m REAL NOT NULL,
                initial_payment_paid_m REAL DEFAULT 0.0,
                balance_paid_m REAL DEFAULT 0.0,
                payment_methods TEXT NOT NULL,
                proposed_items TEXT NOT NULL,
                customer_availability TEXT NOT NULL,
                status TEXT NOT NULL,
                staff_thread_id INTEGER,
                staff_message_id INTEGER,
                assigned_staff_id INTEGER,
                cancellation_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                payment_stage TEXT NOT NULL,
                items_received TEXT NOT NULL,
                credited_value_m REAL NOT NULL,
                verified_by_staff_id INTEGER NOT NULL,
                verified_by_staff_tag TEXT NOT NULL,
                notes TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(order_id)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_id INTEGER NOT NULL,
                actor_tag TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(order_id)
            );

            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)
            conn.commit()

    async def get_next_order_id(self) -> str:
        """Atomically generates sequential order ID like BFS-1001."""
        async with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT value FROM bot_config WHERE key = 'last_order_seq';")
                row = cur.fetchone()
                if row:
                    next_seq = int(row["value"]) + 1
                    cur.execute(
                        "UPDATE bot_config SET value = ? WHERE key = 'last_order_seq';",
                        (str(next_seq),),
                    )
                else:
                    next_seq = 1001
                    cur.execute(
                        "INSERT INTO bot_config (key, value) VALUES ('last_order_seq', ?);",
                        (str(next_seq),),
                    )
                conn.commit()
                return f"BFS-{next_seq}"

    def get_next_order_id_sync(self) -> str:
        """Synchronous variant for testing."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM bot_config WHERE key = 'last_order_seq';")
            row = cur.fetchone()
            if row:
                next_seq = int(row["value"]) + 1
                cur.execute(
                    "UPDATE bot_config SET value = ? WHERE key = 'last_order_seq';",
                    (str(next_seq),),
                )
            else:
                next_seq = 1001
                cur.execute(
                    "INSERT INTO bot_config (key, value) VALUES ('last_order_seq', ?);",
                    (str(next_seq),),
                )
            conn.commit()
            return f"BFS-{next_seq}"

    async def create_order(
        self,
        order_id: str,
        customer_id: int,
        customer_tag: str,
        roblox_username: str,
        category_id: str,
        service_id: str,
        service_name: str,
        total_price_m: float | Decimal,
        payment_plan: str,
        initial_payment_required_m: float | Decimal,
        balance_remaining_m: float | Decimal,
        payment_methods: str,
        proposed_items: str,
        customer_availability: str,
        status: str = "PENDING_ACCEPTANCE",
    ) -> Dict[str, Any]:
        """Inserts a new order and initial audit entry with exact Decimal rounding."""
        tot = float(to_decimal(total_price_m))
        init_req = float(to_decimal(initial_payment_required_m))
        bal_req = float(to_decimal(balance_remaining_m))

        async with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                now = datetime.utcnow().isoformat()
                cur.execute(
                    """
                    INSERT INTO orders (
                        order_id, customer_id, customer_tag, roblox_username,
                        category_id, service_id, service_name, total_price_m,
                        payment_plan, initial_payment_required_m, balance_remaining_m,
                        payment_methods, proposed_items, customer_availability,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        order_id,
                        customer_id,
                        customer_tag,
                        roblox_username,
                        category_id,
                        service_id,
                        service_name,
                        tot,
                        payment_plan,
                        init_req,
                        bal_req,
                        payment_methods,
                        proposed_items,
                        customer_availability,
                        status,
                        now,
                        now,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO audit_logs (order_id, action, actor_id, actor_tag, details)
                    VALUES (?, 'ORDER_CREATED', ?, ?, ?);
                    """,
                    (
                        order_id,
                        customer_id,
                        customer_tag,
                        f"Order created with plan {payment_plan} for {service_name} ({tot}M)",
                    ),
                )
                conn.commit()

        return await self.get_order(order_id)

    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM orders WHERE order_id = ?;", (order_id,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)

    def get_order_sync(self, order_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM orders WHERE order_id = ?;", (order_id,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)

    async def set_thread_and_message(
        self, order_id: str, thread_id: int, message_id: int
    ) -> None:
        async with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE orders
                    SET staff_thread_id = ?, staff_message_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = ?;
                    """,
                    (thread_id, message_id, order_id),
                )
                conn.commit()

    async def update_order_status(
        self,
        order_id: str,
        new_status: str,
        actor_id: int,
        actor_tag: str,
        details: str = "",
        assigned_staff_id: Optional[int] = None,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Validates transition against ALLOWED_TRANSITIONS state machine before updating.
        """
        async with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM orders WHERE order_id = ?;", (order_id,))
                order = cur.fetchone()
                if not order:
                    raise ValueError(f"Order {order_id} not found.")

                current_status = order["status"]
                # State machine validation
                if not force and current_status != new_status:
                    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
                    if new_status not in allowed:
                        raise ValueError(
                            f"Invalid status transition from {current_status} to {new_status}. Allowed: {allowed}"
                        )

                now = datetime.utcnow().isoformat()
                if assigned_staff_id is not None:
                    cur.execute(
                        """
                        UPDATE orders
                        SET status = ?, assigned_staff_id = ?, updated_at = ?
                        WHERE order_id = ?;
                        """,
                        (new_status, assigned_staff_id, now, order_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE orders
                        SET status = ?, updated_at = ?
                        WHERE order_id = ?;
                        """,
                        (new_status, now, order_id),
                    )

                cur.execute(
                    """
                    INSERT INTO audit_logs (order_id, action, actor_id, actor_tag, details)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (order_id, f"STATUS_{new_status}", actor_id, actor_tag, details),
                )
                conn.commit()

        return await self.get_order(order_id)

    async def record_payment(
        self,
        order_id: str,
        payment_stage: str,  # 'UPFRONT' or 'BALANCE'
        items_received: str,
        credited_value_m: float | Decimal,
        staff_id: int,
        staff_tag: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Validates payment stage, prevents over-crediting, duplicate payments,
        and advances order status appropriately.
        """
        credit_dec = to_decimal(credited_value_m)
        if credit_dec <= Decimal("0"):
            raise ValueError("Credited trade value must be greater than 0M.")

        clean_stage = payment_stage.strip().upper()
        if clean_stage not in ["UPFRONT", "BALANCE"]:
            raise ValueError(f"Invalid payment stage '{payment_stage}'. Expected 'UPFRONT' or 'BALANCE'.")

        async with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM orders WHERE order_id = ?;", (order_id,))
                order = cur.fetchone()
                if not order:
                    raise ValueError(f"Order {order_id} not found.")

                status = order["status"]
                if status in ["CANCELLED", "REJECTED", "PAID_AND_CLOSED"]:
                    raise ValueError(f"Cannot record payment for an order with status {status}.")

                plan = order["payment_plan"]
                initial_req = to_decimal(order["initial_payment_required_m"])
                initial_paid = to_decimal(order["initial_payment_paid_m"])
                balance_req = to_decimal(order["balance_remaining_m"])
                balance_paid = to_decimal(order["balance_paid_m"])

                # Check for duplicate payment submission within 10 seconds
                cur.execute(
                    """
                    SELECT payment_id FROM payments
                    WHERE order_id = ? AND payment_stage = ? AND credited_value_m = ?
                    AND datetime(recorded_at) >= datetime('now', '-10 seconds');
                    """,
                    (order_id, clean_stage, float(credit_dec)),
                )
                if cur.fetchone():
                    raise ValueError("Duplicate payment detected within 10 seconds. Action blocked.")

                if clean_stage == "UPFRONT":
                    if initial_paid >= initial_req:
                        raise ValueError(f"Upfront payment is already fully satisfied ({initial_paid}M / {initial_req}M).")

                    new_initial_paid = initial_paid + credit_dec
                    # Status advances to UPFRONT_VERIFIED if satisfied
                    new_status = "UPFRONT_VERIFIED"
                    cur.execute(
                        """
                        UPDATE orders
                        SET initial_payment_paid_m = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE order_id = ?;
                        """,
                        (float(new_initial_paid), new_status, order_id),
                    )

                else:  # BALANCE
                    if plan == "FULL_UPFRONT":
                        raise ValueError("Cannot record remaining balance for a One-Time Full Payment plan (remaining balance is 0M).")

                    if initial_paid < initial_req:
                        raise ValueError("Cannot record remaining balance before initial upfront deposit is paid.")

                    if balance_paid >= balance_req:
                        raise ValueError(f"Remaining balance is already fully satisfied ({balance_paid}M / {balance_req}M).")

                    new_balance_paid = balance_paid + credit_dec
                    new_status = "PAID_AND_CLOSED"
                    cur.execute(
                        """
                        UPDATE orders
                        SET balance_paid_m = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE order_id = ?;
                        """,
                        (float(new_balance_paid), new_status, order_id),
                    )

                # Insert payment log
                cur.execute(
                    """
                    INSERT INTO payments (
                        order_id, payment_stage, items_received, credited_value_m,
                        verified_by_staff_id, verified_by_staff_tag, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        order_id,
                        clean_stage,
                        items_received.strip(),
                        float(credit_dec),
                        staff_id,
                        staff_tag,
                        notes.strip() if notes else "",
                    ),
                )

                # Insert audit log
                cur.execute(
                    """
                    INSERT INTO audit_logs (order_id, action, actor_id, actor_tag, details)
                    VALUES (?, 'PAYMENT_RECORDED', ?, ?, ?);
                    """,
                    (
                        order_id,
                        staff_id,
                        staff_tag,
                        f"Stage {clean_stage}: credited {credit_dec}M for items: {items_received}",
                    ),
                )
                conn.commit()

        return await self.get_order(order_id)

    async def cancel_order(
        self, order_id: str, actor_id: int, actor_tag: str, reason: str, is_rejection: bool = False
    ) -> Dict[str, Any]:
        status = "REJECTED" if is_rejection else "CANCELLED"
        async with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT status FROM orders WHERE order_id = ?;", (order_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Order {order_id} not found.")

                if row["status"] in ["PAID_AND_CLOSED", "CANCELLED", "REJECTED"]:
                    raise ValueError(f"Order is already in a terminal state: {row['status']}.")

                now = datetime.utcnow().isoformat()
                cur.execute(
                    """
                    UPDATE orders
                    SET status = ?, cancellation_reason = ?, updated_at = ?
                    WHERE order_id = ?;
                    """,
                    (status, reason.strip(), now, order_id),
                )
                cur.execute(
                    """
                    INSERT INTO audit_logs (order_id, action, actor_id, actor_tag, details)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (order_id, f"ORDER_{status}", actor_id, actor_tag, f"Reason: {reason.strip()}"),
                )
                conn.commit()

        return await self.get_order(order_id)

    async def get_orders_by_customer(self, customer_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM orders
                WHERE customer_id = ?
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (customer_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]

    async def get_recent_orders(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM orders
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    async def get_order_payments(self, order_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM payments
                WHERE order_id = ?
                ORDER BY recorded_at ASC;
                """,
                (order_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    async def get_order_audits(self, order_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM audit_logs
                WHERE order_id = ?
                ORDER BY created_at ASC;
                """,
                (order_id,),
            )
            return [dict(row) for row in cur.fetchall()]


# Global database instance
db = Database()
