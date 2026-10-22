"""
Blox Fruit Services - SQLite Persistence Engine.
Stores orders, payment verification records, audit history, and configuration.
Uses standard sqlite3 with thread-safe connection pooling for maximum reliability across hosts.
"""

import sqlite3
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from config import Config


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
        """Synchronous variant for unit testing."""
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
        total_price_m: float,
        payment_plan: str,
        initial_payment_required_m: float,
        balance_remaining_m: float,
        payment_methods: str,
        proposed_items: str,
        customer_availability: str,
        status: str = "PENDING_ACCEPTANCE",
    ) -> Dict[str, Any]:
        """Inserts a new order and initial audit entry."""
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
                        total_price_m,
                        payment_plan,
                        initial_payment_required_m,
                        balance_remaining_m,
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
                        f"Order created with plan {payment_plan} for {service_name} ({total_price_m}M)",
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
    ) -> Optional[Dict[str, Any]]:
        async with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
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
        credited_value_m: float,
        staff_id: int,
        staff_tag: str,
        notes: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Records verified payment items and credited M value.
        Updates order totals and advances status.
        """
        async with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM orders WHERE order_id = ?;", (order_id,))
                order = cur.fetchone()
                if not order:
                    return None

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
                        payment_stage,
                        items_received,
                        credited_value_m,
                        staff_id,
                        staff_tag,
                        notes,
                    ),
                )

                now = datetime.utcnow().isoformat()
                if payment_stage == "UPFRONT":
                    new_initial_paid = round(float(order["initial_payment_paid_m"]) + credited_value_m, 2)
                    # If full upfront plan, and paid >= total, mark FULLY_PAID
                    if order["payment_plan"] == "FULL_UPFRONT":
                        new_status = "UPFRONT_VERIFIED"
                    else:
                        new_status = "UPFRONT_VERIFIED"

                    cur.execute(
                        """
                        UPDATE orders
                        SET initial_payment_paid_m = ?, status = ?, updated_at = ?
                        WHERE order_id = ?;
                        """,
                        (new_initial_paid, new_status, now, order_id),
                    )
                else:  # BALANCE
                    new_balance_paid = round(float(order["balance_paid_m"]) + credited_value_m, 2)
                    new_status = "PAID_AND_CLOSED"
                    cur.execute(
                        """
                        UPDATE orders
                        SET balance_paid_m = ?, status = ?, updated_at = ?
                        WHERE order_id = ?;
                        """,
                        (new_balance_paid, new_status, now, order_id),
                    )

                cur.execute(
                    """
                    INSERT INTO audit_logs (order_id, action, actor_id, actor_tag, details)
                    VALUES (?, 'PAYMENT_RECORDED', ?, ?, ?);
                    """,
                    (
                        order_id,
                        staff_id,
                        staff_tag,
                        f"Recorded {credited_value_m}M for stage {payment_stage}. Items: {items_received}",
                    ),
                )
                conn.commit()

        return await self.get_order(order_id)

    async def cancel_order(
        self, order_id: str, actor_id: int, actor_tag: str, reason: str, is_rejection: bool = False
    ) -> Optional[Dict[str, Any]]:
        status = "REJECTED" if is_rejection else "CANCELLED"
        async with self._lock:
            with self._get_connection() as conn:
                cur = conn.cursor()
                now = datetime.utcnow().isoformat()
                cur.execute(
                    """
                    UPDATE orders
                    SET status = ?, cancellation_reason = ?, updated_at = ?
                    WHERE order_id = ?;
                    """,
                    (status, reason, now, order_id),
                )
                cur.execute(
                    """
                    INSERT INTO audit_logs (order_id, action, actor_id, actor_tag, details)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (order_id, f"ORDER_{status}", actor_id, actor_tag, f"Reason: {reason}"),
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
