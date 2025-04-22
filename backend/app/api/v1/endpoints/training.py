from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.schemas.training import (
    DatasetCreate, 
    DatasetResponse, 
    DatasetDetailResponse,
    DatasetUpdate,
    TrainingJobCreate,
    TrainingJobResponse,
    TrainingJobDetailResponse,
    TrainingProgress,
    DeployModelRequest,
    DeployedModelResponse,
    InferenceRequest,
    InferenceResponse,
    EvaluationCreate,
    ModelEvaluationResponse
)
from app.services.lora_training import LoraTrainingService
from app.services.model_manager import ModelManager

router = APIRouter()

# Initialize services
training_service = LoraTrainingService()
model_manager = ModelManager()


# Dataset endpoints
@router.post("/datasets", response_model=DatasetResponse)
async def create_dataset(
    dataset: DatasetCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new training dataset"""
    # Check permissions
    if current_user.role not in ["admin", "researcher"]:
        raise HTTPException(status_code=403, detail="Not authorized to create datasets")
    
    try:
        # Create dataset
        created_dataset = await training_service.create_dataset(
            name=dataset.name,
            description=dataset.description,
            data=dataset.samples
        )
        
        # Set creator
        created_dataset.created_by = current_user.id
        
        # Save to database
        db.add(created_dataset)
        db.commit()
        db.refresh(created_dataset)
        
        return created_dataset
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create dataset: {str(e)}")


@router.get("/datasets", response_model=List[DatasetResponse])
async def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List available training datasets"""
    try:
        datasets = training_service.list_datasets(limit=limit, offset=skip)
        return datasets
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list datasets: {str(e)}")


@router.get("/datasets/{dataset_id}", response_model=DatasetDetailResponse)
async def get_dataset(
    dataset_id: str = Path(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get details of a specific dataset"""
    try:
        dataset = training_service.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Get samples
        samples = training_service.get_dataset_samples(dataset_id)
        
        # Create response with samples
        response = DatasetDetailResponse(
            **dataset.dict(),
            samples=samples
        )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dataset: {str(e)}")


@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: str = Path(...),
    dataset_update: DatasetUpdate = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update dataset details"""
    # Check permissions
    if current_user.role not in ["admin", "researcher"]:
        raise HTTPException(status_code=403, detail="Not authorized to update datasets")
    
    try:
        # Get dataset
        dataset = training_service.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Check ownership
        if dataset.created_by and dataset.created_by != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized to update this dataset")
        
        # Update fields
        if dataset_update.name:
            dataset.name = dataset_update.name
        
        if dataset_update.description is not None:
            dataset.description = dataset_update.description
        
        # Save to database
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        
        return dataset
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update dataset: {str(e)}")


@router.delete("/datasets/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: str = Path(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a dataset"""
    # Check permissions
    if current_user.role not in ["admin", "researcher"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete datasets")
    
    try:
        # Get dataset
        dataset = training_service.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Check ownership
        if dataset.created_by and dataset.created_by != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized to delete this dataset")
        
        # Check if dataset is used in any training jobs
        if db.query(training_service.TrainingJob).filter_by(dataset_id=dataset_id).count() > 0:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete dataset that is used in training jobs"
            )
        
        # Delete from database
        db.delete(dataset)
        db.commit()
        
        # Delete files
        # This would need to be implemented in the training service
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete dataset: {str(e)}")


# Training job endpoints
@router.post("/jobs", response_model=TrainingJobResponse)
async def create_training_job(
    job: TrainingJobCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new training job"""
    # Check permissions
    if current_user.role not in ["admin", "researcher"]:
        raise HTTPException(status_code=403, detail="Not authorized to create training jobs")
    
    try:
        # Check if dataset exists
        dataset = training_service.get_dataset(job.dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Create training job
        training_job = await training_service.create_training_job(
            dataset_id=job.dataset_id,
            model_name=job.base_model,
            config=job.config
        )
        
        # Set additional fields
        training_job.name = job.name
        training_job.description = job.description
        training_job.created_by = current_user.id
        
        # Save to database
        db.add(training_job)
        db.commit()
        db.refresh(training_job)
        
        return training_job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create training job: {str(e)}")


@router.get("/jobs", response_model=List[TrainingJobResponse])
async def list_training_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List training jobs"""
    try:
        jobs = training_service.list_training_jobs(limit=limit, offset=skip)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list training jobs: {str(e)}")


@router.get("/jobs/{job_id}", response_model=TrainingJobDetailResponse)
async def get_training_job(
    job_id: str = Path(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get details of a specific training job"""
    try:
        job = training_service.get_training_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Training job not found")
        
        # Get dataset
        dataset = training_service.get_dataset(job.dataset_id)
        
        # Create response with dataset
        response = TrainingJobDetailResponse(
            **job.dict(),
            dataset=dataset
        )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get training job: {str(e)}")


@router.get("/jobs/{job_id}/progress", response_model=TrainingProgress)
async def get_training_progress(
    job_id: str = Path(...),
    current_user: User = Depends(get_current_active_user)
):
    """Get the current progress of a training job"""
    try:
        progress = training_service.get_training_progress(job_id)
        if not progress:
            raise HTTPException(status_code=404, detail="Training job not found or not started")
        
        return progress
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get training progress: {str(e)}")


@router.post("/jobs/{job_id}/cancel", response_model=TrainingJobResponse)
async def cancel_training_job(
    job_id: str = Path(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cancel a running training job"""
    # Check permissions
    if current_user.role not in ["admin", "researcher"]:
        raise HTTPException(status_code=403, detail="Not authorized to cancel training jobs")
    
    try:
        # Get job
        job = training_service.get_training_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Training job not found")
        
        # Check ownership
        if job.created_by and job.created_by != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized to cancel this training job")
        
        # Cancel job
        cancelled = await training_service.cancel_training_job(job_id)
        if not cancelled:
            raise HTTPException(status_code=400, detail="Failed to cancel training job")
        
        # Refresh job data
        job = training_service.get_training_job(job_id)
        
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel training job: {str(e)}")


# Model deployment endpoints
@router.post("/models/deploy/{job_id}", response_model=DeployedModelResponse)
async def deploy_model(
    job_id: str = Path(...),
    request: DeployModelRequest = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Deploy a trained model for inference"""
    # Check permissions
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to deploy models")
    
    try:
        # Get training job
        job = training_service.get_training_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Training job not found")
        
        # Check if job is completed
        if job.status != "completed":
            raise HTTPException(status_code=400, detail="Training job is not completed")
        
        # Deploy model
        deployed_model = model_manager.deploy_model(
            model_id=job_id,
            name=request.name,
            description=request.description
        )
        
        # Set additional fields
        deployed_model.deployed_by = current_user.id
        deployed_model.training_job_id = job_id
        
        # Set as default if requested
        if request.set_as_default:
            model_manager.set_default_model(job_id)
            deployed_model.is_default = True
        
        # Save to database
        db.add(deployed_model)
        db.commit()
        db.refresh(deployed_model)
        
        return deployed_model
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deploy model: {str(e)}")


@router.get("/models/deployed", response_model=List[DeployedModelResponse])
async def list_deployed_models(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List deployed models"""
    try:
        models = model_manager.get_deployed_models()
        return models
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list deployed models: {str(e)}")


@router.delete("/models/deployed/{model_id}", status_code=204)
async def undeploy_model(
    model_id: str = Path(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Remove a model from deployment"""
    # Check permissions
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to undeploy models")
    
    try:
        # Undeploy model
        success = model_manager.undeploy_model(model_id)
        if not success:
            raise HTTPException(status_code=404, detail="Model not found or already undeployed")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to undeploy model: {str(e)}")


@router.post("/models/default/{model_id}", response_model=DeployedModelResponse)
async def set_default_model(
    model_id: str = Path(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Set a model as the default for inference"""
    # Check permissions
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to set default model")
    
    try:
        # Set default model
        success = model_manager.set_default_model(model_id)
        if not success:
            raise HTTPException(status_code=404, detail="Model not found or not deployed")
        
        # Update database
        models = model_manager.get_deployed_models()
        for model in models:
            model.is_default = (model.id == model_id)
            db.add(model)
        
        db.commit()
        
        # Get the updated model
        deployed_model = next((m for m in models if m.id == model_id), None)
        if not deployed_model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        return deployed_model
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set default model: {str(e)}")


# Inference endpoint
@router.post("/inference", response_model=InferenceResponse)
async def generate_text(
    request: InferenceRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Generate text using a deployed model"""
    try:
        # Start timing
        import time
        start_time = time.time()
        
        # Check if model_id is specified, otherwise use default
        model_id = request.model_id or model_manager.get_default_model_id()
        if not model_id:
            raise HTTPException(status_code=404, detail="No models are deployed")
        
        # Generate text
        response_text = await model_manager.predict(
            prompt=request.prompt,
            model_id=model_id,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
            top_p=request.top_p
        )
        
        # Calculate tokens
        # This is a simplified calculation - in a real app you'd use the tokenizer
        prompt_tokens = len(request.prompt.split())
        completion_tokens = len(response_text.split())
        total_tokens = prompt_tokens + completion_tokens
        
        # Calculate generation time
        generation_time = time.time() - start_time
        
        # Create response
        response = InferenceResponse(
            response=response_text,
            model_id=model_id,
            generation_time=generation_time,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens
        )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate text: {str(e)}")


# Model evaluation endpoints
@router.post("/evaluations", response_model=ModelEvaluationResponse)
async def create_evaluation(
    evaluation: EvaluationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Record a model evaluation"""
    # Check permissions
    if current_user.role not in ["admin", "researcher"]:
        raise HTTPException(status_code=403, detail="Not authorized to create evaluations")
    
    try:
        # Check if model exists
        deployed_models = model_manager.get_deployed_models()
        model_exists = any(m.id == evaluation.model_id for m in deployed_models)
        if not model_exists:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Create evaluation
        from app.models.training import ModelEvaluation
        import uuid
        
        model_eval = ModelEvaluation(
            id=str(uuid.uuid4()),
            model_id=evaluation.model_id,
            metrics=evaluation.metrics,
            test_set_name=evaluation.test_set_name,
            evaluated_by=current_user.id
        )
        
        # Save to database
        db.add(model_eval)
        db.commit()
        db.refresh(model_eval)
        
        return model_eval
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create evaluation: {str(e)}")


@router.get("/evaluations", response_model=List[ModelEvaluationResponse])
async def list_evaluations(
    model_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List model evaluations"""
    try:
        from app.models.training import ModelEvaluation
        
        # Build query
        query = db.query(ModelEvaluation)
        
        # Filter by model_id if provided
        if model_id:
            query = query.filter(ModelEvaluation.model_id == model_id)
        
        # Execute query
        evaluations = query.order_by(ModelEvaluation.evaluated_at.desc()).all()
        
        return evaluations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list evaluations: {str(e)}")