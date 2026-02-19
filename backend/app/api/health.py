from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.db import get_db

router = APIRouter()

@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Health check endpoint to verify service and database connectivity.
    """
    try:
        # Check database connection
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: Database connection failed. {str(e)}"
        )
