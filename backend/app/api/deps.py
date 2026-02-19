from typing import Generator, Optional
from fastapi import Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core import security, metering
from app.core.config import settings
from app.core.db import get_db
from app.models import all_models
from app.schemas import user as user_schema

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> all_models.User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = user_schema.TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    result = await db.execute(
        select(all_models.User).where(all_models.User.id == int(token_data.sub))
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def get_current_active_user(
    current_user: all_models.User = Depends(get_current_user),
) -> all_models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_active_superuser(
    current_user: all_models.User = Depends(get_current_user),
) -> all_models.User:
    if current_user.role != all_models.UserRole.PLATFORM_ADMIN:
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user


async def check_usage_limits(
    response: Response,
    current_user: all_models.User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    FastAPI dependency that intercepts every metered request.
    Admins bypass limits. All other users have usage tracked atomically.
    """
    if current_user.role == all_models.UserRole.PLATFORM_ADMIN:
        return  # Admins bypass limits

    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User not part of an organization")

    used, limit = await metering.track_and_enforce_usage(db, current_user.organization_id)

    # Inject standard rate-limit headers for client visibility
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Used"] = str(used)
    response.headers["X-RateLimit-Remaining"] = str(limit - used)
