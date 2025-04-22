import os
import json
import uuid
import logging
import asyncio
import time
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime
from pydantic import BaseModel

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import (
    LoraConfig,
    get_peft_model,
    PeftModel,
    prepare_model_for_kbit_training
)
from datasets import Dataset

from app.core.config import settings
from app.schemas.training import (
    TrainingProgress,
    TrainingStatus,
    LoraModelConfig,
    LoraTrainingConfig
)
from app.models.training import TrainingJob, TrainingJobStatus, TrainingDataset

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(settings.DATA_DIR, "models")
DATASET_DIR = os.path.join(settings.DATA_DIR, "training_datasets")
CHECKPOINTS_DIR = os.path.join(settings.DATA_DIR, "checkpoints")

# Ensure directories exist
for directory in [MODELS_DIR, DATASET_DIR, CHECKPOINTS_DIR]:
    os.makedirs(directory, exist_ok=True)

class LoraTrainingService:
    """Service for managing LoRA fine-tuning of language models"""
    
    def __init__(self):
        self.active_trainings = {}  # Track currently running trainings
        self.training_progress = {}  # Store training progress
    
    async def create_training_job(
        self, 
        dataset_id: str, 
        model_name: str,
        config: LoraTrainingConfig
    ) -> TrainingJob:
        """Create a new training job"""
        
        # Generate unique ID for the training job
        job_id = str(uuid.uuid4())
        
        # Create training job record
        job = TrainingJob(
            id=job_id,
            dataset_id=dataset_id,
            base_model=model_name,
            lora_config=config.dict(),
            status=TrainingJobStatus.PENDING,
            start_time=None,
            end_time=None,
            metrics={},
            created_at=datetime.utcnow()
        )
        
        # Save to database or file
        self._save_job_metadata(job)
        
        # Initialize progress tracking
        self.training_progress[job_id] = TrainingProgress(
            job_id=job_id,
            status=TrainingStatus.PENDING,
            progress=0.0,
            current_epoch=0,
            total_epochs=config.num_train_epochs,
            loss=None,
            learning_rate=None,
            start_time=None,
            estimated_time_remaining=None
        )
        
        # Start training process in background
        asyncio.create_task(self._run_training_job(job))
        
        return job
    
    async def _run_training_job(self, job: TrainingJob) -> None:
        """Run the training job in the background"""
        
        job_id = job.id
        
        try:
            # Update job status
            job.status = TrainingJobStatus.RUNNING
            job.start_time = datetime.utcnow()
            self._save_job_metadata(job)
            
            # Update progress tracking
            self.training_progress[job_id].status = TrainingStatus.RUNNING
            self.training_progress[job_id].start_time = datetime.utcnow().isoformat()
            
            # Get dataset
            dataset = await self._load_dataset(job.dataset_id)
            if not dataset:
                raise ValueError(f"Dataset {job.dataset_id} not found")
            
            # Load configuration
            lora_config = LoraModelConfig(**job.lora_config)
            
            # Start training process
            await self._train_model(
                job_id=job_id,
                dataset=dataset,
                base_model=job.base_model,
                lora_config=lora_config
            )
            
            # Update job status upon completion
            job.status = TrainingJobStatus.COMPLETED
            job.end_time = datetime.utcnow()
            self._save_job_metadata(job)
            
            # Update progress tracking
            self.training_progress[job_id].status = TrainingStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Training job {job_id} failed: {str(e)}")
            
            # Update job status
            job.status = TrainingJobStatus.FAILED
            job.end_time = datetime.utcnow()
            job.error_message = str(e)
            self._save_job_metadata(job)
            
            # Update progress tracking
            self.training_progress[job_id].status = TrainingStatus.FAILED
            
        finally:
            # Clean up
            if job_id in self.active_trainings:
                del self.active_trainings[job_id]
    
    async def _train_model(
        self,
        job_id: str,
        dataset: Dataset,
        base_model: str,
        lora_config: LoraModelConfig
    ) -> None:
        """Perform the actual model training with LoRA"""
        
        # This should run in a thread or process pool to avoid blocking
        def _training_process():
            try:
                start_time = time.time()
                
                # 1. Load base model with quantization
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16
                )
                
                model = AutoModelForCausalLM.from_pretrained(
                    base_model,
                    quantization_config=bnb_config,
                    device_map="auto",
                    trust_remote_code=True
                )
                
                # 2. Prepare model for training
                model = prepare_model_for_kbit_training(model)
                
                # 3. Configure LoRA adapters
                peft_config = LoraConfig(
                    r=lora_config.lora_r,
                    lora_alpha=lora_config.lora_alpha,
                    lora_dropout=lora_config.lora_dropout,
                    bias="none",
                    task_type="CAUSAL_LM",
                    target_modules=lora_config.target_modules
                )
                
                model = get_peft_model(model, peft_config)
                
                # 4. Load tokenizer
                tokenizer = AutoTokenizer.from_pretrained(base_model)
                tokenizer.pad_token = tokenizer.eos_token
                
                # 5. Setup training arguments
                output_dir = os.path.join(CHECKPOINTS_DIR, job_id)
                
                training_args = TrainingArguments(
                    output_dir=output_dir,
                    num_train_epochs=lora_config.num_train_epochs,
                    per_device_train_batch_size=lora_config.per_device_train_batch_size,
                    gradient_accumulation_steps=lora_config.gradient_accumulation_steps,
                    optim=lora_config.optimizer,
                    learning_rate=lora_config.learning_rate,
                    weight_decay=lora_config.weight_decay,
                    fp16=True,
                    logging_steps=10,
                    save_strategy="epoch",
                    group_by_length=True,
                    report_to="none"
                )
                
                # 6. Setup trainer with custom callback for progress tracking
                class ProgressCallback(transformers.TrainerCallback):
                    def on_log(self, args, state, control, logs=None, **kwargs):
                        if state.is_local_process_zero and logs:
                            epoch = state.epoch
                            progress = epoch / lora_config.num_train_epochs
                            
                            # Update training progress
                            training_progress = self.training_progress.get(job_id)
                            if training_progress:
                                training_progress.progress = float(progress)
                                training_progress.current_epoch = int(epoch)
                                training_progress.loss = logs.get("loss")
                                training_progress.learning_rate = logs.get("learning_rate")
                                
                                # Calculate estimated time remaining
                                elapsed_time = time.time() - start_time
                                if progress > 0:
                                    total_estimated_time = elapsed_time / progress
                                    time_remaining = total_estimated_time - elapsed_time
                                    training_progress.estimated_time_remaining = int(time_remaining)
                
                trainer = transformers.Trainer(
                    model=model,
                    args=training_args,
                    train_dataset=dataset,
                    callbacks=[ProgressCallback()]
                )
                
                # 7. Train the model
                trainer.train()
                
                # 8. Save the final model
                final_model_dir = os.path.join(MODELS_DIR, job_id)
                os.makedirs(final_model_dir, exist_ok=True)
                
                # Save adapter weights
                model.save_pretrained(final_model_dir)
                
                # Save tokenizer
                tokenizer.save_pretrained(final_model_dir)
                
                # Save config
                with open(os.path.join(final_model_dir, "config.json"), "w") as f:
                    json.dump({
                        "base_model": base_model,
                        "lora_config": lora_config.dict(),
                        "training_time": time.time() - start_time,
                        "completed_at": datetime.utcnow().isoformat()
                    }, f, indent=2)
                
                return {
                    "training_time": time.time() - start_time,
                    "model_size": self._get_directory_size(final_model_dir)
                }
                
            except Exception as e:
                logger.error(f"Training process for job {job_id} failed: {str(e)}")
                raise
        
        # Run the training process in a ThreadPoolExecutor
        loop = asyncio.get_event_loop()
        self.active_trainings[job_id] = True
        
        metrics = await loop.run_in_executor(None, _training_process)
        
        # Update job with metrics
        job = self.get_training_job(job_id)
        if job:
            job.metrics = metrics
            self._save_job_metadata(job)
    
    async def _load_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Load a dataset from file or database"""
        dataset_path = os.path.join(DATASET_DIR, f"{dataset_id}.json")
        
        if not os.path.exists(dataset_path):
            return None
        
        with open(dataset_path, "r") as f:
            data = json.load(f)
        
        # Convert to HuggingFace Dataset
        return Dataset.from_dict(data)
    
    def get_training_job(self, job_id: str) -> Optional[TrainingJob]:
        """Get a training job by ID"""
        job_path = os.path.join(CHECKPOINTS_DIR, f"{job_id}_metadata.json")
        
        if not os.path.exists(job_path):
            return None
        
        with open(job_path, "r") as f:
            data = json.load(f)
        
        return TrainingJob(**data)
    
    def list_training_jobs(self, limit: int = 10, offset: int = 0) -> List[TrainingJob]:
        """List training jobs with pagination"""
        jobs = []
        
        # List all job metadata files
        metadata_files = [f for f in os.listdir(CHECKPOINTS_DIR) if f.endswith("_metadata.json")]
        metadata_files.sort(key=lambda x: os.path.getmtime(os.path.join(CHECKPOINTS_DIR, x)), reverse=True)
        
        # Apply pagination
        metadata_files = metadata_files[offset:offset+limit]
        
        # Load job data
        for filename in metadata_files:
            job_path = os.path.join(CHECKPOINTS_DIR, filename)
            
            with open(job_path, "r") as f:
                data = json.load(f)
            
            jobs.append(TrainingJob(**data))
        
        return jobs
    
    def get_training_progress(self, job_id: str) -> Optional[TrainingProgress]:
        """Get the current progress of a training job"""
        return self.training_progress.get(job_id)
    
    def _save_job_metadata(self, job: TrainingJob) -> None:
        """Save job metadata to file"""
        job_path = os.path.join(CHECKPOINTS_DIR, f"{job.id}_metadata.json")
        
        with open(job_path, "w") as f:
            json.dump(job.dict(), f, indent=2, default=str)
    
    def _get_directory_size(self, path: str) -> int:
        """Get the size of a directory in bytes"""
        total_size = 0
        
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                total_size += os.path.getsize(file_path)
        
        return total_size
    
    async def cancel_training_job(self, job_id: str) -> bool:
        """Cancel a running training job"""
        if job_id not in self.active_trainings:
            return False
        
        # In a real implementation, we would need to terminate the training process
        # This is a simplified version
        self.active_trainings[job_id] = False
        
        # Update job status
        job = self.get_training_job(job_id)
        if job:
            job.status = TrainingJobStatus.CANCELLED
            job.end_time = datetime.utcnow()
            self._save_job_metadata(job)
        
        # Update progress tracking
        if job_id in self.training_progress:
            self.training_progress[job_id].status = TrainingStatus.CANCELLED
        
        return True

    async def create_dataset(self, name: str, description: str, data: List[Dict[str, str]]) -> TrainingDataset:
        """Create a new training dataset"""
        dataset_id = str(uuid.uuid4())
        
        # Create dataset record
        dataset = TrainingDataset(
            id=dataset_id,
            name=name,
            description=description,
            sample_count=len(data),
            created_at=datetime.utcnow()
        )
        
        # Save dataset to file
        dataset_path = os.path.join(DATASET_DIR, f"{dataset_id}.json")
        with open(dataset_path, "w") as f:
            json.dump(data, f, indent=2)
        
        # Save metadata
        metadata_path = os.path.join(DATASET_DIR, f"{dataset_id}_metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(dataset.dict(), f, indent=2, default=str)
        
        return dataset
    
    def list_datasets(self, limit: int = 10, offset: int = 0) -> List[TrainingDataset]:
        """List available training datasets"""
        datasets = []
        
        # List all dataset metadata files
        metadata_files = [f for f in os.listdir(DATASET_DIR) if f.endswith("_metadata.json")]
        metadata_files.sort(key=lambda x: os.path.getmtime(os.path.join(DATASET_DIR, x)), reverse=True)
        
        # Apply pagination
        metadata_files = metadata_files[offset:offset+limit]
        
        # Load dataset metadata
        for filename in metadata_files:
            metadata_path = os.path.join(DATASET_DIR, filename)
            
            with open(metadata_path, "r") as f:
                data = json.load(f)
            
            datasets.append(TrainingDataset(**data))
        
        return datasets
    
    def get_dataset(self, dataset_id: str) -> Optional[TrainingDataset]:
        """Get dataset by ID"""
        metadata_path = os.path.join(DATASET_DIR, f"{dataset_id}_metadata.json")
        
        if not os.path.exists(metadata_path):
            return None
        
        with open(metadata_path, "r") as f:
            data = json.load(f)
        
        return TrainingDataset(**data)
    
    def get_dataset_samples(self, dataset_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get sample data from a dataset"""
        dataset_path = os.path.join(DATASET_DIR, f"{dataset_id}.json")
        
        if not os.path.exists(dataset_path):
            return []
        
        with open(dataset_path, "r") as f:
            data = json.load(f)
        
        return data[:limit]