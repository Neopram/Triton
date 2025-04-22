from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─────────────────────────────────────────────
# 📥 Base schema
# ─────────────────────────────────────────────
class OCRBase(BaseModel):
    file_name: str = Field(..., example="BOL_2024_03_Houston.pdf")
    file_path: str = Field(..., example="/uploads/BOL_2024_03_Houston.pdf")
    file_type: Optional[str] = Field(default="application/pdf")

    document_type: Optional[str] = Field(default="Other", example="Bill of Lading")
    extracted_port: Optional[str] = Field(None, example="Houston")
    extracted_date: Optional[datetime] = None
    extracted_quantity: Optional[float] = Field(None, example=85000)
    extracted_vessel_name: Optional[str] = Field(None, example="MT Atlantic Wind")

    voyage_id: Optional[int] = None
    status: Optional[str] = Field(default="Pending")
    error_message: Optional[str] = None


# ─────────────────────────────────────────────
# 📄 Upload schema
# ─────────────────────────────────────────────
class OCRDocumentCreate(OCRBase):
    pass


# ─────────────────────────────────────────────
# ✏️ Update schema
# ─────────────────────────────────────────────
class OCRDocumentUpdate(BaseModel):
    extracted_port: Optional[str]
    extracted_date: Optional[datetime]
    extracted_quantity: Optional[float]
    extracted_vessel_name: Optional[str]
    status: Optional[str]
    error_message: Optional[str]


# ─────────────────────────────────────────────
# 📤 Output schema
# ─────────────────────────────────────────────
class OCRDocumentOut(OCRBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True
