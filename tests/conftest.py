from __future__ import annotations

import os
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-chars-long!!"

from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: F401, E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.utils.timeutil import utcnow  # noqa: E402

engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = async_sessionmaker(engine, expire_on_commit=False)


async def _override_db():
    async with TestSession() as session:
        yield session


@pytest.fixture(autouse=True)
async def _setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    app = create_app()
    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def make_user(client, email, role="driver", name="Test User"):
    # Public registration is drivers-only; partner/admin test users are
    # provisioned directly in the DB (like ParkSpot operations would),
    # then logged in so the token carries the elevated role.
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": name, "role": "driver"})
    assert r.status_code == 201, r.text
    if role != "driver":
        from sqlalchemy import update

        from app.db.models.enums import UserRole
        from app.db.models.user import User

        async with TestSession() as session:
            await session.execute(update(User).where(User.email == email).values(role=UserRole(role)))
            await session.commit()
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def future_window(hours_ahead=1, duration_h=2):
    from datetime import UTC

    start = utcnow().astimezone(UTC) + timedelta(hours=hours_ahead)
    return start, start + timedelta(hours=duration_h)


def iso_utc(dt):
    """Format a datetime as an explicit UTC ISO-8601 string for API payloads."""
    from datetime import UTC

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()
