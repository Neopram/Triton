import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from app.services.semantic_search.faiss_engine import SemanticDocument, get_embedding
from app.services.context_augmentor import ContextAugmentor

# Sample documents for testing
SAMPLE_DOCS = [
    {
        "doc_id": "doc1",
        "text": "The Baltic Dry Index (BDI) is a shipping and trade index created by the London-based Baltic Exchange. It measures changes in the cost of transporting various raw materials, such as coal and steel.",
        "metadata": {"category": "shipping_indices", "year": 2023}
    },
    {
        "doc_id": "doc2",
        "text": "An Aframax is a medium-sized crude tanker with a dead weight tonnage (DWT) between 80,000 and 119,999. The Aframax tanker is the largest tanker size in the AFRA (Average Freight Rate Assessment) tanker rate system.",
        "metadata": {"category": "vessel_types", "year": 2023}
    }
]

@pytest.mark.asyncio
async def test_get_embedding():
    # Mock the embedding function
    with patch('app.services.semantic_search.faiss_engine._mean_pooling', return_value=torch.ones(1, 384)):
        with patch('app.services.semantic_search.faiss_engine.tokenizer') as mock_tokenizer:
            with patch('app.services.semantic_search.faiss_engine.model') as mock_model:
                # Set up mocks
                mock_tokenizer.return_value = {"input_ids": torch.ones(1, 10), "attention_mask": torch.ones(1, 10)}
                mock_model.return_value = [torch.ones(1, 10, 384)]
                
                # Get embedding
                embedding = await get_embedding("test text")
                
                # Check shape
                assert embedding.shape == (384,)
                assert isinstance(embedding, np.ndarray)

@pytest.mark.asyncio
async def test_context_augmentor():
    # Create a mock FAISSIndex
    mock_index = MagicMock()
    mock_index.search.return_value = [
        (SemanticDocument(
            doc_id=SAMPLE_DOCS[0]["doc_id"],
            text=SAMPLE_DOCS[0]["text"],
            metadata=SAMPLE_DOCS[0]["metadata"]
        ), 1.5),
        (SemanticDocument(
            doc_id=SAMPLE_DOCS[1]["doc_id"],
            text=SAMPLE_DOCS[1]["text"],
            metadata=SAMPLE_DOCS[1]["metadata"]
        ), 2.5)
    ]
    
    # Create augmentor with mock index
    augmentor = ContextAugmentor()
    augmentor.index = mock_index
    
    # Test augmentation
    prompt = "What is the Baltic Dry Index?"
    augmented_prompt, context_metadata = await augmentor.augment_prompt(prompt)
    
    # Check that prompt is augmented
    assert "CONTEXT:" in augmented_prompt
    assert "The Baltic Dry Index (BDI)" in augmented_prompt
    assert prompt in augmented_prompt
    
    # Check metadata
    assert len(context_metadata) == 2
    assert context_metadata[0]["doc_id"] == "doc1"
    assert context_metadata[0]["relevance_score"] == 1.5
    
@pytest.mark.asyncio
async def test_augmentor_with_empty_results():
    # Create a mock FAISSIndex that returns empty results
    mock_index = MagicMock()
    mock_index.search.return_value = []
    
    # Create augmentor with mock index
    augmentor = ContextAugmentor()
    augmentor.index = mock_index
    
    # Test augmentation
    prompt = "What is something not in our knowledge base?"
    augmented_prompt, context_metadata = await augmentor.augment_prompt(prompt)
    
    # Check that prompt is unchanged
    assert augmented_prompt == prompt
    assert len(context_metadata) == 0

@pytest.mark.asyncio
async def test_add_document():
    # Create a mock FAISSIndex
    mock_index = MagicMock()
    mock_index.add_document.return_value = True
    
    # Create augmentor with mock index
    augmentor = ContextAugmentor()
    augmentor.index = mock_index
    
    # Test adding document
    result = await augmentor.add_document(
        text="Test document",
        metadata={"category": "test"},
        doc_id="test_doc"
    )
    
    # Check result
    assert result is True
    mock_index.add_document.assert_called_once()
    
    # Get the document that was passed to add_document
    doc = mock_index.add_document.call_args[0][0]
    assert doc.doc_id == "test_doc"
    assert doc.text == "Test document"
    assert doc.metadata["category"] == "test"