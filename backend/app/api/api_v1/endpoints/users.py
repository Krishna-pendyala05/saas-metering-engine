from typing import Any, List
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.core import security
from app.core.db import get_db
from app.models import all_models
from app.schemas import user as user_schema

router = APIRouter()

@router.post("/", response_model=user_schema.User)
async def create_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: user_schema.UserCreate,
) -> Any:
    """
    Create new user and their organization.
    """
    # Check if user exists
    result = await db.execute(select(all_models.User).where(all_models.User.email == user_in.email))
    user = result.scalars().first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    
    # Check if org exists (enforcing unique org names for simplicity)
    result_org = await db.execute(select(all_models.Organization).where(all_models.Organization.name == user_in.organization_name))
    org = result_org.scalars().first()
    if org:
         raise HTTPException(
            status_code=400,
            detail="The organization name is already taken.",
        )

    # Create Org
    new_org = all_models.Organization(name=user_in.organization_name)
    db.add(new_org)
    await db.flush() # Flush to get ID

    # Create User
    new_user = all_models.User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        organization_id=new_org.id,
        role=all_models.UserRole.ORG_ADMIN # First user is Admin
    )
    db.add(new_user)
    
    # Assign Default 'Free' Subscription
    result_plan = await db.execute(select(all_models.SubscriptionPlan).where(all_models.SubscriptionPlan.name == "Free"))
    free_plan = result_plan.scalars().first()
    
    if not free_plan:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: 'Free' subscription plan not found. Seed the database."
        )

    new_sub = all_models.Subscription(
        organization_id=new_org.id,
        plan_id=free_plan.id,
        is_active=True
    )
    db.add(new_sub)
    
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.get("/me", response_model=user_schema.User)
async def read_user_me(
    current_user: all_models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user
