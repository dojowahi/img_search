from abc import ABC, abstractmethod
from typing import Tuple, Optional
from fastapi import UploadFile

class StorageService(ABC):
    """Abstract base class for storage services"""
    
    @abstractmethod
    async def initialize(self):
        """Initialize the storage service"""
        pass
    
    @abstractmethod
    async def save_upload(self, file: UploadFile) -> Tuple[str, bool]:
        """
        Save an uploaded file to temporary storage for processing
        Returns tuple of (temp_file_path, is_cleanup_needed)
        """
        pass
    
    @abstractmethod
    def store_file(self, temp_file_path: str, filename: str, file_id: Optional[str] = None) -> Tuple[str, str]:
        """
        Move a file from temporary storage to permanent storage
        Returns tuple of (file_id, permanent_path_or_url)
        """
        pass
    
    @abstractmethod
    def get_file_path(self, file_id: str, filename: Optional[str] = None) -> str:
        """Get the file path or URL for a stored file"""
        pass
    
    @abstractmethod
    def get_public_url(self, file_id: str, filename: Optional[str] = None) -> str:
        """Get a public URL for accessing the file"""
        pass
    
    @abstractmethod
    def cleanup_temp_file(self, temp_file_path: str) -> None:
        """Clean up a temporary file"""
        pass