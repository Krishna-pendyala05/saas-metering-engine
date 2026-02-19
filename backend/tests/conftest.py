import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.core.db import get_db
from app.models import all_models


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


async def _seed_subscription_plans(db: AsyncSession) -> None:
    """Insert the default Free plan if it doesn't already exist."""
    from sqlalchemy import select
    result = await db.execute(
        select(all_models.SubscriptionPlan).where(
            all_models.SubscriptionPlan.name == "Free"
        )
    )
    if result.scalars().first() is None:
        db.add(
            all_models.SubscriptionPlan(
                name="Free",
                description="Default free tier",
                monthly_quota=1000,
                rate_limit_per_minute=60,
            )
        )
        await db.commit()


@pytest.fixture(scope="module")
async def client() -> AsyncGenerator:
    # Seed required reference data before any test in this module runs
    async for db in get_db():
        await _seed_subscription_plans(db)
        break

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
