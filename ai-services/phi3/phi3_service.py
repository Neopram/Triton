# phi3_service.py
# Lightweight Phi-3 AI service for local processing of maritime queries

import os
import logging
import time
import json
import threading
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
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
        logging.FileHandler("phi3_service.log")
    ]
)
logger = logging.getLogger("phi3_service")

# Load environment variables
PHI3_MODEL_PATH = os.environ.get("PHI3_MODEL_PATH", "microsoft/phi-3-mini-4k-instruct")
PHI3_PORT = int(os.environ.get("PHI3_PORT", "8001"))
PHI3_MAX_TOKENS = int(os.environ.get("PHI3_MAX_TOKENS", "1024"))
PHI3_CACHE_TTL = int(os.environ.get("PHI3_CACHE_TTL", "3600"))
PHI3_IDLE_TIMEOUT = int(os.environ.get("PHI3_IDLE_TIMEOUT", "1800"))  # 30 minutes
PHI3_MAX_CONTEXT_LENGTH = int(os.environ.get("PHI3_MAX_CONTEXT_LENGTH", "4096"))
PHI3_USE_4BIT = os.environ.get("PHI3_USE_4BIT", "TRUE").upper() == "TRUE"

# Data models for the API
class HealthResponse(BaseModel):
    status: str
    version: str
    model: str
    memory_usage: float
    model_loaded: bool
    uptime: float

class Phi3Request(BaseModel):
    input: str
    max_length: int = Field(default=1024, ge=1, le=2048)
    temperature: float = Field(default=0.5, ge=0.0, le=1.0)
    maritime_context: Optional[Dict[str, Any]] = None
    offline_mode: bool = False
    user_id: Optional[str] = None
    request_id: Optional[str] = None

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class Phi3Response(BaseModel):
    output: str
    usage: TokenUsage
    processing_time: float
    model_info: Dict[str, str]
    source: str = "phi3"
    request_id: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None
    status_code: int

# Simple cache for responses
@dataclass
class CacheEntry:
    response: Dict[str, Any]
    timestamp: float

class SimpleCache:
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl  # Time to live in seconds
        self.lock = threading.Lock()
    
    def _get_hash(self, input_str: str, params: Dict[str, Any]) -> str:
        """Generate a simple hash for the cache key."""
        params_str = json.dumps(params, sort_keys=True)
        return f"{hash(input_str)}_{hash(params_str)}"
    
    def get(self, input_str: str, params: Dict[str, Any]) -> Optional[CacheEntry]:
        """Get a cache entry if it exists and hasn't expired."""
        key = self._get_hash(input_str, params)
        
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                # Check if the entry has expired
                if time.time() - entry.timestamp <= self.ttl:
                    return entry
                else:
                    # Remove expired entries
                    del self.cache[key]
            
            return None
    
    def set(self, input_str: str, params: Dict[str, Any], response: Dict[str, Any]) -> None:
        """Store a response in the cache."""
        key = self._get_hash(input_str, params)
        
        with self.lock:
            # If the cache is full, remove the oldest entry
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.cache.items(), key=lambda x: x[1].timestamp)[0]
                del self.cache[oldest_key]
            
            # Store the new entry
            self.cache[key] = CacheEntry(
                response=response,
                timestamp=time.time()
            )
    
    def clear(self) -> None:
        """Clear the entire cache."""
        with self.lock:
            self.cache.clear()

# Main class for the Phi-3 service
class Phi3Service:
    def __init__(self, model_path: str = PHI3_MODEL_PATH):
        self.start_time = time.time()
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self.is_initialized = False
        self.device = "cpu"  # Default to CPU
        self.lock = threading.Lock()
        self.cache = SimpleCache(ttl=PHI3_CACHE_TTL)
        self.last_usage_time = time.time()
        self.idle_timeout = PHI3_IDLE_TIMEOUT
        self.max_context_length = PHI3_MAX_CONTEXT_LENGTH
        
        # Optimized tasks for Phi-3
        self.optimized_tasks = [
            "basic_query",
            "vessel_tracking",
            "position_calculation",
            "eta_simple",
            "weather_interpretation"
        ]
        
        # Statistics tracking
        self.usage_stats = {
            "total_requests": 0,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "errors": 0,
            "cache_hits": 0,
            "offline_mode_activations": 0,
            "processing_times": []
        }
        
        # Try to load the model with optimizations
        self._load_model_optimized()
    
    def _load_model_optimized(self) -> bool:
        """Load a highly optimized version of Phi-3 for limited resources."""
        try:
            logger.info(f"Loading Phi-3 model from {self.model_path}")
            
            # Determine available device
            if torch.cuda.is_available():
                logger.info(f"GPU available: {torch.cuda.get_device_name(0)}")
                self.device = "cuda"
            else:
                logger.info("GPU not available, using CPU")
                self.device = "cpu"
            
            # Quantization config to reduce memory usage
            quantization_config = None
            if self.device == "cuda" and PHI3_USE_4BIT:
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
                logger.info("Using 4-bit quantization for GPU")
            
            start_time = time.time()
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True
            )
            
            # Load model with optimizations
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                device_map="auto",
                quantization_config=quantization_config,
                low_cpu_mem_usage=True,
                trust_remote_code=True
            )
            
            load_time = time.time() - start_time
            logger.info(f"Phi-3 model loaded successfully in {load_time:.2f} seconds")
            
            self.is_initialized = True
            self.last_usage_time = time.time()
            return True
        except Exception as e:
            logger.error(f"Error loading Phi-3 model: {str(e)}")
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
        logger.info("Phi-3 model unloaded from memory")
    
    def check_idle_timeout(self) -> None:
        """Check if the model has been idle for too long and unload it if necessary."""
        if self.is_initialized and (time.time() - self.last_usage_time) > self.idle_timeout:
            logger.info(f"Model idle for more than {self.idle_timeout} seconds, unloading")
            self._unload_model()
    
    def health_check(self) -> Dict[str, Any]:
        """Check the status of the service."""
        memory_usage = 0
        
        if self.device == "cuda" and torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated()
            total = torch.cuda.get_device_properties(0).total_memory
            memory_usage = allocated / total
        else:
            # Basic estimation for CPU
            import psutil
            memory_usage = psutil.virtual_memory().percent / 100
        
        return {
            "status": "healthy" if self.is_initialized else "error",
            "version": "phi3-mini-service-1.0.0",
            "model": self.model_path,
            "memory_usage": memory_usage,
            "model_loaded": self.is_initialized,
            "device": self.device,
            "uptime": time.time() - self.start_time,
            "stats": self.usage_stats
        }
    
    def _format_maritime_prompt(self, request: Phi3Request) -> str:
        """Format the prompt with instructions and maritime context for Phi-3."""
        user_input = request.input.strip()
        
        # Build specific maritime context if available
        maritime_context = ""
        if request.maritime_context:
            context_parts = []
            
            if "vessels" in request.maritime_context:
                vessels = request.maritime_context["vessels"]
                vessel_info = [f"- {v.get('name', 'Unnamed vessel')}: {v.get('position', 'Unknown position')}" for v in vessels]
                if vessel_info:
                    context_parts.append("Vessel information:\n" + "\n".join(vessel_info))
            
            if "weather" in request.maritime_context:
                weather = request.maritime_context["weather"]
                context_parts.append(f"Weather: {weather}")
            
            if "route" in request.maritime_context:
                route = request.maritime_context["route"]
                context_parts.append(f"Route: {route}")
            
            if context_parts:
                maritime_context = "Maritime context:\n" + "\n".join(context_parts) + "\n\n"
        
        # Format compatible with Phi-3 (instruction with <|instructions|><|user|><|assistant|>)
        prompt = f"""<|instructions|>You are Triton AI, a specialized maritime assistant.
You provide concise answers about vessel tracking, routes, weather conditions, and maritime logistics.
Always be practical and focus on providing the most relevant information.
For safety-critical questions, emphasize caution and best practices.
Keep responses brief and to the point, but include all necessary information.
Use nautical terminology appropriate for maritime professionals.<|/instructions|>

<|user|>{maritime_context}{user_input}<|/user|>

<|assistant|>"""
        
        return prompt
    
    def _process_offline(self, request: Phi3Request) -> tuple:
        """Process queries in offline mode with pre-cached responses."""
        # Basic responses for offline mode
        offline_responses = {
            "position": "Unable to provide current vessel positions in offline mode. Last known position data is not available.",
            "weather": "Weather data cannot be retrieved in offline mode. Please re-establish connection for current weather information.",
            "route": "Basic route information is available in offline mode, but may not reflect current conditions.",
            "eta": "Estimated arrival time calculations are limited in offline mode and may not account for current conditions.",
            "default": "Limited functionality in offline mode. Basic information is available, but real-time data requires cloud connection."
        }
        
        # Determine what type of query this is
        input_lower = request.input.lower()
        
        if any(word in input_lower for word in ["position", "location", "where", "tracking"]):
            response = offline_responses["position"]
        elif any(word in input_lower for word in ["weather", "conditions", "forecast"]):
            response = offline_responses["weather"]
        elif any(word in input_lower for word in ["route", "path", "journey"]):
            response = offline_responses["route"]
        elif any(word in input_lower for word in ["eta", "arrival", "time", "when"]):
            response = offline_responses["eta"]
        else:
            response = offline_responses["default"]
        
        # Simulate token usage for consistency in response
        usage = {
            "prompt_tokens": len(request.input.split()),
            "completion_tokens": len(response.split()),
            "total_tokens": len(request.input.split()) + len(response.split())
        }
        
        return response, usage
    
    async def generate(self, request: Phi3Request) -> Phi3Response:
        """Generate a response using the Phi-3 model."""
        start_time = time.time()
        
        # Update statistics
        self.usage_stats["total_requests"] += 1
        
        # If we're in offline mode, provide offline response
        if request.offline_mode:
            self.usage_stats["offline_mode_activations"] += 1
            response_text, usage = self._process_offline(request)
            processing_time = time.time() - start_time
            
            return Phi3Response(
                output=response_text,
                usage=TokenUsage(**usage),
                processing_time=processing_time,
                model_info={"model": self.model_path, "mode": "offline"},
                source="phi3-offline",
                request_id=request.request_id
            )
        
        # Check cache first
        cache_params = {
            "max_length": request.max_length,
            "temperature": request.temperature,
            "maritime_context": json.dumps(request.maritime_context) if request.maritime_context else None
        }
        
        cached = self.cache.get(request.input, cache_params)
        if cached:
            logger.info(f"Cache hit found for request: {request.request_id}")
            self.usage_stats["cache_hits"] += 1
            
            # Update the processing time in the cached response
            cached_response = cached.response.copy()
            cached_response["processing_time"] = time.time() - start_time
            
            return Phi3Response(**cached_response)
        
        try:
            # Acquire lock to ensure exclusive use of the model
            with self.lock:
                if not self.is_initialized:
                    success = self._load_model_optimized()
                    if not success:
                        raise RuntimeError("Could not load Phi-3 model")
                
                # Update last usage time
                self.last_usage_time = time.time()
                
                # Prepare the prompt with specific format for Phi-3
                prompt = self._format_maritime_prompt(request)
                
                # Tokenize input
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
                input_length = inputs.input_ids.shape[1]
                self.usage_stats["total_tokens_in"] += input_length
                
                # Check context length
                if input_length >= self.max_context_length:
                    raise ValueError(f"Input exceeds maximum context length ({input_length} > {self.max_context_length})")
                
                # Generate response
                with torch.no_grad():
                    outputs = self.model.generate(
                        inputs.input_ids,
                        max_new_tokens=request.max_length,
                        do_sample=request.temperature > 0,
                        temperature=max(0.01, request.temperature),
                        top_p=0.9,
                        top_k=50,
                        repetition_penalty=1.1
                    )
                
                # Extract only the response part (without the prompt)
                generated_text = self.tokenizer.decode(
                    outputs[0][input_length:], 
                    skip_special_tokens=True
                )
                
                # Clean up the response
                response_text = generated_text.strip()
                
                # Calculate usage
                output_length = len(outputs[0]) - input_length
                self.usage_stats["total_tokens_out"] += output_length
                
                usage = {
                    "prompt_tokens": input_length,
                    "completion_tokens": output_length,
                    "total_tokens": len(outputs[0])
                }
                
                processing_time = time.time() - start_time
                self.usage_stats["processing_times"].append(processing_time)
                
                # Limit the number of stored times
                if len(self.usage_stats["processing_times"]) > 100:
                    self.usage_stats["processing_times"] = self.usage_stats["processing_times"][-100:]
                
                # Create response
                response = {
                    "output": response_text,
                    "usage": usage,
                    "processing_time": processing_time,
                    "model_info": {
                        "model": self.model_path,
                        "device": self.device
                    },
                    "source": "phi3",
                    "request_id": request.request_id
                }
                
                # Save to cache
                self.cache.set(request.input, cache_params, response)
                
                return Phi3Response(**response)
        except Exception as e:
            self.usage_stats["errors"] += 1
            logger.error(f"Error generating response with Phi-3: {str(e)}")
            raise RuntimeError(f"Processing error: {str(e)}")

# FastAPI Implementation
app = FastAPI(
    title="Phi-3 Local Maritime AI Service",
    description="API for processing maritime queries locally with Phi-3",
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
service = Phi3Service()

# Events
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Phi-3 Local Maritime AI Service")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Phi-3 Local Maritime AI Service")
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
async def health_check():
    """Check the status of the Phi-3 service."""
    health_info = service.health_check()
    return HealthResponse(
        status=health_info["status"],
        version="phi3-mini-service-1.0.0",
        model=health_info["model"],
        memory_usage=health_info["memory_usage"],
        model_loaded=health_info["model_loaded"],
        uptime=health_info["uptime"]
    )

@app.post("/generate", response_model=Phi3Response)
async def generate(request: Phi3Request, background_tasks: BackgroundTasks):
    """Generate text using the local Phi-3 model."""
    try:
        response = await service.generate(request)
        # Check idle timeout in background
        background_tasks.add_task(service.check_idle_timeout)
        return response
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def stats():
    """Get service statistics."""
    health_info = service.health_check()
    return health_info["stats"]

@app.post("/reset-stats")
async def reset_stats():
    """Reset service statistics."""
    service.usage_stats = {
        "total_requests": 0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "errors": 0,
        "cache_hits": 0,
        "offline_mode_activations": 0,
        "processing_times": []
    }
    return {"status": "Statistics reset successfully"}

@app.get("/clear-cache")
async def clear_cache():
    """Clear the cache."""
    service.cache.clear()
    return {"status": "Cache cleared successfully"}

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
    # Start the web server
    uvicorn.run("phi3_service:app", host="0.0.0.0", port=PHI3_PORT, log_level="info")