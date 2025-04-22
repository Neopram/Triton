from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import enum


class VoyageStatus(str, enum.Enum):
    planned = "Planned"
    ongoing = "Ongoing"
    completed = "Completed"
    cancelled = "Cancelled"


class Voyage(Base):
    __tablename__ = "voyages"

    id = Column(Integer, primary_key=True, index=True)

    vessel_id = Column(Integer, ForeignKey("vessels.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    cargo_type = Column(String(50), nullable=True)
    cargo_quantity = Column(Float, nullable=True)

    origin_port = Column(String(100), nullable=False)
    destination_port = Column(String(100), nullable=False)

    laycan_start = Column(DateTime, nullable=True)
    laycan_end = Column(DateTime, nullable=True)
    departure_date = Column(DateTime, nullable=True)
    arrival_date = Column(DateTime, nullable=True)

    freight_rate = Column(Float, nullable=True)       # USD/MT or lump sum
    bunkers_cost = Column(Float, nullable=True)       # USD
    port_charges = Column(Float, nullable=True)
    canal_fees = Column(Float, nullable=True)
    tce_result = Column(Float, nullable=True)

    status = Column(Enum(VoyageStatus), default=VoyageStatus.planned)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    vessel = relationship("Vessel", back_populates="voyages")
    user = relationship("User", back_populates="voyages")

    def __repr__(self):
        return f"<Voyage {self.id} | {self.origin_port} → {self.destination_port} | Vessel {self.vessel_id}>"
