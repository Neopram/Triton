from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table, func
from sqlalchemy.orm import relationship
from app.core.database import Base

# Association table for message reactions
message_reactions = Table(
    "message_reactions",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("message_id", Integer, ForeignKey("messages.id"), primary_key=True),
    Column("emoji", String(10), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    message = relationship("Message", back_populates="attachments")

    def __repr__(self):
        return f"<MessageAttachment id={self.id} file={self.file_name}>"

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    
    # Sender and receiver
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Content and status
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_messages")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")
    reactions = relationship(
        "User",
        secondary=message_reactions,
        backref="message_reactions"
    )
    
    def __repr__(self):
        return f"<Message id={self.id} from={self.sender_id} to={self.recipient_id}>"