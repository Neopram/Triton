from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime
import re


# ─────────────────────────────────────────────
# 📥 Base Message Schema
# ─────────────────────────────────────────────
class MessageBase(BaseModel):
    content: str = Field(..., example="Hello! When will the cargo arrive?")


# ─────────────────────────────────────────────
# 📤 Message Create Schema
# ─────────────────────────────────────────────
class MessageCreate(MessageBase):
    recipient_id: int = Field(..., example=42)


# ─────────────────────────────────────────────
# 📎 Attachment Schema
# ─────────────────────────────────────────────
class AttachmentOut(BaseModel):
    id: int
    file_name: str
    file_size: int
    mime_type: str
    created_at: datetime

    class Config:
        orm_mode = True


# ─────────────────────────────────────────────
# 👍 Reaction Schema
# ─────────────────────────────────────────────
class ReactionCreate(BaseModel):
    emoji: str = Field(..., example="👍")
    
    @validator('emoji')
    def validate_emoji(cls, v):
        # Simple emoji validation (could be more sophisticated)
        emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u2B55]')
        if not emoji_pattern.search(v):
            raise ValueError('Invalid emoji format')
        return v


# ─────────────────────────────────────────────
# 👥 User Minimal Info
# ─────────────────────────────────────────────
class UserInfo(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        orm_mode = True


# ─────────────────────────────────────────────
# 📤 Message Output Schema
# ─────────────────────────────────────────────
class MessageOut(MessageBase):
    id: int
    sender_id: int
    recipient_id: int
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None
    sender: Optional[UserInfo] = None
    recipient: Optional[UserInfo] = None
    attachments: List[AttachmentOut] = []
    reactions: Dict[str, int] = Field(default_factory=dict)  # emoji -> count

    class Config:
        orm_mode = True


# ─────────────────────────────────────────────
# 📤 Message List Schema (simplified)
# ─────────────────────────────────────────────
class MessageListItem(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    content: str
    is_read: bool
    created_at: datetime
    sender_name: Optional[str] = None
    has_attachments: bool

    class Config:
        orm_mode = True