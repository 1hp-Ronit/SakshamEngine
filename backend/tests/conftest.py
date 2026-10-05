"""Test harness: isolated SQLite per test, simulated messaging, no LLM, mock services reached in-process via ASGI."""
from __future__ import annotations

import os

# Must be set before app modules read settings. Env vars win over .env, so a developer's real keys are never used in tests.
os.environ.update({
    "MESSAGING_MODE": "simulated", "LLM_FALLBACK_ONLY": "true", "GEMINI_API_KEY": "", "WHATSAPP_ACCESS_TOKEN": "",
    "SECRET_KEY": "test-secret-key", "PUBLIC_BASE_URL": "https://test.example.com", "DEMO_RECIPIENT_NUMBER": "",
})

import httpx
import pytest
import pytest_asyncio

from app.core import database
from app.core.http import override_http_client


@pytest_asyncio.fixture
async def db_ready(tmp_path):
    database.init_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.drop_and_create_all()
    yield
    await database.get_engine().dispose()


@pytest_asyncio.fixture
async def client(db_ready):
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
        override_http_client(c)  # adapters call /mock/* in-process
        yield c
    override_http_client(None)


@pytest_asyncio.fixture
async def db(db_ready):
    async with database.session_factory()() as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
def trained_model():
    """Ensure model artifacts exist (trains once if missing — takes a couple of minutes on a cold checkout)."""
    from pathlib import Path

    from app.core.config import get_settings

    if not (Path(get_settings().env.ml_artifacts_dir) / "model.joblib").exists():
        from ml import train

        train.main()
