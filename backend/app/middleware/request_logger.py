# C:\Users\feder\Desktop\MaritimeAPP\backend\app\middleware\request_logger.py

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging import log_api_request

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all HTTP requests"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Record start time
        start_time = time.time()
        
        # Get client IP address
        client_host = request.client.host if request.client else "unknown"
        
        # Try to extract user ID if user is authenticated
        user_id = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.id
        
        # Process the request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log the request
            log_api_request(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                processing_time=processing_time,
                user_id=user_id
            )
            
            return response
        except Exception as e:
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log the error
            log_api_request(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=500,  # Assuming server error
                processing_time=processing_time,
                user_id=user_id,
                error=str(e)
            )
            
            # Re-raise the exception
            raise