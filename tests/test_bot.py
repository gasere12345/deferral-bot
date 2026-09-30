import socket

import pytest


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _request(url: str, method: str = "GET"):
    from aiohttp import ClientSession

    async with ClientSession() as session:
        async with session.request(method, url) as resp:
            return resp.status, await resp.text()


class TestHealthServer:
    async def test_root_returns_200(self, monkeypatch):
        from bot import bot as bot_module

        port = _free_port()
        monkeypatch.setattr(bot_module, "PORT", port)
        await bot_module.health_check()
        try:
            status, body = await _request(f"http://127.0.0.1:{port}/")
            assert status == 200
            assert body == "OK"
        finally:
            await bot_module._health_runner.cleanup()
            bot_module._health_runner = None

    async def test_health_path_returns_200(self, monkeypatch):
        from bot import bot as bot_module

        port = _free_port()
        monkeypatch.setattr(bot_module, "PORT", port)
        await bot_module.health_check()
        try:
            status, body = await _request(f"http://127.0.0.1:{port}/health")
            assert status == 200
            assert body == "OK"
        finally:
            await bot_module._health_runner.cleanup()
            bot_module._health_runner = None

    async def test_head_root_returns_200(self, monkeypatch):
        from bot import bot as bot_module

        port = _free_port()
        monkeypatch.setattr(bot_module, "PORT", port)
        await bot_module.health_check()
        try:
            status, _ = await _request(f"http://127.0.0.1:{port}/", method="HEAD")
            assert status == 200
        finally:
            await bot_module._health_runner.cleanup()
            bot_module._health_runner = None

    async def test_raises_when_port_unavailable(self, monkeypatch):
        from bot import bot as bot_module

        port = _free_port()
        blocker = socket.socket()
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocker.bind(("0.0.0.0", port))
        blocker.listen(1)
        monkeypatch.setattr(bot_module, "PORT", port)
        monkeypatch.setattr(bot_module, "_health_runner", None)
        try:
            with pytest.raises(OSError):
                await bot_module.health_check()
            assert bot_module._health_runner is None
        finally:
            blocker.close()


class TestStartup:
    async def test_raises_without_token(self, monkeypatch):
        from bot import bot as bot_module

        monkeypatch.setattr(bot_module, "TELEGRAM_TOKEN", None)
        with pytest.raises(RuntimeError, match="TELEGRAM_TOKEN"):
            await bot_module.main()

    async def test_db_init_success_first_attempt(self, monkeypatch):
        from bot import bot as bot_module

        calls = []

        async def _ok():
            calls.append(1)

        monkeypatch.setattr(bot_module, "db_init", _ok)
        await bot_module._init_db_with_retry(attempts=3, delay=0)
        assert len(calls) == 1

    async def test_db_init_retries_then_succeeds(self, monkeypatch):
        from bot import bot as bot_module

        calls = []

        async def _flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("turso down")

        monkeypatch.setattr(bot_module, "db_init", _flaky)
        await bot_module._init_db_with_retry(attempts=5, delay=0)
        assert len(calls) == 3

    async def test_db_init_raises_after_all_attempts(self, monkeypatch):
        from bot import bot as bot_module

        calls = []

        async def _always_fails():
            calls.append(1)
            raise ConnectionError("turso down")

        monkeypatch.setattr(bot_module, "db_init", _always_fails)
        with pytest.raises(RuntimeError, match="after 2 attempts"):
            await bot_module._init_db_with_retry(attempts=2, delay=0)
        assert len(calls) == 2


class TestIntEnv:
    def test_empty_value_falls_back_to_default(self, monkeypatch):
        from bot.config import _int_env

        monkeypatch.setenv("TEST_PORT", "")
        assert _int_env("TEST_PORT", 8080) == 8080

    def test_missing_value_falls_back_to_default(self, monkeypatch):
        from bot.config import _int_env

        monkeypatch.delenv("TEST_PORT", raising=False)
        assert _int_env("TEST_PORT", 8080) == 8080

    def test_garbage_value_falls_back_to_default(self, monkeypatch):
        from bot.config import _int_env

        monkeypatch.setenv("TEST_PORT", "not-a-number")
        assert _int_env("TEST_PORT", 8080) == 8080

    def test_valid_value_parsed(self, monkeypatch):
        from bot.config import _int_env

        monkeypatch.setenv("TEST_PORT", "10000")
        assert _int_env("TEST_PORT", 8080) == 10000
