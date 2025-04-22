from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class MarketInsightRecord(Base):
    __tablename__ = "market_insights"

    id = Column(Integer, primary_key=True, index=True)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="market_insights")
    
    # Original content and results
    content = Column(Text, nullable=False)  # Original analyzed content
    insights = Column(Text, nullable=False)  # AI-generated insights
    
    # Analysis metadata
    engine_used = Column(String(50), default="phi3")  # AI engine used
    prompt = Column(Text, nullable=True)  # Prompt used for generation
    
    # User feedback (for future phases)
    rating = Column(Float, nullable=True)  # Rating from 1-5
    feedback = Column(Text, nullable=True)  # Comments on quality
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<MarketInsight id={self.id} engine={self.engine_used}>"