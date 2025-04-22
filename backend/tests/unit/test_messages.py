import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.message import Message, MessageAttachment
from app.services.file_storage import save_message_attachment
from app.core.utils.emoji import is_valid_emoji, extract_emojis_from_text, count_reactions


def test_emoji_validation():
    assert is_valid_emoji("👍") == True
    assert is_valid_emoji("hello") == False
    assert is_valid_emoji("hello 👍") == True


def test_extract_emojis():
    assert extract_emojis_from_text("Hello 👍 world 🚢!") == ["👍", "🚢"]
    assert extract_emojis_from_text("No emojis here") == []


def test_count_reactions():
    reactions = [("👍", 1), ("👍", 2), ("❤️", 3), ("👍", 4)]
    counts = count_reactions(reactions)
    
    assert counts["👍"] == 3
    assert counts["❤️"] == 1


@pytest.mark.asyncio
async def test_save_attachment():
    # Mock file
    mock_file = MagicMock()
    mock_file.filename = "test.txt"
    mock_file.content_type = "text/plain"
    mock_file.file.tell.return_value = 1024  # 1KB
    
    with patch("os.makedirs"), patch("builtins.open"), patch("shutil.copyfileobj"), patch("uuid.uuid4", return_value="test-uuid"):
        result = await save_message_attachment(mock_file, 1)
        
        assert result["file_name"] == "test.txt"
        assert "test-uuid" in result["file_path"]
        assert result["file_size"] == 1024
        assert result["mime_type"] == "text/plain"

# More tests would be added for message crud operations