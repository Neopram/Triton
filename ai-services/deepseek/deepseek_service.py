# deepseek_service.py
# DeepSeek AI service for cloud-based processing of complex maritime queries

import os
import logging
import time
import json
import asyncio
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("deepseek_service.log")
    ]
)
logger = logging.getLogger("deepseek_service")

# Data models for the API
class HealthResponse(BaseModel):
    status: str
    version: str
    model: str
    load: float
    memory_used: float
    uptime: float

class DeepSeekRequest(BaseModel):
    prompt: str
    max_tokens: int = Field(default=2048, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    stream: bool = False
    maritime_context: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class DeepSeekResponse(BaseModel):
    text: str
    usage: TokenUsage
    processing_time: float
    model_version: str
    source: str = "deepseek"
    request_id: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None
    status_code: int

# Main class for the DeepSeek service
class DeepSeekService:
    def __init__(self, model_path: str = None):
        self.start_time = time.time()
        self.model_path = model_path or os.environ.get("DEEPSEEK_MODEL", "deepseek-ai/deepseek-coder-33b-instruct")
        self.model = None
        self.tokenizer = None
        self.is_initialized = False
        self.last_usage_time = 0
        self.idle_timeout = int(os.environ.get("DEEPSEEK_IDLE_TIMEOUT", "3600"))  # 1 hour default
        self.max_context_length = 8192
        
        # Initialize resource counter
        self.usage_stats = {
            "total_requests": 0,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "errors": 0,
            "cache_hits": 0,
            "processing_times": []
        }
        
        # Simple in-memory cache
        self.response_cache = {}
        self.cache_ttl = int(os.environ.get("DEEPSEEK_CACHE_TTL", "3600"))  # 1 hour default
        
        # Try to load the model on initialization
        self._load_model()
    
    def _load_model(self) -> bool:
        """Load the DeepSeek model into memory."""
        try:
            logger.info(f"Loading DeepSeek model from {self.model_path}")
            
            # Check GPU availability
            if torch.cuda.is_available():
                logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
                device = "cuda"
            else:
                logger.info("GPU not available, using CPU")
                device = "cpu"
            
            start_time = time.time()
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            
            # Load model with optimized parameters
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto",
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )
            
            load_time = time.time() - start_time
            logger.info(f"Model loaded successfully in {load_time:.2f} seconds")
            
            self.is_initialized = True
            self.last_usage_time = time.time()
            return True
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            self.is_initialized = False
            return False
    
    def _unload_model(self) -> None:
        """Release the model from memory to save resources."""
        if self.model is not None:
            del self.model
            self.model = None
            
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
            
        # Force CUDA memory release if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        self.is_initialized = False
        logger.info("Model unloaded from memory")
    
    @contextmanager
    def ensure_model_loaded(self):
        """Context manager to ensure the model is loaded during operation."""
        if not self.is_initialized:
            self._load_model()
            
        try:
            yield
        finally:
            self.last_usage_time = time.time()
    
    def check_idle_timeout(self) -> None:
        """Check if the model has been idle for too long and unload it if necessary."""
        if self.is_initialized and (time.time() - self.last_usage_time) > self.idle_timeout:
            logger.info(f"Model idle for more than {self.idle_timeout} seconds, unloading")
            self._unload_model()
    
    def health_check(self) -> Dict[str, Any]:
        """Check the status of the service."""
        gpu_load = 0
        memory_used = 0
        
        if torch.cuda.is_available():
            # Get GPU usage information
            gpu_load = torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated() if torch.cuda.max_memory_allocated() > 0 else 0
            memory_used = torch.cuda.memory_allocated() / (1024 * 1024)  # MB
        
        return {
            "status": "healthy" if self.is_initialized else "initializing",
            "version": "deepseek-maritime-service-1.0.0",
            "model": self.model_path,
            "load": gpu_load,
            "memory_used": memory_used,
            "uptime": time.time() - self.start_time,
            "stats": self.usage_stats
        }
    
    def _prepare_maritime_prompt(self, request: DeepSeekRequest) -> str:
        """Prepare a specialized prompt for maritime queries."""
        base_prompt = request.prompt
        
        # Enrich with maritime data if available
        if request.maritime_context:
            maritime_context = []
            
            if 'vessels' in request.maritime_context:
                vessel_info = []
                for vessel in request.maritime_context['vessels']:
                    vessel_info.append(f"- {vessel.get('name', 'Unknown vessel')}: Position {vessel.get('position', 'unknown')}, Speed {vessel.get('speed', 'unknown')} knots")
                
                if vessel_info:
                    maritime_context.append("Vessel Information:\n" + "\n".join(vessel_info))
            
            if 'weather' in request.maritime_context:
                weather = request.maritime_context['weather']
                maritime_context.append(f"Weather Conditions: {weather.get('description', 'N/A')}, Wind: {weather.get('wind', 'N/A')}, Waves: {weather.get('waves', 'N/A')}")
            
            if 'ports' in request.maritime_context:
                port_info = []
                for port in request.maritime_context['ports']:
                    port_info.append(f"- {port.get('name', 'Unknown port')}: Status {port.get('status', 'unknown')}, Capacity {port.get('capacity', 'unknown')}")
                
                if port_info:
                    maritime_context.append("Port Information:\n" + "\n".join(port_info))
            
            if 'route' in request.maritime_context:
                route = request.maritime_context['route']
                route_info = f"Route: From {route.get('origin', 'Unknown')} to {route.get('destination', 'Unknown')}"
                if 'waypoints' in route:
                    waypoints = route['waypoints']
                    if waypoints and len(waypoints) > 0:
                        route_info += f"\nWaypoints: {len(waypoints)}"
                maritime_context.append(route_info)
            
            # Add maritime context to the prompt
            if maritime_context:
                enhanced_prompt = f"""### System
You are Triton AI, a specialized maritime assistant for shipping and vessel management.
Provide expert, concise responses about maritime topics including vessel tracking, routes, 
weather conditions, and maritime operations. Focus on accuracy and practical information.
For safety issues, emphasize maritime best practices and regulations.

### Maritime Context
{chr(10).join(maritime_context)}

### User Query
{base_prompt}

### Response
"""
                return enhanced_prompt
        
        # If there's no maritime data, use a basic format
        return f"""### System
You are Triton AI, a specialized maritime assistant for shipping and vessel management.
Provide expert, concise responses about maritime topics including vessel tracking, routes, 
weather conditions, and maritime operations. Focus on accuracy and practical information.
For safety issues, emphasize maritime best practices and regulations.

### User Query
{base_prompt}

### Response
"""
    
    def _compute_cache_key(self, request: DeepSeekRequest) -> str:
        """Generate a cache key for a request."""
        # Simplify the context for the cache key
        context_key = {}
        if request.maritime_context:
            for key in ['vessels', 'weather', 'ports', 'route']:
                if key in request.maritime_context:
                    # Simplify to avoid too large keys
                    if key == 'vessels' and isinstance(request.maritime_context[key], list):
                        context_key[key] = len(request.maritime_context[key])
                    elif key == 'weather':
                        if isinstance(request.maritime_context[key], dict):
                            context_key[key] = request.maritime_context[key].get('description', '')
                    else:
                        context_key[key] = True
        
        # Create cache key
        cache_dict = {
            "prompt": request.prompt,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "context": context_key
        }
        
        return json.dumps(cache_dict, sort_keys=True)
    
    def _cleanup_cache(self) -> None:
        """Clean up expired entries from the cache."""
        current_time = time.time()
        keys_to_remove = []
        
        for key, (data, timestamp) in self.response_cache.items():
            if current_time - timestamp > self.cache_ttl:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.response_cache[key]
    
    async def generate(self, request: DeepSeekRequest) -> DeepSeekResponse:
        """Generate text using the DeepSeek model based on a prompt."""
        start_time = time.time()
        
        # Update statistics
        self.usage_stats["total_requests"] += 1
        
        # Check cache
        cache_key = self._compute_cache_key(request)
        if cache_key in self.response_cache:
            cached_data, _ = self.response_cache[cache_key]
            self.usage_stats["cache_hits"] += 1
            logger.info(f"Cache hit for request: {request.request_id}")
            
            # Recreate response with current timing
            cached_data["processing_time"] = time.time() - start_time
            return DeepSeekResponse(**cached_data)
        
        try:
            with self.ensure_model_loaded():
                # Prepare the prompt with maritime context
                prompt = self._prepare_maritime_prompt(request)
                
                # Tokenize the input
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
                input_tokens = inputs.input_ids.shape[1]
                self.usage_stats["total_tokens_in"] += input_tokens
                
                # Verify that it doesn't exceed the maximum context
                if input_tokens >= self.max_context_length:
                    raise ValueError(f"Input exceeds maximum context length ({input_tokens} > {self.max_context_length})")
                
                # Generate response
                outputs = self.model.generate(
                    inputs.input_ids,
                    max_new_tokens=request.max_tokens,
                    do_sample=request.temperature > 0,
                    temperature=max(0.01, request.temperature),  # Avoid temperature 0
                    pad_token_id=self.tokenizer.eos_token_id
                )
                
                # Decode the complete response
                full_output = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                
                # Extract only the response part (omit the prompt)
                response_text = full_output[len(prompt):].strip()
                
                # Update statistics
                output_tokens = len(outputs[0]) - len(inputs.input_ids[0])
                self.usage_stats["total_tokens_out"] += output_tokens
                
                processing_time = time.time() - start_time
                self.usage_stats["processing_times"].append(processing_time)
                
                # Limit the number of stored times
                if len(self.usage_stats["processing_times"]) > 100:
                    self.usage_stats["processing_times"] = self.usage_stats["processing_times"][-100:]
                
                # Create response
                response = {
                    "text": response_text,
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens
                    },
                    "processing_time": processing_time,
                    "model_version": self.model_path,
                    "source": "deepseek",
                    "request_id": request.request_id
                }
                
                # Save to cache
                self.response_cache[cache_key] = (response, time.time())
                
                # Clean cache periodically
                if len(self.response_cache) % 10 == 0:
                    self._cleanup_cache()
                
                return DeepSeekResponse(**response)
                
        except Exception as e:
            self.usage_stats["errors"] += 1
            logger.error(f"Error in generation: {str(e)}")
            raise RuntimeError(f"Error generating text: {str(e)}")

# FastAPI Implementation
app = FastAPI(
    title="DeepSeek Maritime AI Service",
    description="API for processing complex maritime queries with DeepSeek",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("BACKEND_CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize service
service = DeepSeekService()

# Regularly check if the model should be unloaded due to inactivity
@app.on_event("startup")
async def startup_event():
    logger.info("Starting DeepSeek Maritime AI Service")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down DeepSeek Maritime AI Service")
    if service.is_initialized:
        service._unload_model()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.debug(f"Request {request.method} {request.url.path} processed in {process_time:.4f} seconds")
    return response

@app.get("/health", response_model=HealthResponse)
async def health():
    """Endpoint to check the status of the service."""
    health_info = service.health_check()
    return HealthResponse(
        status=health_info["status"],
        version=health_info["version"],
        model=health_info["model"],
        load=health_info["load"],
        memory_used=health_info["memory_used"],
        uptime=health_info["uptime"]
    )

@app.post("/generate", response_model=DeepSeekResponse)
async def generate(request: DeepSeekRequest, background_tasks: BackgroundTasks):
    """Endpoint to generate text using DeepSeek."""
    try:
        response = await service.generate(request)
        # Check timeout in background
        background_tasks.add_task(service.check_idle_timeout)
        return response
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def stats():
    """Endpoint to get service statistics."""
    health_info = service.health_check()
    return health_info["stats"]

@app.post("/reset-stats")
async def reset_stats():
    """Endpoint to reset service statistics."""
    service.usage_stats = {
        "total_requests": 0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "errors": 0,
        "cache_hits": 0,
        "processing_times": []
    }
    return {"status": "Statistics reset successfully"}

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "details": str(exc), "status_code": 500}
    )

# Entry point for direct execution
if __name__ == "__main__":
    # Configure port from environment variables
    port = int(os.environ.get("DEEPSEEK_PORT", "8000"))
    
    # Start the web server
    uvicorn.run("deepseek_service:app", host="0.0.0.0", port=port, log_level="info")