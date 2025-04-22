import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
from fastapi import UploadFile, HTTPException, BackgroundTasks
import tempfile
import os
import io
import re
import docx2txt
from typing import Dict, List, Optional, Tuple, Union
import uuid
from datetime import datetime

from app.core.logging import api_logger
from app.core.config import settings
from app.services.semantic_search.faiss_engine import FaissSearchEngine
from app.services.file_storage import save_file_to_storage
from app.models.ocr import OCRDocument

# Supported file formats
SUPPORTED_IMAGE_FORMATS = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/tiff"]
SUPPORTED_PDF_FORMAT = "application/pdf"
SUPPORTED_DOCUMENT_FORMATS = ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]

# OCR configuration
OCR_CONFIG = {
    'language': 'eng',  # Default language
    'config': '--psm 3 --oem 3',  # Page segmentation mode 3 (auto) and OCR Engine mode 3 (default)
    'dpi': 300,  # DPI for PDF conversion
    'quality': 100  # Quality for image processing
}

# Maritime-specific corrections
MARITIME_TERMS_CORRECTIONS = {
    # Common OCR mistakes for maritime terms
    "vcssel": "vessel",
    "vessol": "vessel",
    "contalner": "container",
    "shlp": "ship",
    "charlerer": "charterer",
    "frelght": "freight",
    "lading": "lading",
    "demurrage": "demurrage",
    "ballast": "ballast"
}

class OCRProcessor:
    def __init__(self):
        self.search_engine = None
        self.initialize_search_engine()
    
    def initialize_search_engine(self):
        """Initialize the search engine for document indexing."""
        try:
            # Use the same FAISS engine we set up for RAG
            self.search_engine = FaissSearchEngine()
            api_logger.info("OCR search engine initialized successfully")
        except Exception as e:
            api_logger.error(f"Failed to initialize OCR search engine: {str(e)}")
            self.search_engine = None
    
    async def extract_text_from_file(self, file: UploadFile, background_tasks: BackgroundTasks = None) -> Dict[str, Union[str, Dict]]:
        """
        Extract text content from uploaded file using OCR.

        Args:
            file: UploadFile object (image, PDF, or document)
            background_tasks: Optional BackgroundTasks for async indexing

        Returns:
            Dict containing extracted text and metadata
        """
        document_id = str(uuid.uuid4())
        original_filename = file.filename
        extraction_start = datetime.utcnow()
        
        try:
            # Determine extraction method based on file type
            if file.content_type in SUPPORTED_IMAGE_FORMATS:
                text, metadata = await self._extract_from_image(file)
            elif file.content_type == SUPPORTED_PDF_FORMAT:
                text, metadata = await self._extract_from_pdf(file)
            elif file.content_type in SUPPORTED_DOCUMENT_FORMATS:
                text, metadata = await self._extract_from_document(file)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file.content_type}")
            
            # Apply maritime-specific post-processing
            processed_text = self._post_process_text(text)
            
            # Save file to storage if enabled
            if settings.STORE_OCR_FILES:
                file_path = await save_file_to_storage(file, folder="ocr_documents")
                metadata["file_path"] = file_path
            
            # Prepare result with metadata
            result = {
                "document_id": document_id,
                "original_filename": original_filename,
                "text": processed_text,
                "extraction_time": (datetime.utcnow() - extraction_start).total_seconds(),
                "metadata": metadata,
                "word_count": len(processed_text.split())
            }
            
            # Index document for RAG if search engine is available and background tasks provided
            if self.search_engine and background_tasks:
                # Create OCR document record
                document = OCRDocument(
                    id=document_id,
                    filename=original_filename,
                    content_type=file.content_type,
                    text_content=processed_text[:5000],  # Store preview in DB
                    word_count=result["word_count"],
                    metadata=metadata
                )
                
                # Add to background tasks
                background_tasks.add_task(
                    self._index_document_async,
                    document_id,
                    processed_text,
                    original_filename,
                    metadata
                )
                
                # Add indexing status to result
                result["indexing_status"] = "queued"
            
            return result
            
        except Exception as e:
            api_logger.error(f"OCR extraction failed for {original_filename}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"OCR extraction failed: {str(e)}")
    
    async def _extract_from_image(self, file: UploadFile) -> Tuple[str, Dict]:
        """Extract text from image files using pytesseract with enhanced processing."""
        contents = await file.read()
        try:
            image = Image.open(io.BytesIO(contents))
            
            # Get image metadata
            metadata = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "pages": 1
            }
            
            # Enhance image quality for better OCR
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Apply OCR with custom configuration
            text = pytesseract.image_to_string(
                image, 
                lang=OCR_CONFIG['language'],
                config=OCR_CONFIG['config']
            )
            
            return text.strip(), metadata
        except Exception as e:
            raise RuntimeError(f"Failed to process image: {str(e)}")
    
    async def _extract_from_pdf(self, file: UploadFile) -> Tuple[str, Dict]:
        """Extract text from PDF files with enhanced processing."""
        contents = await file.read()
        text_result = []
        
        try:
            with tempfile.TemporaryDirectory() as path:
                # Convert PDF to images with high quality settings
                images = convert_from_bytes(
                    contents, 
                    output_folder=path,
                    dpi=OCR_CONFIG['dpi'],
                    fmt="jpeg",
                    grayscale=False,
                    thread_count=2  # Use parallel processing
                )
                
                # Create metadata
                metadata = {
                    "pages": len(images),
                    "format": "PDF"
                }
                
                # Process each page
                for i, img in enumerate(images):
                    # Apply OCR with custom configuration
                    page_text = pytesseract.image_to_string(
                        img, 
                        lang=OCR_CONFIG['language'],
                        config=OCR_CONFIG['config']
                    )
                    
                    # Add page number metadata
                    text_result.append(f"[Page {i+1}]\n{page_text}")
                
            return "\n\n".join(text_result).strip(), metadata
            
        except Exception as e:
            raise RuntimeError(f"Failed to process PDF: {str(e)}")
    
    async def _extract_from_document(self, file: UploadFile) -> Tuple[str, Dict]:
        """Extract text from Word documents."""
        contents = await file.read()
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
                temp_file.write(contents)
                temp_path = temp_file.name
            
            # Extract text from docx
            text = docx2txt.process(temp_path)
            
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            
            # Create metadata
            metadata = {
                "format": "DOCX",
                "pages": text.count('\f') + 1  # Approximate page count based on form feeds
            }
            
            return text.strip(), metadata
            
        except Exception as e:
            raise RuntimeError(f"Failed to process document: {str(e)}")
    
    def _post_process_text(self, text: str) -> str:
        """Apply maritime-specific post-processing to improve OCR results."""
        # Apply common maritime term corrections
        for error, correction in MARITIME_TERMS_CORRECTIONS.items():
            text = re.sub(r'\b' + re.escape(error) + r'\b', correction, text, flags=re.IGNORECASE)
        
        # Fix common OCR issues
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix line breaks in paragraphs vs. actual paragraph breaks
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Clean up any remaining artifacts
        text = text.replace('|', 'I').replace('0', 'O')
        
        return text.strip()
    
    async def _index_document_async(self, document_id: str, text: str, filename: str, metadata: Dict):
        """Index the document in the search engine for RAG."""
        try:
            if self.search_engine:
                # Chunk the document for better retrieval
                chunks = self._chunk_document(text)
                
                # Index each chunk
                for i, chunk in enumerate(chunks):
                    self.search_engine.add_document(
                        doc_id=f"{document_id}_{i}",
                        text=chunk,
                        metadata={
                            "document_id": document_id,
                            "filename": filename,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            **metadata
                        }
                    )
                
                # Commit changes
                self.search_engine.commit()
                api_logger.info(f"Successfully indexed OCR document {document_id} with {len(chunks)} chunks")
                
                # Update document status in database if needed
                # This would be implemented with your DB access code
                
        except Exception as e:
            api_logger.error(f"Failed to index OCR document {document_id}: {str(e)}")
    
    def _chunk_document(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split document into overlapping chunks for better retrieval."""
        chunks = []
        
        # If text is shorter than chunk_size, return as is
        if len(text) <= chunk_size:
            return [text]
        
        # Split text into paragraphs
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            # If adding this paragraph exceeds chunk size, save current chunk and start new one
            if len(current_chunk) + len(para) > chunk_size:
                chunks.append(current_chunk.strip())
                # Keep overlap from end of previous chunk
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else ""
                current_chunk = overlap_text + para + "\n\n"
            else:
                current_chunk += para + "\n\n"
        
        # Add the last chunk if it's not empty
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def search_ocr_documents(self, query: str, limit: int = 5) -> List[Dict]:
        """Search indexed OCR documents using semantic search."""
        if not self.search_engine:
            raise HTTPException(status_code=500, detail="Search engine not initialized")
        
        try:
            results = self.search_engine.search(query, limit=limit)
            return results
        except Exception as e:
            api_logger.error(f"OCR document search failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Document search failed: {str(e)}")

# Create singleton instance
ocr_processor = OCRProcessor()

# Main function to be called from API endpoints
async def extract_text_from_file(file: UploadFile, background_tasks: Optional[BackgroundTasks] = None) -> Dict:
    """
    Public interface for OCR text extraction with optional RAG integration.
    
    Args:
        file: UploadFile object (image, PDF, or document)
        background_tasks: Optional BackgroundTasks for async RAG indexing
        
    Returns:
        Dict containing extracted text and metadata
    """
    return await ocr_processor.extract_text_from_file(file, background_tasks)

# Search function for RAG integration
async def search_ocr_documents(query: str, limit: int = 5) -> List[Dict]:
    """
    Search OCR-processed documents using semantic search.
    
    Args:
        query: Search query
        limit: Maximum number of results to return
        
    Returns:
        List of document chunks matching the query
    """
    return await ocr_processor.search_ocr_documents(query, limit)