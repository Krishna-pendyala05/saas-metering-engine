from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models import all_models
from app.core.config import settings

from sqlalchemy.orm import selectinload

async def get_current_subscription(db: AsyncSession, org_id: int) -> all_models.Subscription:
    # Get active subscription and its plan
    stmt = (
        select(all_models.Subscription)
        .options(selectinload(all_models.Subscription.plan))
        .where(all_models.Subscription.organization_id == org_id)
        .where(all_models.Subscription.is_active == True)
    )
    result = await db.execute(stmt)
    return result.scalars().first()

async def track_and_enforce_usage(db: AsyncSession, org_id: int) -> tuple[int, int]:
    # 1. Get Limits
    subscription = await get_current_subscription(db, org_id)
    
    if not subscription:
        # Default policy: No active sub -> Block or Free Tier? 
        # Assuming we need a plan to operate.
        raise HTTPException(status_code=403, detail="No active subscription found.")

    plan_limit = subscription.plan.monthly_quota
    
    # 2. Determine Period
    now = datetime.now(timezone.utc)
    
    if settings.DEMO_MODE:
        # DEMO MODE: 5-minute rolling windows (as per original portfolio design)
        minute_window = (now.minute // 5) * 5
        period_start = now.replace(minute=minute_window, second=0, microsecond=0)
    else:
        # PRODUCTION MODE: Monthly windows (Standard SaaS behavior)
        # Resets at 00:00 UTC on the 1st of every month
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 3. Atomic Check-and-Increment
    # Strategy: Ensure record exists safely, then Atomic Update.
    
    # 3a. Ensure record exists (Atomic Insert)
    
    insert_stmt = (
        pg_insert(all_models.UsageRecord)
        .values(
            organization_id=org_id,
            period_start=period_start,
            request_count=0
        )
        .on_conflict_do_nothing(
            index_elements=['organization_id', 'period_start']
        )
    )
    await db.execute(insert_stmt)
    
    # 3b. Atomic Update
    stmt = (
        update(all_models.UsageRecord)
        .where(all_models.UsageRecord.organization_id == org_id)
        .where(all_models.UsageRecord.period_start == period_start)
        .where(all_models.UsageRecord.request_count < plan_limit)
        .values(request_count=all_models.UsageRecord.request_count + 1)
        .returning(all_models.UsageRecord.request_count)
        .execution_options(synchronize_session=False)
    )
    
    result = await db.execute(stmt)
    new_count = result.scalars().first()
    
    if new_count is None:
        # Update failed. 2 Possibilities: 
        # 1. Record missing (Impossible due to 3a, unless deleted concurrently)
        # 2. Condition (count < limit) failed -> Limit Exceeded
        
        # Read current count to confirm validity
        check_stmt = select(all_models.UsageRecord).where(
            all_models.UsageRecord.organization_id == org_id,
            all_models.UsageRecord.period_start == period_start
        )
        record = (await db.execute(check_stmt)).scalars().first()
        
        if record and record.request_count >= plan_limit:
             if settings.DEMO_MODE:
                 next_window = period_start + timedelta(minutes=5)
             elif period_start.month == 12:
                 next_window = period_start.replace(year=period_start.year + 1, month=1)
             else:
                 next_window = period_start.replace(month=period_start.month + 1)
             
             seconds_left = int((next_window - datetime.now(timezone.utc)).total_seconds())
             raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Try again in {seconds_left} seconds.")
        
        # Fallback if something really weird happened
        raise HTTPException(status_code=500, detail="Metering error.")
    
    await db.commit()
    return new_count, plan_limit

