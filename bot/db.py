from contextlib import asynccontextmanager
from datetime import date, timedelta

import aiosqlite

from bot.config import DATABASE_PATH, TURSO_URL, TURSO_AUTH_TOKEN
from bot.calendar_utils import calc_deferral_end

_CREATE_SUPPLIERS = """
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    deferral_days INTEGER NOT NULL
)
"""

_CREATE_DELIVERIES = """
CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    delivery_date TEXT NOT NULL,
    amount REAL,
    paid INTEGER DEFAULT 0,
    manual_end_date TEXT DEFAULT NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
)
"""

_DELIVERY_COLS = (
    "d.id, d.supplier_id, d.delivery_date, d.amount, d.paid, "
    "d.manual_end_date, s.name AS supplier_name, s.deferral_days"
)


class _LocalBackend:
    def __init__(self, path):
        self.path = path

    @asynccontextmanager
    async def _conn(self):
        db = await aiosqlite.connect(self.path)
        await db.execute("PRAGMA foreign_keys = ON")
        try:
            yield db
        finally:
            await db.close()

    async def init(self):
        async with self._conn() as db:
            await db.execute(_CREATE_SUPPLIERS)
            await db.execute(_CREATE_DELIVERIES)
            await db.commit()

    async def fetch_all(self, sql, params=None):
        async with self._conn() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params or [])
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def fetch_one(self, sql, params=None):
        rows = await self.fetch_all(sql, params)
        return rows[0] if rows else None

    async def execute(self, sql, params=None):
        async with self._conn() as db:
            await db.execute(sql, params or [])
            await db.commit()

    async def execute_insert(self, sql, params=None):
        async with self._conn() as db:
            cursor = await db.execute(sql, params or [])
            await db.commit()
            return cursor.lastrowid

    async def execute_bool(self, sql, params=None):
        try:
            await self.execute(sql, params)
            return True
        except Exception:
            return False


class _TursoBackend:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        self._client = None

    async def _get_client(self):
        if self._client is None:
            from libsql_client import create_client
            self._client = create_client(url=self.url, auth_token=self.token)
        return self._client

    @staticmethod
    def _rows(results):
        if results is None:
            return []
        return [row.asdict() for row in results.rows]

    async def init(self):
        client = await self._get_client()
        await client.execute(_CREATE_SUPPLIERS)
        await client.execute(_CREATE_DELIVERIES)

    async def fetch_all(self, sql, params=None):
        client = await self._get_client()
        return self._rows(await client.execute(sql, params))

    async def fetch_one(self, sql, params=None):
        rows = await self.fetch_all(sql, params)
        return rows[0] if rows else None

    async def execute(self, sql, params=None):
        client = await self._get_client()
        await client.execute(sql, params)

    async def execute_insert(self, sql, params=None):
        client = await self._get_client()
        res = await client.execute(sql, params)
        return res.last_insert_rowid if res is not None else None

    async def execute_bool(self, sql, params=None):
        try:
            await self.execute(sql, params)
            return True
        except Exception:
            return False


_backend = None


def _get_backend():
    global _backend
    if _backend is None:
        if TURSO_URL and TURSO_AUTH_TOKEN:
            _backend = _TursoBackend(TURSO_URL, TURSO_AUTH_TOKEN)
        else:
            _backend = _LocalBackend(DATABASE_PATH)
    return _backend


async def init():
    await _get_backend().init()


async def add_supplier(name: str, deferral_days: int):
    return await _get_backend().execute_bool(
        "INSERT INTO suppliers (name, deferral_days) VALUES (?, ?)",
        [name, deferral_days],
    )


async def get_all_suppliers():
    return await _get_backend().fetch_all(
        "SELECT id, name, deferral_days FROM suppliers ORDER BY name"
    )


async def get_supplier(supplier_id: int):
    return await _get_backend().fetch_one(
        "SELECT id, name, deferral_days FROM suppliers WHERE id = ?",
        [supplier_id],
    )


async def edit_supplier(supplier_id: int, name: str = None, deferral_days: int = None):
    backend = _get_backend()
    if name is not None:
        await backend.execute("UPDATE suppliers SET name = ? WHERE id = ?", [name, supplier_id])
    if deferral_days is not None:
        await backend.execute(
            "UPDATE suppliers SET deferral_days = ? WHERE id = ?", [deferral_days, supplier_id]
        )


async def delete_supplier(supplier_id: int):
    backend = _get_backend()
    await backend.execute("DELETE FROM deliveries WHERE supplier_id = ?", [supplier_id])
    await backend.execute("DELETE FROM suppliers WHERE id = ?", [supplier_id])


async def add_delivery(supplier_id: int, delivery_date: str, amount: float):
    backend = _get_backend()
    exists = await backend.fetch_one("SELECT id FROM suppliers WHERE id = ?", [supplier_id])
    if exists is None:
        raise ValueError("supplier not found")
    return await backend.execute_insert(
        "INSERT INTO deliveries (supplier_id, delivery_date, amount) VALUES (?, ?, ?)",
        [supplier_id, delivery_date, amount],
    )


async def get_deliveries(supplier_id: int = None, date_from: str = None, date_to: str = None, unpaid_only: bool = False):
    query = f"""
        SELECT {_DELIVERY_COLS}
        FROM deliveries d
        JOIN suppliers s ON d.supplier_id = s.id
        WHERE 1=1
    """
    params = []
    if supplier_id is not None:
        query += " AND d.supplier_id = ?"
        params.append(supplier_id)
    if date_from:
        query += " AND d.delivery_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND d.delivery_date <= ?"
        params.append(date_to)
    if unpaid_only:
        query += " AND d.paid = 0"
    query += " ORDER BY d.delivery_date DESC"
    return await _get_backend().fetch_all(query, params)


async def get_delivery(delivery_id: int):
    return await _get_backend().fetch_one(
        f"SELECT {_DELIVERY_COLS} FROM deliveries d JOIN suppliers s ON d.supplier_id = s.id WHERE d.id = ?",
        [delivery_id],
    )


async def mark_paid(delivery_id: int):
    await _get_backend().execute("UPDATE deliveries SET paid = 1 WHERE id = ?", [delivery_id])


async def set_manual_end_date(delivery_id: int, new_date: str):
    await _get_backend().execute(
        "UPDATE deliveries SET manual_end_date = ? WHERE id = ?", [new_date, delivery_id]
    )


async def clear_manual_end_date(delivery_id: int):
    await _get_backend().execute("UPDATE deliveries SET manual_end_date = NULL WHERE id = ?", [delivery_id])


async def edit_delivery(delivery_id: int, delivery_date: str = None, amount: float = None):
    backend = _get_backend()
    if delivery_date is not None:
        await backend.execute(
            "UPDATE deliveries SET delivery_date = ? WHERE id = ?", [delivery_date, delivery_id]
        )
    if amount is not None:
        await backend.execute("UPDATE deliveries SET amount = ? WHERE id = ?", [amount, delivery_id])


async def delete_delivery(delivery_id: int):
    await _get_backend().execute("DELETE FROM deliveries WHERE id = ?", [delivery_id])


async def get_deliveries_for_date(target_date: str):
    all_unpaid = await get_unpaid_with_deferral_end()
    return [d for d in all_unpaid if d["deferral_end"] == target_date]


async def get_unpaid_with_deferral_end():
    rows = await _get_backend().fetch_all(
        f"SELECT {_DELIVERY_COLS} FROM deliveries d JOIN suppliers s ON d.supplier_id = s.id WHERE d.paid = 0"
    )
    return _with_deferral_end(rows)


async def get_overdue(target_date: str):
    all_unpaid = await get_unpaid_with_deferral_end()
    return [d for d in all_unpaid if d["deferral_end"] < target_date]


async def get_upcoming(target_date: str, days: int):
    all_unpaid = await get_unpaid_with_deferral_end()
    limit = (date.fromisoformat(target_date) + timedelta(days=days)).strftime("%Y-%m-%d")
    return [
        d for d in all_unpaid
        if target_date < d["deferral_end"] <= limit
    ]


async def get_all_deliveries_with_end():
    rows = await _get_backend().fetch_all(
        f"SELECT {_DELIVERY_COLS} FROM deliveries d JOIN suppliers s ON d.supplier_id = s.id ORDER BY d.delivery_date DESC"
    )
    return _with_deferral_end(rows)


def _with_deferral_end(rows):
    result = []
    for row in rows:
        deferral_end = calc_deferral_end(
            row["delivery_date"], row["deferral_days"], row["manual_end_date"]
        )
        item = dict(row)
        item["deferral_end"] = deferral_end
        result.append(item)
    return result
