import pytest
from unittest.mock import patch
from app.services.ai_engine import query_ai_engine


@pytest.mark.asyncio
async def test_ai_engine_phi3():
    with patch('app.services.phi3_engine.query_phi3', return_value="Test insight from phi3"):
        result = await query_ai_engine("Test prompt", engine="phi3")
        assert result == "Test insight from phi3"


@pytest.mark.asyncio
async def test_ai_engine_deepseek():
    with patch('app.services.deepseek_engine.query_deepseek', return_value="Test insight from deepseek"):
        result = await query_ai_engine("Test prompt", engine="deepseek")
        assert result == "Test insight from deepseek"


@pytest.mark.asyncio
async def test_ai_engine_with_context():
    with patch('app.services.phi3_engine.query_phi3') as mock_phi3:
        await query_ai_engine("Test prompt", context="Additional context")
        
        # Verify that the prompt includes the context
        args, _ = mock_phi3.call_args
        assert "Additional context" in args[0]
        assert "Test prompt" in args[0]