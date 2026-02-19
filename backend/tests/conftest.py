import asyncio
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.config import settings
from app.models import all_models


def _sync_seed_database() -> None:
    """
    Seed required reference data synchronously before any pytest event loop starts.
    Uses its own short-lived engine so it doesn't pollute the app's connection pool.
    """
    from sqlalchemy import select

    async def _seed():
        engine = create_async_engine(settings.get_database_url(), echo=False)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as db:
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
        await engine.dispose()

    asyncio.run(_seed())


# Seed once before the whole session — runs synchronously, no pytest loop involved
_sync_seed_database()


@pytest.fixture(scope="function")
async def client() -> AsyncGenerator:
    """
    Function-scoped client: each test gets its own event loop and fresh
    asyncpg connections, avoiding the "Future attached to a different loop" error.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
