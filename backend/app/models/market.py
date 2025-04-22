from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class MarketRateType(str):
    spot = "Spot"
    contract = "Contract"


class MarketReport(Base):
    __tablename__ = "market_reports"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    vessel_type = Column(String(50), nullable=False)
    cargo_type = Column(String(50), nullable=True)
    route = Column(String(100), nullable=False, index=True)
    rate_type = Column(String(20), default="Spot")
    rate_usd_per_mt = Column(Float, nullable=False)

    source = Column(String(100), nullable=True, default="Manual Entry")
    comment = Column(String(255), nullable=True)

    report_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    def __repr__(self):
        return f"<MarketReport id={self.id} {self.route} | {self.rate_usd_per_mt} USD/MT>"
