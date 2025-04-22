from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
import uvicorn
import logging

from app.core.config import settings
from app.core.logging import configure_logger, api_logger
from app.core.database import init_db
from app.api.v1.endpoints import (
    auth, voyages, vessels, finance, market, ocr, emissions, ai, tce, training, knowledge
)
from app.middleware.request_logger import RequestLoggerMiddleware

# Initialize logger
logger = configure_logger()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Maritime Business Intelligence Platform",
        description="A scalable platform for voyage economics, fleet operations, and financial visibility.",
        version="1.0.0"
    )

    # Middleware: CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add request logger middleware
    app.add_middleware(RequestLoggerMiddleware)

    # Routers
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(voyages.router, prefix="/api/v1/voyages", tags=["Voyages"])
    app.include_router(vessels.router, prefix="/api/v1/vessels", tags=["Vessels"])
    app.include_router(finance.router, prefix="/api/v1/finance", tags=["Finance"])
    app.include_router(market.router, prefix="/api/v1/market", tags=["Market Intelligence"])
    app.include_router(ocr.router, prefix="/api/v1/ocr", tags=["OCR"])
    app.include_router(emissions.router, prefix="/api/v1/emissions", tags=["Emissions"])
    app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI Interface"])
    app.include_router(tce.router, prefix="/api/v1/tce", tags=["TCE Calculator"])
    app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge Base"])
    app.include_router(training.router, prefix="/api/v1/training", tags=["Training"])

    # Health check
    @app.get("/", tags=["Health"])
    async def health():
        return JSONResponse(status_code=200, content={"status": "ok"})

    # Exception handling
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(f"HTTP error: {exc.detail}")
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning("Validation error", exc_info=True)
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    # Startup
    @app.on_event("startup")
    async def startup_event():
        logger.info("🚀 Starting Maritime Business Intelligence Platform...")
        
        # Ensure storage directories exist
        os.makedirs(settings.FILE_STORAGE_PATH, exist_ok=True)
        os.makedirs(os.path.join(settings.FILE_STORAGE_PATH, "message_attachments"), exist_ok=True)
        
        # Ensure log directory exists
        os.makedirs(settings.LOG_DIR, exist_ok=True)
        
        try:
            await init_db()
            logger.info("✅ Database connection established.")
        except Exception as e:
            logger.error(f"❌ Database init failed: {e}")

        try:
            from app.services.phi3_engine import query_phi3
            res = query_phi3("Hello, are you ready?")
            logger.info(f"🤖 Phi-3 engine responded: {res[:60]}...")
        except Exception as e:
            logger.warning(f"⚠️ Phi-3 local model not available: {e}")
        
        api_logger.info("✅ Request logging middleware initialized")

    return app

# Entry point
app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")