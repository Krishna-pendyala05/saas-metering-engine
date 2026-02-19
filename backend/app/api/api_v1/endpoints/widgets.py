from typing import Any, List
from fastapi import APIRouter, Depends
from app.api import deps
from app import schemas

router = APIRouter()

@router.get("/", dependencies=[Depends(deps.check_usage_limits)], response_model=List[schemas.Widget])
async def read_widgets() -> Any:
    """
    Retrieve widgets. This endpoint is metered. You will get 5 requests per five minute.
    """
    return [{"name": "Widget A"}, {"name": "Widget B"}]
