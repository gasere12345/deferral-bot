import pytest


@pytest.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    import bot.db as db_module
    import bot.config as cfg_module

    cfg_module.DATABASE_PATH = db_path
    db_module.DATABASE_PATH = db_path
    db_module._backend = None

    await db_module.init()


class TestSuppliers:
    async def test_add_supplier(self, db):
        from bot.db import add_supplier, get_all_suppliers

        ok = await add_supplier("TestSupplier", 30)
        assert ok

        suppliers = await get_all_suppliers()
        assert len(suppliers) == 1
        assert suppliers[0]["name"] == "TestSupplier"
        assert suppliers[0]["deferral_days"] == 30

    async def test_add_duplicate_supplier_returns_false(self, db):
        from bot.db import add_supplier

        await add_supplier("Dup", 30)
        ok = await add_supplier("Dup", 30)
        assert not ok

    async def test_get_all_suppliers_empty(self, db):
        from bot.db import get_all_suppliers

        suppliers = await get_all_suppliers()
        assert suppliers == []

    async def test_get_all_suppliers_multiple(self, db):
        from bot.db import add_supplier, get_all_suppliers

        await add_supplier("B", 30)
        await add_supplier("A", 15)
        await add_supplier("C", 60)

        suppliers = await get_all_suppliers()
        names = [s["name"] for s in suppliers]
        assert names == ["A", "B", "C"]

    async def test_get_supplier_by_id(self, db):
        from bot.db import add_supplier, get_supplier

        await add_supplier("Target", 45)
        s = await get_supplier(1)
        assert s is not None
        assert s["name"] == "Target"
        assert s["deferral_days"] == 45

    async def test_get_supplier_not_found(self, db):
        from bot.db import get_supplier

        s = await get_supplier(999)
        assert s is None

    async def test_edit_supplier_name(self, db):
        from bot.db import add_supplier, edit_supplier, get_supplier

        await add_supplier("OldName", 30)
        await edit_supplier(1, name="NewName")
        s = await get_supplier(1)
        assert s["name"] == "NewName"
        assert s["deferral_days"] == 30

    async def test_edit_supplier_deferral_days(self, db):
        from bot.db import add_supplier, edit_supplier, get_supplier

        await add_supplier("Sup", 30)
        await edit_supplier(1, deferral_days=60)
        s = await get_supplier(1)
        assert s["deferral_days"] == 60

    async def test_delete_supplier(self, db):
        from bot.db import add_supplier, delete_supplier, get_all_suppliers

        await add_supplier("ToDelete", 30)
        await delete_supplier(1)
        suppliers = await get_all_suppliers()
        assert len(suppliers) == 0

    async def test_delete_supplier_removes_deliveries(self, db):
        from bot.db import add_supplier, add_delivery, delete_supplier, get_deliveries

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 1000.0)
        await delete_supplier(1)
        deliveries = await get_deliveries(supplier_id=1)
        assert len(deliveries) == 0


class TestDeliveries:
    async def test_add_delivery(self, db):
        from bot.db import add_supplier, add_delivery, get_delivery

        await add_supplier("Sup", 30)
        delivery_id = await add_delivery(1, "2026-07-01", 5000.0)
        assert delivery_id == 1

        dv = await get_delivery(delivery_id)
        assert dv is not None
        assert dv["supplier_name"] == "Sup"
        assert dv["amount"] == 5000.0
        assert dv["paid"] == 0

    async def test_get_deliveries_by_supplier(self, db):
        from bot.db import add_supplier, add_delivery, get_deliveries

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await add_delivery(1, "2026-07-05", 200.0)

        deliveries = await get_deliveries(supplier_id=1)
        assert len(deliveries) == 2

    async def test_get_deliveries_empty(self, db):
        from bot.db import get_deliveries

        deliveries = await get_deliveries(supplier_id=999)
        assert len(deliveries) == 0

    async def test_get_deliveries_date_range(self, db):
        from bot.db import add_supplier, add_delivery, get_deliveries

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await add_delivery(1, "2026-07-15", 200.0)

        result = await get_deliveries(date_from="2026-07-10", date_to="2026-07-20")
        assert len(result) == 1
        assert result[0]["amount"] == 200.0

    async def test_get_deliveries_unpaid_only(self, db):
        from bot.db import add_supplier, add_delivery, mark_paid, get_deliveries

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await add_delivery(1, "2026-07-05", 200.0)
        await mark_paid(1)

        unpaid = await get_deliveries(unpaid_only=True)
        assert len(unpaid) == 1
        assert unpaid[0]["id"] == 2

    async def test_get_delivery_not_found(self, db):
        from bot.db import get_delivery

        dv = await get_delivery(999)
        assert dv is None

    async def test_mark_paid(self, db):
        from bot.db import add_supplier, add_delivery, get_delivery, mark_paid

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await mark_paid(1)
        dv = await get_delivery(1)
        assert dv["paid"] == 1

    async def test_set_manual_end_date(self, db):
        from bot.db import add_supplier, add_delivery, set_manual_end_date, get_delivery

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await set_manual_end_date(1, "2026-08-01")
        dv = await get_delivery(1)
        assert dv["manual_end_date"] == "2026-08-01"

    async def test_clear_manual_end_date(self, db):
        from bot.db import add_supplier, add_delivery, set_manual_end_date, clear_manual_end_date, get_delivery

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await set_manual_end_date(1, "2026-08-01")
        await clear_manual_end_date(1)
        dv = await get_delivery(1)
        assert dv["manual_end_date"] is None

    async def test_edit_delivery_date(self, db):
        from bot.db import add_supplier, add_delivery, edit_delivery, get_delivery

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await edit_delivery(1, delivery_date="2026-07-15")
        dv = await get_delivery(1)
        assert dv["delivery_date"] == "2026-07-15"

    async def test_edit_delivery_amount(self, db):
        from bot.db import add_supplier, add_delivery, edit_delivery, get_delivery

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await edit_delivery(1, amount=999.99)
        dv = await get_delivery(1)
        assert dv["amount"] == 999.99

    async def test_delete_delivery(self, db):
        from bot.db import add_supplier, add_delivery, delete_delivery, get_delivery

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await delete_delivery(1)
        dv = await get_delivery(1)
        assert dv is None

    async def test_get_deliveries_for_date(self, db):
        from bot.db import add_supplier, add_delivery, get_deliveries_for_date

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)

        deferral_end_date = "2026-07-30"
        result = await get_deliveries_for_date(deferral_end_date)
        assert len(result) == 1
        assert result[0]["supplier_name"] == "Sup"

    async def test_get_deliveries_for_date_no_match(self, db):
        from bot.db import add_supplier, add_delivery, get_deliveries_for_date

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)

        result = await get_deliveries_for_date("2026-08-15")
        assert result == []

    async def test_get_deliveries_for_date_no_unpaid(self, db):
        from bot.db import add_supplier, add_delivery, mark_paid, get_deliveries_for_date

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await mark_paid(1)

        result = await get_deliveries_for_date("2026-07-31")
        assert result == []

    async def test_get_deliveries_for_date_with_manual_end(self, db):
        from bot.db import add_supplier, add_delivery, set_manual_end_date, get_deliveries_for_date

        await add_supplier("Sup", 30)
        await add_delivery(1, "2026-07-01", 100.0)
        await set_manual_end_date(1, "2026-09-01")

        result = await get_deliveries_for_date("2026-09-01")
        assert len(result) == 1

        result2 = await get_deliveries_for_date("2026-07-31")
        assert result2 == []

    async def test_unpaid_with_deferral_end(self, db):
        from bot.db import add_supplier, add_delivery, mark_paid, get_unpaid_with_deferral_end

        await add_supplier("A", 5)
        await add_delivery(1, "2026-07-06", 100.0)
        await add_delivery(1, "2026-07-08", 200.0)
        await mark_paid(1)

        unpaid = await get_unpaid_with_deferral_end()
        assert len(unpaid) == 1
        assert unpaid[0]["id"] == 2
        assert unpaid[0]["deferral_end"] == "2026-07-13"

    async def test_get_overdue(self, db):
        from bot.db import add_supplier, add_delivery, get_overdue

        await add_supplier("A", 5)
        await add_delivery(1, "2026-07-06", 100.0)

        assert len(await get_overdue("2026-07-11")) == 1
        assert len(await get_overdue("2026-07-10")) == 0

    async def test_get_upcoming(self, db):
        from bot.db import add_supplier, add_delivery, get_upcoming

        await add_supplier("A", 5)
        await add_delivery(1, "2026-07-06", 100.0)

        assert len(await get_upcoming("2026-07-06", 4)) == 1
        assert len(await get_upcoming("2026-07-06", 3)) == 0
        assert len(await get_upcoming("2026-07-10", 1)) == 0

    async def test_get_all_deliveries_with_end(self, db):
        from bot.db import add_supplier, add_delivery, mark_paid, get_all_deliveries_with_end

        await add_supplier("A", 5)
        await add_delivery(1, "2026-07-06", 100.0)
        await add_delivery(1, "2026-07-08", 200.0)
        await mark_paid(1)

        all_dv = await get_all_deliveries_with_end()
        assert len(all_dv) == 2
        assert all("deferral_end" in d for d in all_dv)

    async def test_fk_enforced(self, db):
        from bot.db import add_delivery
        import pytest as _pytest

        with _pytest.raises(Exception):
            await add_delivery(999, "2026-07-01", 100.0)

    async def test_reschedule_row_manual_end_access(self, db):
        from bot.db import add_supplier, add_delivery, get_deliveries

        await add_supplier("Sup", 5)
        await add_delivery(1, "2026-07-06", 200.0)
        rows = await get_deliveries(supplier_id=1, unpaid_only=True)
        assert rows[0]["manual_end_date"] is None

    async def test_backend_selection(self, monkeypatch):
        import bot.db as db_module

        monkeypatch.setattr(db_module, "_backend", None)
        monkeypatch.setattr(db_module, "TURSO_URL", None)
        monkeypatch.setattr(db_module, "TURSO_AUTH_TOKEN", None)
        assert isinstance(db_module._get_backend(), db_module._LocalBackend)

        monkeypatch.setattr(db_module, "_backend", None)
        monkeypatch.setattr(db_module, "TURSO_URL", "libsql://test.turso.io")
        monkeypatch.setattr(db_module, "TURSO_AUTH_TOKEN", "secret")
        assert isinstance(db_module._get_backend(), db_module._TursoBackend)

    async def test_partial_turso_config_raises(self, monkeypatch):
        import bot.db as db_module
        import pytest as _pytest

        monkeypatch.setattr(db_module, "_backend", None)
        monkeypatch.setattr(db_module, "TURSO_URL", "libsql://test.turso.io")
        monkeypatch.setattr(db_module, "TURSO_AUTH_TOKEN", None)
        with _pytest.raises(RuntimeError):
            db_module._get_backend()

        monkeypatch.setattr(db_module, "TURSO_URL", None)
        monkeypatch.setattr(db_module, "TURSO_AUTH_TOKEN", "secret")
        with _pytest.raises(RuntimeError):
            db_module._get_backend()


class TestTursoBackend:
    async def _backend(self, tmp_path):
        import bot.db as db_module
        from bot.db import _TursoBackend

        backend = _TursoBackend(str(tmp_path / "turso.db"), "ignored")
        await backend.init()
        return backend

    async def test_full_crud_via_libsql_file(self, tmp_path):
        backend = await self._backend(tmp_path)
        assert await backend.execute_bool(
            "INSERT INTO suppliers (name, deferral_days) VALUES (?, ?)", ["Sup", 30]
        )
        rows = await backend.fetch_all("SELECT id, name, deferral_days FROM suppliers")
        assert rows == [{"id": 1, "name": "Sup", "deferral_days": 30}]

        rowid = await backend.execute_insert(
            "INSERT INTO deliveries (supplier_id, delivery_date, amount) VALUES (?, ?, ?)",
            [1, "2026-07-06", 100.0],
        )
        assert rowid == 1
        one = await backend.fetch_one("SELECT amount FROM deliveries WHERE id = ?", [1])
        assert one == {"amount": 100.0}

        assert await backend.fetch_one("SELECT 1 WHERE 1 = 0") is None
        assert await backend.execute_bool("INSERT INTO suppliers (name, deferral_days) VALUES (?, ?)", ["Sup", 30]) is False

    async def test_execute_bool_constraint_vs_real_error(self, tmp_path):
        backend = await self._backend(tmp_path)
        import pytest as _pytest

        assert await backend.execute_bool(
            "INSERT INTO suppliers (name, deferral_days) VALUES (?, ?)", ["Dup", 5]
        ) is True
        assert await backend.execute_bool(
            "INSERT INTO suppliers (name, deferral_days) VALUES (?, ?)", ["Dup", 5]
        ) is False
        with _pytest.raises(Exception):
            await backend.execute_bool("INSERT INTO nope (x) VALUES (1)", [])

    async def test_execute_many_single_commit(self, tmp_path):
        backend = await self._backend(tmp_path)
        await backend.execute_many([
            ("INSERT INTO suppliers (name, deferral_days) VALUES (?, ?)", ["M", 10]),
            ("INSERT INTO suppliers (name, deferral_days) VALUES (?, ?)", ["N", 15]),
        ])
        rows = await backend.fetch_all("SELECT name FROM suppliers ORDER BY name")
        assert [r["name"] for r in rows] == ["M", "N"]
