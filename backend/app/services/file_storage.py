import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.core.config import settings

# Base storage paths
STORAGE_PATH = os.getenv("FILE_STORAGE_PATH", "storage")
MESSAGE_ATTACHMENTS_PATH = os.path.join(STORAGE_PATH, "message_attachments")

# Ensure directories exist
os.makedirs(STORAGE_PATH, exist_ok=True)
os.makedirs(MESSAGE_ATTACHMENTS_PATH, exist_ok=True)

async def save_message_attachment(file: UploadFile, user_id: int) -> dict:
    """
    Save a message attachment to the file system.
    
    Args:
        file: The uploaded file
        user_id: ID of the user uploading the file
        
    Returns:
        dict: Information about the saved file
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Invalid file")
    
    # Create user-specific directory
    user_dir = os.path.join(MESSAGE_ATTACHMENTS_PATH, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    
    # Generate unique filename
    file_ext = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(user_dir, unique_filename)
    
    # Get file size
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    
    # Check file size limit (10MB)
    if file_size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds maximum allowed (10MB)")
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
    
    # Return file info
    relative_path = os.path.join(str(user_id), unique_filename)
    return {
        "file_name": file.filename,
        "file_path": relative_path,
        "file_size": file_size,
        "mime_type": file.content_type or "application/octet-stream"
    }

def get_attachment_path(relative_path: str) -> str:
    """
    Get the absolute path for a message attachment.
    
    Args:
        relative_path: Relative path stored in the database
        
    Returns:
        str: Absolute path to the file
    """
    return os.path.join(MESSAGE_ATTACHMENTS_PATH, relative_path)

async def delete_attachment(relative_path: str) -> bool:
    """
    Delete a message attachment.
    
    Args:
        relative_path: Relative path stored in the database
        
    Returns:
        bool: True if deletion was successful
    """
    full_path = get_attachment_path(relative_path)
    
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False
    except Exception:
        return False