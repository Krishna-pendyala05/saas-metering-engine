from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import structlog
import time

from app.core.config import settings
from app.api.api_v1.api import api_router
from app.core.logging import setup_logging

# Setup Logging
setup_logging()
logger = structlog.get_logger()

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # structlog is synchronous — do NOT await it
    logger.info(
        "request_processed",
        path=request.url.path,
        method=request.method,
        status_code=response.status_code,
        process_time_ms=round(process_time * 1000, 2),
    )
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
    return response

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to the SaaS Metering Platform API", "mode": "DEMO" if settings.DEMO_MODE else "PRODUCTION"}
