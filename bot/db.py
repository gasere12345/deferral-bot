import aiosqlite
from datetime import date
from bot.calendar_utils import calc_deferral_end
from bot.config import DATABASE_PATH


async def init():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                deferral_days INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                delivery_date TEXT NOT NULL,
                amount REAL,
                paid INTEGER DEFAULT 0,
                manual_end_date TEXT DEFAULT NULL,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            )
        """)
        await db.commit()


async def add_supplier(name: str, deferral_days: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO suppliers (name, deferral_days) VALUES (?, ?)",
                (name, deferral_days),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_all_suppliers():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, name, deferral_days FROM suppliers ORDER BY name")
        return await cursor.fetchall()


async def get_supplier(supplier_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, deferral_days FROM suppliers WHERE id = ?",
            (supplier_id,),
        )
        return await cursor.fetchone()


async def edit_supplier(supplier_id: int, name: str = None, deferral_days: int = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if name is not None:
            await db.execute("UPDATE suppliers SET name = ? WHERE id = ?", (name, supplier_id))
        if deferral_days is not None:
            await db.execute("UPDATE suppliers SET deferral_days = ? WHERE id = ?", (deferral_days, supplier_id))
        await db.commit()


async def delete_supplier(supplier_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM deliveries WHERE supplier_id = ?", (supplier_id,))
        await db.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        await db.commit()


async def add_delivery(supplier_id: int, delivery_date: str, amount: float):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO deliveries (supplier_id, delivery_date, amount) VALUES (?, ?, ?)",
            (supplier_id, delivery_date, amount),
        )
        await db.commit()
        return cursor.lastrowid


async def get_deliveries(supplier_id: int = None, date_from: str = None, date_to: str = None, unpaid_only: bool = False):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT d.id, d.supplier_id, d.delivery_date, d.amount, d.paid,
                   d.manual_end_date, s.name AS supplier_name, s.deferral_days
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
        cursor = await db.execute(query, params)
        return await cursor.fetchall()


async def get_delivery(delivery_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT d.id, d.supplier_id, d.delivery_date, d.amount, d.paid,
                      d.manual_end_date, s.name AS supplier_name, s.deferral_days
               FROM deliveries d
               JOIN suppliers s ON d.supplier_id = s.id
               WHERE d.id = ?""",
            (delivery_id,),
        )
        return await cursor.fetchone()


async def mark_paid(delivery_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE deliveries SET paid = 1 WHERE id = ?", (delivery_id,))
        await db.commit()


async def set_manual_end_date(delivery_id: int, new_date: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE deliveries SET manual_end_date = ? WHERE id = ?", (new_date, delivery_id))
        await db.commit()


async def clear_manual_end_date(delivery_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE deliveries SET manual_end_date = NULL WHERE id = ?", (delivery_id,))
        await db.commit()


async def edit_delivery(delivery_id: int, delivery_date: str = None, amount: float = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if delivery_date is not None:
            await db.execute("UPDATE deliveries SET delivery_date = ? WHERE id = ?", (delivery_date, delivery_id))
        if amount is not None:
            await db.execute("UPDATE deliveries SET amount = ? WHERE id = ?", (amount, delivery_id))
        await db.commit()


async def delete_delivery(delivery_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM deliveries WHERE id = ?", (delivery_id,))
        await db.commit()


async def get_deliveries_for_date(target_date: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT d.id, d.supplier_id, d.delivery_date, d.amount, d.paid,
                      d.manual_end_date, s.name AS supplier_name, s.deferral_days
               FROM deliveries d
               JOIN suppliers s ON d.supplier_id = s.id
               WHERE d.paid = 0""",
        )
        rows = await cursor.fetchall()
    result = []
    for row in rows:
        deferral_end = calc_deferral_end(
            row["delivery_date"], row["deferral_days"], row["manual_end_date"]
        )
        if deferral_end == target_date:
            result.append(dict(row))
    return result
