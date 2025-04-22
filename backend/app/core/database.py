from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Create Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# Create SessionLocal
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

# Base class for models
Base = declarative_base()

# Dependency for FastAPI routes
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Called on app startup
async def init_db():
    import app.models.user
    import app.models.voyage
    import app.models.vessel
    import app.models.finance
    import app.models.market
    import app.models.market_insight
    import app.models.message  # Add the new model
    import app.models.emissions
    import app.models.__init__

    async with engine.begin() as conn:
        if settings.ENVIRONMENT == "development":
            await conn.run_sync(Base.metadata.create_all)