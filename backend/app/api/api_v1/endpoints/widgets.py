from typing import Any, List
from fastapi import APIRouter, Depends
from app.api import deps
from app.schemas import user as user_schema

router = APIRouter()

@router.get("/", dependencies=[Depends(deps.check_usage_limits)])
async def read_widgets() -> Any:
    """
    Retrieve widgets. This endpoint is metered. You will get 5 requests per five minute.
    """
    return [{"name": "Widget A"}, {"name": "Widget B"}]
