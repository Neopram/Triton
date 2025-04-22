from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class VesselType(str, enum.Enum):
    tanker = "Tanker"
    bulker = "Bulker"
    container = "Container"
    lng = "LNG"
    lpg = "LPG"
    ro_ro = "Ro-Ro"
    general_cargo = "General Cargo"


class Vessel(Base):
    __tablename__ = "vessels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    imo_number = Column(String(20), unique=True, nullable=True)
    call_sign = Column(String(20), nullable=True)
    flag = Column(String(50), nullable=True)

    vessel_type = Column(Enum(VesselType), nullable=False, default=VesselType.tanker)
    dwt = Column(Float, nullable=True)  # Deadweight
    draft = Column(Float, nullable=True)
    loa = Column(Float, nullable=True)  # Length overall
    beam = Column(Float, nullable=True) # Width

    fuel_type = Column(String(50), default="IFO380")
    consumption_at_sea = Column(Float, default=30.0)  # MT/day
    consumption_at_port = Column(Float, default=2.5)   # MT/day

    eexi_rating = Column(String(5), nullable=True)
    cii_rating = Column(String(5), nullable=True)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    voyages = relationship("Voyage", back_populates="vessel", lazy="joined", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Vessel id={self.id} name={self.name} type={self.vessel_type}>"
