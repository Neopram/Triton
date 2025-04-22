import os
import numpy as np
import faiss
import pickle
import json
from typing import List, Dict, Any, Optional, Tuple
import torch
from transformers import AutoTokenizer, AutoModel
import asyncio
import time
from pathlib import Path

from app.core.config import settings
from app.core.logging import ai_logger

# Default paths
EMBEDDINGS_DIR = os.path.join(settings.FILE_STORAGE_PATH, "embeddings")
DOCUMENTS_PATH = os.path.join(EMBEDDINGS_DIR, "documents.json")
INDEX_PATH = os.path.join(EMBEDDINGS_DIR, "faiss_index.bin")

# Ensure directories exist
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

# Sentence transformer model for embeddings
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# Initialize tokenizer and model
tokenizer = None
model = None

def _load_model():
    """Load the model and tokenizer for embeddings."""
    global tokenizer, model
    if tokenizer is None or model is None:
        ai_logger.info(f"Loading embedding model: {MODEL_NAME}")
        try:
            tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            model = AutoModel.from_pretrained(MODEL_NAME)
            if torch.cuda.is_available():
                model = model.cuda()
            model.eval()
            ai_logger.info(f"Model loaded successfully")
        except Exception as e:
            ai_logger.error(f"Error loading model: {str(e)}")
            raise

# Mean Pooling function to get sentence embeddings
def _mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

async def get_embedding(text: str) -> np.ndarray:
    """
    Get embedding vector for a text string.
    
    Args:
        text: Text to embed
        
    Returns:
        numpy array with embedding vector
    """
    # Ensure model is loaded
    if tokenizer is None or model is None:
        _load_model()
    
    # Tokenize and get embedding
    encoded_input = tokenizer(text, padding=True, truncation=True, max_length=512, return_tensors='pt')
    if torch.cuda.is_available():
        encoded_input = {k: v.cuda() for k, v in encoded_input.items()}
    
    with torch.no_grad():
        model_output = model(**encoded_input)
    
    # Mean pooling
    embeddings = _mean_pooling(model_output, encoded_input['attention_mask'])
    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
    
    # Convert to numpy and return
    return embeddings[0].cpu().numpy()

class SemanticDocument:
    """Class representing a document with its embedding."""
    
    def __init__(self, doc_id: str, text: str, metadata: Dict[str, Any], embedding: Optional[np.ndarray] = None):
        self.doc_id = doc_id
        self.text = text
        self.metadata = metadata
        self.embedding = embedding
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without embedding)."""
        return {
            "doc_id": self.doc_id,
            "text": self.text,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], embedding: Optional[np.ndarray] = None) -> 'SemanticDocument':
        """Create from dictionary."""
        return cls(
            doc_id=data["doc_id"],
            text=data["text"],
            metadata=data["metadata"],
            embedding=embedding
        )

class FAISSIndex:
    """FAISS index for semantic search."""
    
    def __init__(self):
        self.index = None
        self.documents = {}
        self.embedding_size = 384  # Size for the model we're using
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize the FAISS index."""
        try:
            # Try to load existing index and documents
            if os.path.exists(INDEX_PATH) and os.path.exists(DOCUMENTS_PATH):
                self.index = faiss.read_index(INDEX_PATH)
                with open(DOCUMENTS_PATH, 'r') as f:
                    self.documents = {doc["doc_id"]: SemanticDocument.from_dict(doc) 
                                     for doc in json.load(f)}
                ai_logger.info(f"Loaded existing index with {len(self.documents)} documents")
            else:
                # Create new index
                self.index = faiss.IndexFlatL2(self.embedding_size)
                ai_logger.info("Created new FAISS index")
        except Exception as e:
            ai_logger.error(f"Error initializing FAISS index: {str(e)}")
            # Create new index as fallback
            self.index = faiss.IndexFlatL2(self.embedding_size)
            self.documents = {}
    
    async def add_document(self, doc: SemanticDocument) -> bool:
        """
        Add a document to the index.
        
        Args:
            doc: Document to add
            
        Returns:
            Success status
        """
        try:
            # Get embedding if not provided
            if doc.embedding is None:
                doc.embedding = await get_embedding(doc.text)
            
            # Add to index
            self.index.add(np.array([doc.embedding], dtype=np.float32))
            
            # Store document without embedding
            self.documents[doc.doc_id] = doc
            
            # Save index and documents
            self._save_index()
            return True
        except Exception as e:
            ai_logger.error(f"Error adding document to index: {str(e)}")
            return False
    
    async def add_documents(self, docs: List[SemanticDocument]) -> int:
        """
        Add multiple documents to the index.
        
        Args:
            docs: List of documents to add
            
        Returns:
            Number of documents successfully added
        """
        count = 0
        embeddings = []
        
        # Process in batches
        for doc in docs:
            try:
                # Get embedding if not provided
                if doc.embedding is None:
                    doc.embedding = await get_embedding(doc.text)
                
                embeddings.append(doc.embedding)
                self.documents[doc.doc_id] = doc
                count += 1
            except Exception as e:
                ai_logger.error(f"Error processing document {doc.doc_id}: {str(e)}")
        
        if embeddings:
            # Add all embeddings to index
            self.index.add(np.array(embeddings, dtype=np.float32))
            
            # Save index and documents
            self._save_index()
        
        return count
    
    async def search(self, query: str, top_k: int = 5) -> List[Tuple[SemanticDocument, float]]:
        """
        Search for similar documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of (document, score) tuples
        """
        if len(self.documents) == 0:
            return []
        
        try:
            # Get query embedding
            query_embedding = await get_embedding(query)
            
            # Search index
            query_embedding = np.array([query_embedding], dtype=np.float32)
            distances, indices = self.index.search(query_embedding, min(top_k, len(self.documents)))
            
            # Get results
            results = []
            for i, idx in enumerate(indices[0]):
                if idx != -1:  # Valid index
                    # Get doc_id by position
                    doc_id = list(self.documents.keys())[idx]
                    doc = self.documents[doc_id]
                    results.append((doc, float(distances[0][i])))
            
            return results
        except Exception as e:
            ai_logger.error(f"Error searching index: {str(e)}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the index.
        
        Note: FAISS doesn't support direct deletion, so we need to rebuild the index
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            Success status
        """
        if doc_id not in self.documents:
            return False
        
        try:
            # Remove from documents
            del self.documents[doc_id]
            
            # Rebuild index
            self._rebuild_index()
            return True
        except Exception as e:
            ai_logger.error(f"Error deleting document: {str(e)}")
            return False
    
    def _rebuild_index(self):
        """Rebuild the FAISS index from documents."""
        # Create new index
        self.index = faiss.IndexFlatL2(self.embedding_size)
        
        # Add all embeddings
        embeddings = []
        for doc_id, doc in self.documents.items():
            if doc.embedding is not None:
                embeddings.append(doc.embedding)
        
        if embeddings:
            self.index.add(np.array(embeddings, dtype=np.float32))
        
        # Save index and documents
        self._save_index()
    
    def _save_index(self):
        """Save the index and documents to disk."""
        try:
            # Save index
            faiss.write_index(self.index, INDEX_PATH)
            
            # Save documents (without embeddings)
            with open(DOCUMENTS_PATH, 'w') as f:
                json.dump([doc.to_dict() for doc in self.documents.values()], f)
        except Exception as e:
            ai_logger.error(f"Error saving index: {str(e)}")

# Singleton instance
_index_instance = None

def get_index() -> FAISSIndex:
    """Get singleton instance of FAISS index."""
    global _index_instance
    if _index_instance is None:
        _index_instance = FAISSIndex()
    return _index_instance