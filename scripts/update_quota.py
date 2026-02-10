import asyncio
from sqlalchemy import select, update
from app.core.db import AsyncSessionLocal
from app.models import all_models

async def lower_limit():
    async with AsyncSessionLocal() as db:
        # Find the Free plan
        stmt = select(all_models.SubscriptionPlan).where(all_models.SubscriptionPlan.name == "Free")
        result = await db.execute(stmt)
        plan = result.scalars().first()
        
        if plan:
            print(f"Old Quota: {plan.monthly_quota}")
            
            # Update quota to 5
            plan.monthly_quota = 5
            await db.commit()
            print("New Quota: 5 (Effective immediately)")
            
            # Reset your usage so you can test from 0 to 5
            reset_stmt = (
                update(all_models.UsageRecord)
                .where(all_models.UsageRecord.organization_id == 5)
                .values(request_count=0)
            )
            await db.execute(reset_stmt)
            await db.commit()
            print("Usage reset to 0 for Org 5.")

if __name__ == "__main__":
    asyncio.run(lower_limit())
