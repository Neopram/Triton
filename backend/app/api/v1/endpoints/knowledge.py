from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import uuid
import time
import os

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.middleware.permissions import verify_permission, ResourceType, Operation
from app.services.context_augmentor import get_context_augmentor
from app.services.file_parser import extract_text_from_file
from app.core.logging import api_logger, log_api_request
from app.schemas.knowledge import (
    DocumentCreate, DocumentInfo, DocumentList, 
    KnowledgeSearchQuery, DocumentSearchResult
)

router = APIRouter()

# ─────────────────────────────────────────────
# 📝 Add document to knowledge base
# ─────────────────────────────────────────────
@router.post("/documents", response_model=DocumentInfo, status_code=201)
async def add_document(
    document: DocumentCreate,
    current_user: User = Depends(verify_permission(ResourceType.INSIGHT, Operation.CREATE))
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Get augmentor
        augmentor = get_context_augmentor()
        
        # Prepare metadata
        metadata = document.metadata or {}
        metadata.update({
            "source": "api",
            "user_id": current_user.id,
            "created_at": time.time()
        })
        
        # Add document
        doc_id = document.doc_id or f"doc_{int(time.time())}_{hash(document.text) % 10000:04d}"
        success = await augmentor.add_document(
            text=document.text,
            metadata=metadata,
            doc_id=doc_id
        )
        
        if not success:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "POST", "/knowledge/documents", 500, processing_time, 
                current_user.id, "Failed to add document"
            )
            raise HTTPException(status_code=500, detail="Failed to add document")
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/knowledge/documents", 201, processing_time, current_user.id
        )
        
        return {
            "doc_id": doc_id,
            "metadata": metadata,
            "text_preview": document.text[:200] + "..." if len(document.text) > 200 else document.text
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/knowledge/documents", 500, processing_time, 
            current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# 📤 Upload file to knowledge base
# ─────────────────────────────────────────────
@router.post("/upload", response_model=DocumentInfo, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[Dict[str, Any]] = Body(None),
    current_user: User = Depends(verify_permission(ResourceType.INSIGHT, Operation.CREATE))
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Extract text from file
        file_content = await file.read()
        text = await extract_text_from_file(file_content, file.filename)
        
        if not text:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "POST", "/knowledge/upload", 400, processing_time, 
                current_user.id, "Failed to extract text from file"
            )
            raise HTTPException(status_code=400, detail="Failed to extract text from file")
        
        # Prepare metadata
        doc_metadata = metadata or {}
        doc_metadata.update({
            "source": "upload",
            "filename": file.filename,
            "user_id": current_user.id,
            "created_at": time.time()
        })
        
        # Add document
        doc_id = f"doc_{int(time.time())}_{hash(text) % 10000:04d}"
        augmentor = get_context_augmentor()
        success = await augmentor.add_document(
            text=text,
            metadata=doc_metadata,
            doc_id=doc_id
        )
        
        if not success:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "POST", "/knowledge/upload", 500, processing_time, 
                current_user.id, "Failed to add document"
            )
            raise HTTPException(status_code=500, detail="Failed to add document")
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/knowledge/upload", 201, processing_time, current_user.id
        )
        
        return {
            "doc_id": doc_id,
            "metadata": doc_metadata,
            "text_preview": text[:200] + "..." if len(text) > 200 else text
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/knowledge/upload", 500, processing_time, 
            current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# 🔍 Search knowledge base
# ─────────────────────────────────────────────
@router.post("/search", response_model=List[DocumentSearchResult])
async def search_knowledge(
    query: KnowledgeSearchQuery,
    current_user: User = Depends(verify_permission(ResourceType.INSIGHT, Operation.READ))
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Search documents
        augmentor = get_context_augmentor()
        results, _ = await augmentor.augment_prompt(
            prompt=query.query,
            max_context_length=10000,  # Large limit for search
            similarity_threshold=query.similarity_threshold or 10.0,
            max_contexts=query.limit or 5
        )
        
        # Format results
        search_results = []
        for doc, score in results:
            search_results.append({
                "doc_id": doc.doc_id,
                "metadata": doc.metadata,
                "text_preview": doc.text[:200] + "..." if len(doc.text) > 200 else doc.text,
                "relevance_score": score
            })
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/knowledge/search", 200, processing_time, current_user.id,
            extra={"query": query.query, "results_count": len(search_results)}
        )
        
        return search_results
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/knowledge/search", 500, processing_time, 
            current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))