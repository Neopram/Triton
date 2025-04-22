from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class ModelType(str, Enum):
    """Types of models that can be deployed"""
    BASE = "base"
    LORA = "lora"
    QLORA = "qlora"
    GGUF = "gguf"


class TrainingJobStatus(str, Enum):
    """Status of a training job"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingDataset(Base):
    """Database model for training datasets"""
    __tablename__ = "training_datasets"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    format = Column(String, nullable=False, default="instruct")  # instruct, chat, raw
    sample_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    creator = relationship("User", back_populates="datasets")
    jobs = relationship("TrainingJob", back_populates="dataset")
    
    # Metadata
    metadata = Column(JSON, nullable=True)


class TrainingJob(Base):
    """Database model for training jobs"""
    __tablename__ = "training_jobs"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    dataset_id = Column(String, ForeignKey("training_datasets.id"), nullable=False)
    base_model = Column(String, nullable=False)
    
    # LoRA configuration
    lora_config = Column(JSON, nullable=False)
    
    # Job status and timing
    status = Column(String, nullable=False, default=TrainingJobStatus.PENDING.value)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    
    # Performance metrics
    metrics = Column(JSON, nullable=True)
    
    # Error information
    error_message = Column(String, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    dataset = relationship("TrainingDataset", back_populates="jobs")
    creator = relationship("User", back_populates="training_jobs")
    deployed_model = relationship("DeployedModel", back_populates="training_job", uselist=False)


class DeployedModel(Base):
    """Database model for deployed models"""
    __tablename__ = "deployed_models"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    # Model information
    base_model = Column(String, nullable=False)
    model_type = Column(String, nullable=False, default=ModelType.LORA.value)
    
    # Original training job if applicable
    training_job_id = Column(String, ForeignKey("training_jobs.id"), nullable=True)
    
    # Deployment status
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    
    # Deployment metrics
    inference_count = Column(Integer, nullable=False, default=0)
    average_latency_ms = Column(Integer, nullable=True)
    
    # Audit fields
    deployed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    deployed_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    training_job = relationship("TrainingJob", back_populates="deployed_model")
    deployer = relationship("User", back_populates="deployed_models")
    
    # Configuration and performance metrics
    metrics = Column(JSON, nullable=True)
    config = Column(JSON, nullable=True)


class ModelEvaluation(Base):
    """Database model for model evaluations"""
    __tablename__ = "model_evaluations"

    id = Column(String, primary_key=True, index=True)
    model_id = Column(String, ForeignKey("deployed_models.id"), nullable=False)
    
    # Evaluation metrics
    metrics = Column(JSON, nullable=False)
    
    # Test set information
    test_set_name = Column(String, nullable=True)
    test_set_size = Column(Integer, nullable=True)
    
    # Audit fields
    evaluated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    evaluated_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    model = relationship("DeployedModel")
    evaluator = relationship("User")


# Add relationship references to User model
from app.models.user import User
User.datasets = relationship("TrainingDataset", back_populates="creator")
User.training_jobs = relationship("TrainingJob", back_populates="creator")
User.deployed_models = relationship("DeployedModel", back_populates="deployer")