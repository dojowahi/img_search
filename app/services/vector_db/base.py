from abc import ABC, abstractmethod
from typing import List, Dict, Any
import numpy as np

class VectorDBService(ABC):
    """Abstract base class for vector database services"""
    
    @abstractmethod
    async def initialize(self):
        """Initialize the vector database service"""
        pass
    
    @abstractmethod
    def store_embedding(self, id: str, vector: np.ndarray, metadata: Dict[str, Any] = None):
        """Store an embedding vector with metadata"""
        pass
    
    @abstractmethod
    def search_similar(self, vector: np.ndarray, limit: int = 5) -> List[Any]:
        """
        Search for similar vectors
        Returns a list of search results with id, score, and payload
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of the vector database implementation"""
        pass