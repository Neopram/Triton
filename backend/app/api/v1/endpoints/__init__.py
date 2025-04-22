from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, voyages, vessels, finance, market, ocr, emissions, ai, tce, config, knowledge
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Auth"])
router.include_router(voyages.router, prefix="/voyages", tags=["Voyages"])
router.include_router(vessels.router, prefix="/vessels", tags=["Vessels"])
router.include_router(finance.router, prefix="/finance", tags=["Finance"])
router.include_router(market.router, prefix="/market", tags=["Market"])
router.include_router(ocr.router, prefix="/ocr", tags=["OCR"])
router.include_router(emissions.router, prefix="/emissions", tags=["Emissions"])
router.include_router(ai.router, prefix="/ai", tags=["AI"])
router.include_router(tce.router, prefix="/tce", tags=["TCE"])
router.include_router(config.router, prefix="/config", tags=["Config"])
router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge"])