from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, func, Float
from sqlalchemy.orm import relationship
from app.core.database import Base


class DocumentType(str):
    bill_of_lading = "Bill of Lading"
    invoice = "Invoice"
    voyage_report = "Voyage Report"
    fuel_report = "Bunker Delivery Note"
    other = "Other"


class OCRDocument(Base):
    __tablename__ = "ocr_documents"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    voyage_id = Column(Integer, ForeignKey("voyages.id"), nullable=True)

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False, default="image/pdf")

    document_type = Column(String(50), default="Other")
    extracted_port = Column(String(100), nullable=True)
    extracted_date = Column(DateTime, nullable=True)
    extracted_quantity = Column(Float, nullable=True)
    extracted_vessel_name = Column(String(100), nullable=True)

    status = Column(String(50), default="Pending")  # or "Processed", "Failed"
    error_message = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    voyage = relationship("Voyage")

    def __repr__(self):
        return f"<OCRDocument id={self.id} type={self.document_type} file={self.file_name}>"
