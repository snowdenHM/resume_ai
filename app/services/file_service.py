"""
File service for handling resume uploads, parsing, and processing.
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import mimetypes
import re

import aiofiles
from fastapi import UploadFile
import magic

from app.config import settings
from app.core.security import security
from app.exceptions import (
    FileProcessingException, UnsupportedFileTypeException,
    FileTooLargeException, MaliciousFileException
)
from app.utils.file_parser import ResumeParser

logger = logging.getLogger(__name__)


class FileService:
    """Service for file upload, validation, and processing."""
    
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.max_file_size = settings.MAX_FILE_SIZE
        self.allowed_types = settings.ALLOWED_FILE_TYPES
        self.parser = ResumeParser()
        
        # Ensure upload directory exists
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Supported MIME types mapping
        self.mime_types = {
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/msword": ".doc",
            "text/plain": ".txt"
        }
    
    async def upload_resume(
        self,
        file: UploadFile,
        user_id: uuid.UUID,
        resume_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Upload and process a resume file.
        
        Args:
            file: Uploaded file
            user_id: User ID
            resume_id: Optional existing resume ID for updates
            
        Returns:
            File processing results
        """
        try:
            # Validate file
            await self._validate_file(file)
            
            # Generate unique filename
            file_id = resume_id or uuid.uuid4()
            file_extension = self._get_file_extension(file.filename)
            safe_filename = self._generate_safe_filename(file_id, file_extension)
            
            # Create user directory
            user_dir = self.upload_dir / str(user_id)
            user_dir.mkdir(exist_ok=True)
            
            file_path = user_dir / safe_filename
            
            # Save file
            await self._save_file(file, file_path)
            
            # Get file info
            file_info = await self._get_file_info(file_path, file.filename)
            
            # Parse file content
            parsing_result = await self._parse_file(file_path, file_info["mime_type"])
            
            # Combine results
            result = {
                **file_info,
                **parsing_result,
                "file_path": str(file_path),
                "user_id": str(user_id),
                "resume_id": str(file_id)
            }
            
            logger.info(f"Resume uploaded and processed: {safe_filename} for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Resume upload failed for user {user_id}: {e}")
            raise FileProcessingException(f"File upload failed: {str(e)}")
    
    async def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            file_path: Path to file to delete
            
        Returns:
            True if successful
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"File deleted: {file_path}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"File deletion failed: {file_path}, error: {e}")
            return False
    
    async def get_file_content(self, file_path: str) -> bytes:
        """
        Get file content as bytes.
        
        Args:
            file_path: Path to file
            
        Returns:
            File content as bytes
        """
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
                
        except Exception as e:
            logger.error(f"Failed to read file: {file_path}, error: {e}")
            raise FileProcessingException(f"Failed to read file: {str(e)}")
    
    async def reprocess_file(self, file_path: str) -> Dict[str, Any]:
        """
        Reprocess an existing file.
        
        Args:
            file_path: Path to existing file
            
        Returns:
            Reprocessing results
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileProcessingException("File not found")
            
            # Detect MIME type
            mime_type = magic.from_file(str(path), mime=True)
            
            # Parse file
            parsing_result = await self._parse_file(path, mime_type)
            
            logger.info(f"File reprocessed: {file_path}")
            return parsing_result
            
        except Exception as e:
            logger.error(f"File reprocessing failed: {file_path}, error: {e}")
            raise FileProcessingException(f"File reprocessing failed: {str(e)}")
    
    # Private Methods
    async def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > self.max_file_size:
            raise FileTooLargeException(self.max_file_size // (1024 * 1024))
        
        # Check file type by extension
        file_extension = self._get_file_extension(file.filename)
        if file_extension not in self.allowed_types:
            raise UnsupportedFileTypeException(file_extension, self.allowed_types)
        
        # Read file content for validation
        content = await file.read()
        file.file.seek(0)  # Reset for later reading
        
        # Validate MIME type
        detected_mime = magic.from_buffer(content, mime=True)
        if detected_mime not in self.mime_types:
            raise UnsupportedFileTypeException(detected_mime, list(self.mime_types.keys()))
        
        # Security check
        security_check = security.check_file_safety(content, list(self.mime_types.keys()))
        if not security_check["is_safe"]:
            if security_check.get("has_suspicious_content"):
                raise MaliciousFileException()
            else:
                raise FileProcessingException("File failed security validation")
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename."""
        if not filename:
            return ""
        return Path(filename).suffix.lower()
    
    def _generate_safe_filename(self, file_id: uuid.UUID, extension: str) -> str:
        """Generate safe filename."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"resume_{file_id}_{timestamp}{extension}"
    
    async def _save_file(self, file: UploadFile, file_path: Path) -> None:
        """Save uploaded file to disk."""
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
                
        except Exception as e:
            raise FileProcessingException(f"Failed to save file: {str(e)}")
    
    async def _get_file_info(self, file_path: Path, original_filename: str) -> Dict[str, Any]:
        """Get file information."""
        try:
            stat = file_path.stat()
            mime_type = magic.from_file(str(file_path), mime=True)
            
            return {
                "original_filename": original_filename,
                "file_size": stat.st_size,
                "mime_type": mime_type,
                "file_extension": file_path.suffix,
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "modified_at": datetime.fromtimestamp(stat.st_mtime)
            }
            
        except Exception as e:
            raise FileProcessingException(f"Failed to get file info: {str(e)}")
    
    async def _parse_file(self, file_path: Path, mime_type: str) -> Dict[str, Any]:
        """Parse file content based on type."""
        try:
            if mime_type == "application/pdf":
                return await self.parser.parse_pdf(file_path)
            elif mime_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
                return await self.parser.parse_docx(file_path)
            elif mime_type == "application/msword":
                return await self.parser.parse_doc(file_path)
            elif mime_type == "text/plain":
                return await self.parser.parse_text(file_path)
            else:
                raise FileProcessingException(f"Unsupported file type for parsing: {mime_type}")
                
        except Exception as e:
            logger.error(f"File parsing failed: {file_path}, error: {e}")
            return {
                "raw_text": "",
                "structured_data": {},
                "word_count": 0,
                "page_count": 0,
                "parsing_error": str(e)
            }
    
    def get_file_url(self, file_path: str) -> str:
        """Generate file access URL."""
        # This would typically generate a signed URL or API endpoint
        # For now, return a simple path
        return f"/api/v1/files/{Path(file_path).name}"
    
    def get_file_hash(self, content: bytes) -> str:
        """Generate file hash for deduplication."""
        return hashlib.sha256(content).hexdigest()
    
    async def cleanup_orphaned_files(self, user_id: uuid.UUID, active_file_paths: List[str]) -> int:
        """
        Clean up orphaned files for a user.
        
        Args:
            user_id: User ID
            active_file_paths: List of currently active file paths
            
        Returns:
            Number of files cleaned up
        """
        try:
            user_dir = self.upload_dir / str(user_id)
            if not user_dir.exists():
                return 0
            
            cleaned_count = 0
            active_paths = set(Path(path).name for path in active_file_paths)
            
            for file_path in user_dir.iterdir():
                if file_path.is_file() and file_path.name not in active_paths:
                    file_path.unlink()
                    cleaned_count += 1
                    logger.info(f"Cleaned up orphaned file: {file_path}")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Cleanup failed for user {user_id}: {e}")
            return 0
    
    async def get_storage_stats(self, user_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Args:
            user_id: Optional user ID for user-specific stats
            
        Returns:
            Storage statistics
        """
        try:
            if user_id:
                user_dir = self.upload_dir / str(user_id)
                if not user_dir.exists():
                    return {"total_files": 0, "total_size": 0}
                
                files = list(user_dir.iterdir())
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                
                return {
                    "total_files": len(files),
                    "total_size": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2)
                }
            else:
                # Global stats
                total_files = 0
                total_size = 0
                
                for user_dir in self.upload_dir.iterdir():
                    if user_dir.is_dir():
                        files = list(user_dir.iterdir())
                        total_files += len(files)
                        total_size += sum(f.stat().st_size for f in files if f.is_file())
                
                return {
                    "total_files": total_files,
                    "total_size": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2)
                }
                
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {"error": str(e)}


# Export service
__all__ = ["FileService"]