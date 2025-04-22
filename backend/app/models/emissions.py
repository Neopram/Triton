from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class EmissionRecord(Base):
    __tablename__ = "emission_records"

    id = Column(Integer, primary_key=True, index=True)

    vessel_id = Column(Integer, ForeignKey("vessels.id"), nullable=False)
    voyage_id = Column(Integer, ForeignKey("voyages.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    reporting_period = Column(String(20), nullable=False)  # e.g., "2024-Q1", "2025-Annual"
    fuel_type = Column(String(50), nullable=False, default="IFO380")
    fuel_consumed_mt = Column(Float, nullable=False)
    co2_emitted_mt = Column(Float, nullable=False)

    eexi_rating = Column(String(5), nullable=True)
    cii_score = Column(Float, nullable=True)
    cii_rating = Column(String(5), nullable=True)

    regulation_flag = Column(String(50), default="EU ETS")  # Optional for expansion

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")
    vessel = relationship("Vessel")
    voyage = relationship("Voyage")

    def __repr__(self):
        return f"<EmissionRecord id={self.id} vessel={self.vessel_id} CO₂={self.co2_emitted_mt} MT>"
