import asyncio
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models import all_models

async def verify_data():
    async with AsyncSessionLocal() as db:
        # Check Admin
        result = await db.execute(select(all_models.User).where(all_models.User.email == "admin@example.com"))
        admin = result.scalars().first()
        if admin:
            print(f"Verified Admin: {admin.email}, Role: {admin.role}")
        else:
            print("Admin NOT found!")

        # Check Plans
        result = await db.execute(select(all_models.SubscriptionPlan))
        plans = result.scalars().all()
        print(f"Verfied Plans: {[p.name for p in plans]}")

if __name__ == "__main__":
    asyncio.run(verify_data())
