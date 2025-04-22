from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator

# Enums
class TrainingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DatasetFormat(str, Enum):
    INSTRUCT = "instruct"
    CHAT = "chat"
    RAW = "raw"


# Base schemas
class LoraModelConfig(BaseModel):
    """Configuration for LoRA fine-tuning"""
    lora_r: int = Field(8, description="LoRA attention dimension")
    lora_alpha: int = Field(16, description="LoRA alpha")
    lora_dropout: float = Field(0.05, description="LoRA dropout")
    
    # Training parameters
    learning_rate: float = Field(3e-4, description="Learning rate")
    num_train_epochs: int = Field(3, description="Number of training epochs")
    per_device_train_batch_size: int = Field(4, description="Batch size per device")
    gradient_accumulation_steps: int = Field(1, description="Gradient accumulation steps")
    
    # Advanced configuration
    target_modules: List[str] = Field(
        ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        description="Target modules for LoRA"
    )
    weight_decay: float = Field(0.001, description="Weight decay")
    optimizer: str = Field("adamw_torch", description="Optimizer type")
    fp16: bool = Field(True, description="Use mixed precision training")
    
    class Config:
        schema_extra = {
            "example": {
                "lora_r": 8,
                "lora_alpha": 16,
                "lora_dropout": 0.05,
                "learning_rate": 3e-4,
                "num_train_epochs": 3,
                "per_device_train_batch_size": 4,
                "gradient_accumulation_steps": 1,
                "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
                "weight_decay": 0.001,
                "optimizer": "adamw_torch",
                "fp16": True
            }
        }


class TrainingProgress(BaseModel):
    """Training progress information"""
    job_id: str
    status: TrainingStatus
    progress: float = Field(0.0, ge=0.0, le=1.0)
    current_epoch: int = 0
    total_epochs: int
    loss: Optional[float] = None
    learning_rate: Optional[float] = None
    start_time: Optional[str] = None
    estimated_time_remaining: Optional[int] = None  # in seconds


# Request schemas
class DatasetCreate(BaseModel):
    """Schema for creating a training dataset"""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    format: DatasetFormat = Field(DatasetFormat.INSTRUCT)
    samples: List[Dict[str, str]] = Field(..., min_items=10)
    
    @validator('samples')
    def validate_samples(cls, samples, values):
        """Validate that samples have the correct format"""
        format = values.get('format', DatasetFormat.INSTRUCT)
        
        for i, sample in enumerate(samples):
            if format == DatasetFormat.INSTRUCT:
                if not all(k in sample for k in ['instruction', 'response']):
                    raise ValueError(f"Sample {i} missing required fields for instruct format")
            
            elif format == DatasetFormat.CHAT:
                if 'messages' not in sample:
                    raise ValueError(f"Sample {i} missing 'messages' field for chat format")
                
                messages = sample['messages']
                if not isinstance(messages, list) or len(messages) < 2:
                    raise ValueError(f"Sample {i} must have at least 2 messages")
                
                for msg in messages:
                    if not all(k in msg for k in ['role', 'content']):
                        raise ValueError(f"Message in sample {i} missing required fields")
            
            elif format == DatasetFormat.RAW:
                if 'text' not in sample:
                    raise ValueError(f"Sample {i} missing 'text' field for raw format")
        
        return samples


class DatasetUpdate(BaseModel):
    """Schema for updating a training dataset"""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class LoraTrainingConfig(BaseModel):
    """Configuration for LoRA fine-tuning"""
    # LoRA configuration
    lora_r: int = Field(8, ge=1, le=64, description="LoRA attention dimension")
    lora_alpha: int = Field(16, ge=1, le=128, description="LoRA alpha parameter")
    lora_dropout: float = Field(0.05, ge=0.0, le=0.5, description="Dropout probability for LoRA layers")
    
    # Training parameters
    learning_rate: float = Field(3e-4, ge=1e-6, le=1e-2, description="Learning rate")
    num_train_epochs: int = Field(3, ge=1, le=20, description="Number of training epochs")
    per_device_train_batch_size: int = Field(4, ge=1, le=32, description="Training batch size per device")
    gradient_accumulation_steps: int = Field(1, ge=1, le=16, description="Number of updates steps to accumulate before performing a backward/update pass")
    
    # Advanced parameters
    target_modules: Optional[List[str]] = None
    weight_decay: float = Field(0.001, ge=0.0, le=0.1, description="Weight decay")
    optimizer: str = Field("adamw_torch", description="Optimizer")
    warmup_ratio: float = Field(0.03, ge=0.0, le=0.5, description="Portion of training steps for learning rate warmup")
    max_grad_norm: float = Field(1.0, ge=0.0, le=10.0, description="Maximum gradient norm (for gradient clipping)")


class TrainingJobCreate(BaseModel):
    """Schema for creating a new training job"""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    dataset_id: str
    base_model: str = Field(..., min_length=3, max_length=200)
    config: LoraTrainingConfig


class DeployModelRequest(BaseModel):
    """Schema for deploying a trained model"""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    set_as_default: bool = Field(False, description="Whether to set this model as the default for inference")


class InferenceRequest(BaseModel):
    """Schema for making inference requests"""
    prompt: str = Field(..., min_length=1)
    model_id: Optional[str] = None
    max_new_tokens: int = Field(256, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0)
    
    class Config:
        schema_extra = {
            "example": {
                "prompt": "Write a short poem about the ocean:",
                "max_new_tokens": 256,
                "temperature": 0.7,
                "top_p": 0.9
            }
        }


class InferenceResponse(BaseModel):
    """Schema for inference response"""
    response: str
    model_id: str
    generation_time: float  # in seconds
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class EvaluationCreate(BaseModel):
    """Schema for creating a model evaluation"""
    model_id: str
    test_set_name: Optional[str] = None
    metrics: Dict[str, Any]


# Response schemas
class DatasetResponse(BaseModel):
    """Schema for dataset response"""
    id: str
    name: str
    description: Optional[str]
    format: str
    sample_count: int
    created_at: datetime
    created_by: Optional[str]
    
    class Config:
        orm_mode = True


class DatasetDetailResponse(DatasetResponse):
    """Detailed schema for dataset response including samples"""
    samples: List[Dict[str, Any]]
    
    class Config:
        orm_mode = True


class TrainingJobResponse(BaseModel):
    """Schema for training job response"""
    id: str
    name: str
    description: Optional[str]
    dataset_id: str
    base_model: str
    status: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    created_at: datetime
    created_by: Optional[str]
    metrics: Optional[Dict[str, Any]]
    error_message: Optional[str]
    
    class Config:
        orm_mode = True


class TrainingJobDetailResponse(TrainingJobResponse):
    """Detailed schema for training job response including configuration"""
    lora_config: Dict[str, Any]
    dataset: DatasetResponse
    
    class Config:
        orm_mode = True


class DeployedModelResponse(BaseModel):
    """Schema for deployed model response"""
    id: str
    name: str
    description: Optional[str]
    base_model: str
    model_type: str
    is_active: bool
    is_default: bool
    inference_count: int
    average_latency_ms: Optional[int]
    deployed_at: datetime
    deployed_by: Optional[str]
    metrics: Optional[Dict[str, Any]]
    
    class Config:
        orm_mode = True


class ModelEvaluationResponse(BaseModel):
    """Schema for model evaluation response"""
    id: str
    model_id: str
    metrics: Dict[str, Any]
    test_set_name: Optional[str]
    test_set_size: Optional[int]
    evaluated_at: datetime
    
    class Config:
        orm_mode = True