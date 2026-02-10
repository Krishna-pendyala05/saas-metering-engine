import asyncio
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models import all_models

async def check_usage():
    async with AsyncSessionLocal() as db:
        # Get usage for Org ID 5 (from your previous "users/me" response)
        stmt = select(all_models.UsageRecord).where(all_models.UsageRecord.organization_id == 5)
        result = await db.execute(stmt)
        record = result.scalars().first()
        
        if record:
            print(f"Current Usage Count: {record.request_count}")
            print(f"Last Updated: {record.last_updated}")
        else:
            print("No Usage Record found for Organization 5")

if __name__ == "__main__":
    asyncio.run(check_usage())
