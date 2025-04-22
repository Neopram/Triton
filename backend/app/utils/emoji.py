import re
from typing import List, Dict, Optional, Tuple

# Common emoji categories
COMMON_EMOJIS = {
    "positive": ["👍", "❤️", "👏", "🎉", "🙏", "😊"],
    "neutral": ["👀", "🤔", "😐", "⚓"],
    "negative": ["👎", "😢", "😡", "🚫"]
}

def is_valid_emoji(text: str) -> bool:
    """
    Check if a string is a valid emoji.
    Very simple check, can be improved with more robust regex.
    
    Args:
        text: String to check
        
    Returns:
        bool: True if the string is a valid emoji
    """
    # This regex is simplified and not exhaustive
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u2B55]')
    return bool(emoji_pattern.search(text))

def get_emoji_suggestions(category: Optional[str] = None) -> List[str]:
    """
    Get a list of suggested emojis, optionally filtered by category.
    
    Args:
        category: Optional category filter (positive, neutral, negative)
        
    Returns:
        List[str]: List of suggested emojis
    """
    if category and category in COMMON_EMOJIS:
        return COMMON_EMOJIS[category]
    
    # Return all emojis if no category specified
    all_emojis = []
    for emojis in COMMON_EMOJIS.values():
        all_emojis.extend(emojis)
    return all_emojis

def extract_emojis_from_text(text: str) -> List[str]:
    """
    Extract all emojis from a text string.
    
    Args:
        text: Text string to extract emojis from
        
    Returns:
        List[str]: List of emojis found in the text
    """
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u2B55]')
    return emoji_pattern.findall(text)

def count_reactions(reactions: List[Tuple[str, int]]) -> Dict[str, int]:
    """
    Count reactions by emoji.
    
    Args:
        reactions: List of (emoji, user_id) tuples
        
    Returns:
        Dict[str, int]: Dictionary mapping emoji to count
    """
    counts = {}
    for emoji, _ in reactions:
        counts[emoji] = counts.get(emoji, 0) + 1
    return counts