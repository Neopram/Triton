import time
from typing import Dict, Any, List, Optional, Tuple
import asyncio

from app.core.logging import ai_logger
from app.services.semantic_search.faiss_engine import get_index, SemanticDocument

class ContextAugmentor:
    """Service for augmenting AI prompts with relevant context."""
    
    def __init__(self):
        self.index = get_index()
    
    async def augment_prompt(
        self, 
        prompt: str, 
        max_context_length: int = 1500,
        similarity_threshold: float = 5.0,
        max_contexts: int = 3
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Augment a prompt with relevant context from the knowledge base.
        
        Args:
            prompt: Original prompt
            max_context_length: Maximum length of context to add
            similarity_threshold: Maximum distance to consider a document relevant
            max_contexts: Maximum number of context documents to include
            
        Returns:
            Tuple of (augmented prompt, list of context metadata)
        """
        start_time = time.time()
        ai_logger.info(f"Augmenting prompt: {prompt[:100]}...")
        
        try:
            # Search for relevant documents
            results = await self.index.search(prompt, top_k=max_contexts * 2)
            
            # Filter by similarity threshold and sort by relevance
            filtered_results = [(doc, score) for doc, score in results if score < similarity_threshold]
            filtered_results.sort(key=lambda x: x[1])  # Sort by score (lower is better)
            
            # Take top results
            top_results = filtered_results[:max_contexts]
            
            if not top_results:
                ai_logger.info(f"No relevant context found for prompt")
                return prompt, []
            
            # Prepare context
            context_blocks = []
            context_metadata = []
            
            total_length = 0
            for doc, score in top_results:
                # Skip if adding this would exceed max length
                if total_length + len(doc.text) > max_context_length:
                    continue
                
                context_blocks.append(doc.text)
                context_metadata.append({
                    "doc_id": doc.doc_id,
                    "metadata": doc.metadata,
                    "relevance_score": score
                })
                total_length += len(doc.text)
            
            # Combine context with prompt
            if context_blocks:
                context_text = "\n\n".join(context_blocks)
                augmented_prompt = f"""I'll provide some context information that may be relevant to the question.

CONTEXT:
{context_text}

QUESTION:
{prompt}

Based on the context provided (if relevant) and your knowledge, please answer the question."""
            else:
                augmented_prompt = prompt
            
            processing_time = time.time() - start_time
            ai_logger.info(
                f"Prompt augmented with {len(context_blocks)} context blocks",
                extra={
                    "contexts_found": len(context_blocks),
                    "total_context_length": total_length,
                    "processing_time_ms": round(processing_time * 1000, 2)
                }
            )
            
            return augmented_prompt, context_metadata
        
        except Exception as e:
            ai_logger.error(f"Error augmenting prompt: {str(e)}")
            return prompt, []  # Return original prompt on error
    
    async def add_document(
        self, 
        text: str, 
        metadata: Dict[str, Any], 
        doc_id: Optional[str] = None
    ) -> bool:
        """
        Add a document to the knowledge base.
        
        Args:
            text: Document text
            metadata: Document metadata
            doc_id: Optional document ID
            
        Returns:
            Success status
        """
        if not doc_id:
            # Generate ID from timestamp and hash
            doc_id = f"doc_{int(time.time())}_{hash(text) % 10000:04d}"
        
        # Create document
        doc = SemanticDocument(
            doc_id=doc_id,
            text=text,
            metadata=metadata
        )
        
        # Add to index
        return await self.index.add_document(doc)
    
    async def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        """
        Add multiple documents to the knowledge base.
        
        Args:
            documents: List of document dictionaries
                Each with 'text', 'metadata', and optional 'doc_id'
            
        Returns:
            Number of documents successfully added
        """
        # Convert to SemanticDocument objects
        docs = []
        for doc in documents:
            doc_id = doc.get("doc_id")
            if not doc_id:
                doc_id = f"doc_{int(time.time())}_{hash(doc['text']) % 10000:04d}"
            
            docs.append(SemanticDocument(
                doc_id=doc_id,
                text=doc["text"],
                metadata=doc["metadata"]
            ))
        
        # Add to index
        return await self.index.add_documents(docs)
    
    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the knowledge base.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Success status
        """
        return self.index.delete_document(doc_id)

# Singleton instance
_augmentor_instance = None

def get_context_augmentor() -> ContextAugmentor:
    """Get singleton instance of context augmentor."""
    global _augmentor_instance
    if _augmentor_instance is None:
        _augmentor_instance = ContextAugmentor()
    return _augmentor_instance