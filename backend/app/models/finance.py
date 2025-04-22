from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class FinanceRecord(Base):
    __tablename__ = "finance_records"

    id = Column(Integer, primary_key=True, index=True)

    voyage_id = Column(Integer, ForeignKey("voyages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    revenue_usd = Column(Float, nullable=False, default=0.0)
    cost_bunkers_usd = Column(Float, nullable=True, default=0.0)
    cost_ports_usd = Column(Float, nullable=True, default=0.0)
    cost_canals_usd = Column(Float, nullable=True, default=0.0)
    other_costs_usd = Column(Float, nullable=True, default=0.0)

    total_costs_usd = Column(Float, nullable=True, default=0.0)
    profit_usd = Column(Float, nullable=True, default=0.0)
    pnl_margin_pct = Column(Float, nullable=True, default=0.0)

    comment = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    voyage = relationship("Voyage")
    user = relationship("User")

    def __repr__(self):
        return f"<FinanceRecord id={self.id} profit={self.profit_usd} margin={self.pnl_margin_pct}%>"
