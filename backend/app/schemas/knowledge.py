from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

# ─────────────────────────────────────────────
# 📝 Document creation schema
# ─────────────────────────────────────────────
class DocumentCreate(BaseModel):
    text: str = Field(..., example="This is a document about maritime regulations.")
    metadata: Optional[Dict[str, Any]] = Field(None, example={"category": "regulations", "year": 2024})
    doc_id: Optional[str] = Field(None, example="doc_123456")

# ─────────────────────────────────────────────
# 📋 Document info schema
# ─────────────────────────────────────────────
class DocumentInfo(BaseModel):
    doc_id: str
    metadata: Dict[str, Any]
    text_preview: str

# ─────────────────────────────────────────────
# 📋 Document list schema
# ─────────────────────────────────────────────
class DocumentList(BaseModel):
    documents: List[DocumentInfo]
    total: int
    page: int
    page_size: int

# ─────────────────────────────────────────────
# 🔍 Knowledge search query
# ─────────────────────────────────────────────
class KnowledgeSearchQuery(BaseModel):
    query: str = Field(..., example="What are the latest maritime regulations?")
    limit: Optional[int] = Field(5, ge=1, le=20, example=5)
    similarity_threshold: Optional[float] = Field(10.0, ge=0.1, le=100.0, example=10.0)

# ─────────────────────────────────────────────
# 🔍 Document search result
# ─────────────────────────────────────────────
class DocumentSearchResult(BaseModel):
    doc_id: str
    metadata: Dict[str, Any]
    text_preview: str
    relevance_score: float