from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
import pytesseract
from PIL import Image
import io

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.ocr import OCRDocument
from app.schemas.ocr import OCRDocumentCreate, OCRDocumentUpdate, OCRDocumentOut
from app.models.user import User, UserRole

router = APIRouter()


# ─────────────────────────────────────────────
# 🔐 Role Check
# ─────────────────────────────────────────────
def can_manage_documents(user: User) -> bool:
    return user.role in [UserRole.admin, UserRole.fleet_manager, UserRole.operator]


# ─────────────────────────────────────────────
# 📤 Upload document metadata (OCR stub)
# ─────────────────────────────────────────────
@router.post("/", response_model=OCRDocumentOut, status_code=201)
async def upload_ocr_document(
    data: OCRDocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not can_manage_documents(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    doc = OCRDocument(
        **data.dict(),
        user_id=current_user.id
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


# ─────────────────────────────────────────────
# 📃 List uploaded documents
# ─────────────────────────────────────────────
@router.get("/", response_model=List[OCRDocumentOut])
async def list_ocr_documents(
    document_type: Optional[str] = None,
    voyage_id: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(OCRDocument)
    if document_type:
        query = query.where(OCRDocument.document_type == document_type)
    if voyage_id:
        query = query.where(OCRDocument.voyage_id == voyage_id)
    if status:
        query = query.where(OCRDocument.status == status)

    result = await db.execute(query)
    return result.scalars().all()


# ─────────────────────────────────────────────
# 🔎 View document detail
# ─────────────────────────────────────────────
@router.get("/{document_id}", response_model=OCRDocumentOut)
async def get_ocr_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(OCRDocument).where(OCRDocument.id == document_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ─────────────────────────────────────────────
# ✏️ Correct or update extracted data
# ─────────────────────────────────────────────
@router.put("/{document_id}", response_model=OCRDocumentOut)
async def update_ocr_document(
    document_id: int,
    updates: OCRDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not can_manage_documents(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    result = await db.execute(select(OCRDocument).where(OCRDocument.id == document_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    for key, value in updates.dict(exclude_unset=True).items():
        setattr(doc, key, value)

    await db.commit()
    await db.refresh(doc)
    return doc


# ─────────────────────────────────────────────
# 📑 Analyze uploaded image or PDF with OCR
# ─────────────────────────────────────────────
@router.post("/analyze")
async def analyze_ocr_file(file: UploadFile = File(...)):
    """
    Upload a file (image or scanned PDF) and run OCR to extract text.
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        text = pytesseract.image_to_string(image)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
