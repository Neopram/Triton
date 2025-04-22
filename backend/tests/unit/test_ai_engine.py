import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.services.ai_engine import (
    query_ai_engine,
    get_available_engines,
    register_ai_engine,
    get_current_ai_engine
)

# Test registry and decorator
def test_engine_registry():
    # Register a test engine
    @register_ai_engine("test_engine")
    def get_test_engine():
        return lambda x: "Test response"
    
    # Check if it's in available engines
    engines = get_available_engines()
    assert "test_engine" in engines
    assert "phi3" in engines
    assert "deepseek" in engines

# Test query with default engine
@pytest.mark.asyncio
async def test_query_default_engine():
    with patch("app.services.phi3_engine.query_phi3", return_value="Test response"):
        with patch("app.core.config.settings.AI_ENGINE", "phi3"):
            response = await query_ai_engine("Test prompt")
            assert response == "Test response"

# Test query with specified engine
@pytest.mark.asyncio
async def test_query_specific_engine():
    with patch("app.services.deepseek_engine.query_deepseek", return_value="DeepSeek response"):
        response = await query_ai_engine("Test prompt", engine="deepseek")
        assert response == "DeepSeek response"

# Test query with context
@pytest.mark.asyncio
async def test_query_with_context():
    test_prompt = "Test prompt"
    test_context = "This is some context"
    
    with patch("app.services.phi3_engine.query_phi3") as mock_phi3:
        mock_phi3.return_value = "Response with context"
        
        response = await query_ai_engine(test_prompt, context=test_context)
        
        # Check that context was included in the prompt
        call_args = mock_phi3.call_args[0][0]
        assert test_context in call_args
        assert test_prompt in call_args
        assert response == "Response with context"

# Test error handling for unknown engine
@pytest.mark.asyncio
async def test_unknown_engine():
    with pytest.raises(HTTPException) as excinfo:
        await query_ai_engine("Test prompt", engine="unknown_engine")
    
    assert excinfo.value.status_code == 400
    assert "Unknown AI engine" in excinfo.value.detail

# Test get_current_ai_engine
@pytest.mark.asyncio
async def test_get_current_engine():
    with patch("app.core.config.settings.AI_ENGINE", "phi3"):
        info = await get_current_ai_engine()
        assert info["current_engine"] == "phi3"
        assert "phi3" in info["available_engines"]
        assert info["is_valid"] is True