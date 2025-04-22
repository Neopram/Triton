import os
import json
import logging
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import HTTPException

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel, PeftConfig

from app.core.config import settings
from app.models.training import DeployedModel, ModelType

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(settings.DATA_DIR, "models")
DEPLOYED_MODELS_DIR = os.path.join(settings.DATA_DIR, "deployed_models")

# Ensure directories exist
for directory in [MODELS_DIR, DEPLOYED_MODELS_DIR]:
    os.makedirs(directory, exist_ok=True)

class ModelManager:
    """Service for managing trained models and model deployment"""
    
    def __init__(self):
        self.loaded_models = {}  # Cache for loaded models
        self.default_model_id = None
        
        # Load deployed models on startup
        self._load_deployed_models_config()
    
    def _load_deployed_models_config(self) -> None:
        """Load the configuration of currently deployed models"""
        config_path = os.path.join(DEPLOYED_MODELS_DIR, "config.json")
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                self.default_model_id = config.get("default_model_id")
        else:
            # Create empty config if it doesn't exist
            with open(config_path, "w") as f:
                json.dump({"deployed_models": [], "default_model_id": None}, f, indent=2)
    
    def _save_deployed_models_config(self, deployed_models: List[DeployedModel]) -> None:
        """Save the configuration of currently deployed models"""
        config_path = os.path.join(DEPLOYED_MODELS_DIR, "config.json")
        
        config = {
            "deployed_models": [model.dict() for model in deployed_models],
            "default_model_id": self.default_model_id,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2, default=str)
    
    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all trained models available for deployment"""
        available_models = []
        
        for model_id in os.listdir(MODELS_DIR):
            model_dir = os.path.join(MODELS_DIR, model_id)
            
            if not os.path.isdir(model_dir):
                continue
            
            config_path = os.path.join(model_dir, "config.json")
            
            if not os.path.exists(config_path):
                continue
            
            with open(config_path, "r") as f:
                config = json.load(f)
            
            # Add model size
            model_size = self._get_directory_size(model_dir)
            
            available_models.append({
                "id": model_id,
                "base_model": config.get("base_model"),
                "lora_config": config.get("lora_config"),
                "training_time": config.get("training_time"),
                "completed_at": config.get("completed_at"),
                "model_size_bytes": model_size,
                "model_size_mb": round(model_size / (1024 * 1024), 2)
            })
        
        return available_models
    
    def get_deployed_models(self) -> List[DeployedModel]:
        """Get the list of currently deployed models"""
        config_path = os.path.join(DEPLOYED_MODELS_DIR, "config.json")
        
        if not os.path.exists(config_path):
            return []
        
        with open(config_path, "r") as f:
            config = json.load(f)
        
        deployed_models = []
        for model_data in config.get("deployed_models", []):
            deployed_models.append(DeployedModel(**model_data))
        
        return deployed_models
    
    def deploy_model(self, model_id: str, name: str, description: str) -> DeployedModel:
        """Deploy a trained model for inference"""
        # Check if model exists
        model_dir = os.path.join(MODELS_DIR, model_id)
        if not os.path.isdir(model_dir):
            raise HTTPException(status_code=404, detail=f"Model with ID {model_id} not found")
        
        # Load model config
        config_path = os.path.join(model_dir, "config.json")
        with open(config_path, "r") as f:
            model_config = json.load(f)
        
        # Copy model to deployed_models directory
        deployed_model_dir = os.path.join(DEPLOYED_MODELS_DIR, model_id)
        
        # Remove if exists
        if os.path.exists(deployed_model_dir):
            shutil.rmtree(deployed_model_dir)
        
        # Copy model files
        shutil.copytree(model_dir, deployed_model_dir)
        
        # Create deployed model record
        deployed_model = DeployedModel(
            id=model_id,
            name=name,
            description=description,
            base_model=model_config.get("base_model"),
            model_type=ModelType.LORA,
            deployed_at=datetime.utcnow(),
            is_active=True
        )
        
        # Add to deployed models list
        deployed_models = self.get_deployed_models()
        
        # Check if already deployed
        existing_index = next((i for i, m in enumerate(deployed_models) if m.id == model_id), None)
        if existing_index is not None:
            deployed_models[existing_index] = deployed_model
        else:
            deployed_models.append(deployed_model)
        
        # If this is the first model, set as default
        if not self.default_model_id:
            self.default_model_id = model_id
        
        # Save configuration
        self._save_deployed_models_config(deployed_models)
        
        return deployed_model
    
    def undeploy_model(self, model_id: str) -> bool:
        """Remove a model from deployment"""
        deployed_models = self.get_deployed_models()
        
        # Find and remove the model
        filtered_models = [m for m in deployed_models if m.id != model_id]
        
        if len(filtered_models) == len(deployed_models):
            # Model not found
            return False
        
        # Update default model if needed
        if self.default_model_id == model_id:
            self.default_model_id = filtered_models[0].id if filtered_models else None
        
        # Save updated configuration
        self._save_deployed_models_config(filtered_models)
        
        # Remove model directory
        deployed_model_dir = os.path.join(DEPLOYED_MODELS_DIR, model_id)
        if os.path.exists(deployed_model_dir):
            shutil.rmtree(deployed_model_dir)
        
        # Remove from cache if loaded
        if model_id in self.loaded_models:
            del self.loaded_models[model_id]
        
        return True
    
    def set_default_model(self, model_id: str) -> bool:
        """Set a model as the default for inference"""
        deployed_models = self.get_deployed_models()
        
        # Check if model is deployed
        if not any(m.id == model_id for m in deployed_models):
            return False
        
        # Update default model
        self.default_model_id = model_id
        
        # Save configuration
        self._save_deployed_models_config(deployed_models)
        
        return True
    
    def get_default_model_id(self) -> Optional[str]:
        """Get the ID of the default model"""
        return self.default_model_id
    
    def _get_directory_size(self, path: str) -> int:
        """Get the size of a directory in bytes"""
        total_size = 0
        
        for dirpath, _, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                total_size += os.path.getsize(file_path)
        
        return total_size
    
    async def get_model(self, model_id: Optional[str] = None) -> Any:
        """
        Get a loaded model for inference
        If model_id is None, the default model will be used
        """
        model_id = model_id or self.default_model_id
        
        if not model_id:
            raise HTTPException(status_code=404, detail="No models are deployed")
        
        # Check if model is already loaded
        if model_id in self.loaded_models:
            return self.loaded_models[model_id]
        
        # Load model
        try:
            deployed_model_dir = os.path.join(DEPLOYED_MODELS_DIR, model_id)
            
            if not os.path.exists(deployed_model_dir):
                raise HTTPException(status_code=404, detail=f"Model with ID {model_id} is not deployed")
            
            # Load config
            config_path = os.path.join(deployed_model_dir, "config.json")
            with open(config_path, "r") as f:
                config = json.load(f)
            
            base_model_name = config.get("base_model")
            
            # Load base model and tokenizer
            tokenizer = AutoTokenizer.from_pretrained(base_model_name)
            
            # For LoRA models
            peft_config = PeftConfig.from_pretrained(deployed_model_dir)
            
            # Load base model
            model = AutoModelForCausalLM.from_pretrained(
                peft_config.base_model_name_or_path,
                torch_dtype=torch.float16,
                device_map="auto"
            )
            
            # Load LoRA adapter
            model = PeftModel.from_pretrained(model, deployed_model_dir)
            
            # Cache the loaded model and tokenizer
            self.loaded_models[model_id] = {
                "model": model,
                "tokenizer": tokenizer,
                "config": config
            }
            
            return self.loaded_models[model_id]
            
        except Exception as e:
            logger.error(f"Error loading model {model_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")
    
    async def predict(self, 
                     prompt: str, 
                     model_id: Optional[str] = None,
                     max_new_tokens: int = 256,
                     temperature: float = 0.7,
                     top_p: float = 0.9) -> str:
        """Generate text with a deployed model"""
        model_data = await self.get_model(model_id)
        
        model = model_data["model"]
        tokenizer = model_data["tokenizer"]
        
        # Set pad token to eos token if not set
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        # Encode prompt
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        
        # Generate
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=temperature > 0,
                pad_token_id=tokenizer.pad_token_id,
            )
        
        # Decode and return response
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Remove prompt from response
        if response.startswith(prompt):
            response = response[len(prompt):]
        
        return response.strip()