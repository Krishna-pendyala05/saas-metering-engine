import asyncio
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models import all_models
from app.core import security

async def init_db():
    async with AsyncSessionLocal() as db:
        # Create Plans
        plans = [
            {"name": "Free", "monthly_quota": 1000, "rate_limit_per_minute": 10},
            {"name": "Pro", "monthly_quota": 100000, "rate_limit_per_minute": 1000},
            {"name": "Enterprise", "monthly_quota": 1000000, "rate_limit_per_minute": None},
        ]
        
        for plan_data in plans:
            stmt = select(all_models.SubscriptionPlan).where(all_models.SubscriptionPlan.name == plan_data["name"])
            result = await db.execute(stmt)
            existing_plan = result.scalars().first()
            
            if not existing_plan:
                new_plan = all_models.SubscriptionPlan(**plan_data)
                db.add(new_plan)
        
        await db.commit()
        
        # Create Admin
        admin_email = "admin@example.com"
        stmt = select(all_models.User).where(all_models.User.email == admin_email)
        result = await db.execute(stmt)
        admin = result.scalars().first()
        
        if not admin:
            # Create Admin Org
            admin_org = all_models.Organization(name="Platform Admin Org")
            db.add(admin_org)
            await db.flush()
            
            new_admin = all_models.User(
                email=admin_email,
                hashed_password=security.get_password_hash("admin"),
                full_name="Platform Admin",
                role=all_models.UserRole.PLATFORM_ADMIN,
                organization_id=admin_org.id
            )
            db.add(new_admin)
            await db.commit()

        print("Database initialized successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
