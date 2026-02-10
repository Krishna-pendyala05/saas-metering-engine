from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models import all_models

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
    subscription = result.scalars().first()
    return subscription

async def track_and_enforce_usage(db: AsyncSession, org_id: int) -> tuple[int, int]:
    # 1. Get Limits
    subscription = await get_current_subscription(db, org_id)
    
    if not subscription:
        # Default policy: No active sub -> Block or Free Tier? 
        # Assuming we need a plan to operate.
        raise HTTPException(status_code=403, detail="No active subscription found.")

    plan_limit = subscription.plan.monthly_quota
    
    # 2. Determine Period (5-minute windows)
    now = datetime.now(timezone.utc)
    # Calculate 5-minute window start: e.g., 10:02 -> 10:00, 10:07 -> 10:05
    minute_window = (now.minute // 5) * 5
    period_start = now.replace(minute=minute_window, second=0, microsecond=0)

    # 3. Atomic Check-and-Increment
    # Strategy: Try to update WHERE count < limit
    # If update returns 0 rows, check if it's because record missing OR limit reached.
    
    stmt = (
        update(all_models.UsageRecord)
        .where(all_models.UsageRecord.organization_id == org_id)
        .where(all_models.UsageRecord.period_start == period_start)
        .where(all_models.UsageRecord.request_count < plan_limit)
        .values(request_count=all_models.UsageRecord.request_count + 1)
        .returning(all_models.UsageRecord.request_count) # Return new count
        .execution_options(synchronize_session=False)
    )
    
    result = await db.execute(stmt)
    new_count = result.scalars().first()
    
    if new_count is None:
        # Either record doesn't exist, or limit reached.
        # Check if record exists
        check_stmt = select(all_models.UsageRecord).where(
            all_models.UsageRecord.organization_id == org_id,
            all_models.UsageRecord.period_start == period_start
        )
        record = (await db.execute(check_stmt)).scalars().first()
        
        if record:
            # Record exists, so limit must be reached
            if record.request_count >= plan_limit:
                 # Calculate time until reset
                 next_window = period_start + timedelta(minutes=5)
                 seconds_left = int((next_window - datetime.now(timezone.utc)).total_seconds())
                 raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Try again in {seconds_left} seconds.")
            return record.request_count, plan_limit # Should ideally not reach here if logic above is correct
        else:
            # Record missing, create it.
            try:
                new_record = all_models.UsageRecord(
                    organization_id=org_id,
                    period_start=period_start,
                    request_count=1 # Start at 1
                )
                db.add(new_record)
                await db.commit()
                return 1, plan_limit
            except IntegrityError:
                await db.rollback()
                # Retry update recursively or just fail specific request
                return await track_and_enforce_usage(db, org_id)
    else:
        # Update successful, usage incremented.
        await db.commit()
        return new_count, plan_limit

