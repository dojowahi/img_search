import logging
import os
from typing import Any, Dict, List, NamedTuple

import chromadb
import numpy as np
from chromadb.utils import embedding_functions

from app.core.config import settings
from app.services.vector_db.base import VectorDBService

logger = logging.getLogger(__name__)

class ChromaSearchResult(NamedTuple):
    """Standard search result structure"""
    id: str
    score: float
    payload: Dict[str, Any]

class ChromaVectorDBService(VectorDBService):
    """ChromaDB implementation of VectorDBService"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.collection_name = settings.CHROMA_COLLECTION_NAME
        self.persist_directory = settings.CHROMA_PERSIST_DIRECTORY
    
    async def initialize(self):
        """Initialize the ChromaDB client and create collection if needed"""
        try:
            # Create persist directory if it doesn't exist
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            logger.info(f"Initialized ChromaDB client with persistence at {self.persist_directory}")
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                logger.info(f"Found existing ChromaDB collection: {self.collection_name}")
            except Exception:
                # Define a custom embedding function that accepts raw vectors
                class RawEmbeddingFunction(embedding_functions.EmbeddingFunction):
                    def __call__(self, texts):
                        return texts  # Identity function - the vectors are already created by CLIP

                # Create a new collection
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    embedding_function=RawEmbeddingFunction(),
                    metadata={"description": "Image embeddings from CLIP model"}
                )
                logger.info(f"Created new ChromaDB collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {e}")
            raise
    
    def store_embedding(self, id: str, vector: np.ndarray, metadata: Dict[str, Any] = None):
        """Store an embedding in ChromaDB"""
        if metadata is None:
            metadata = {}
        
        try:
            # Convert any non-string metadata values to strings to ensure compatibility
            metadata_copy = {}
            for k, v in metadata.items():
                if isinstance(v, (int, float)):
                    metadata_copy[k] = str(v)
                elif isinstance(v, dict):
                    # Store nested dict as string to avoid compatibility issues
                    import json
                    metadata_copy[k] = json.dumps(v)
                else:
                    metadata_copy[k] = str(v) if not isinstance(v, str) else v
            
            # Check if the document already exists
            try:
                existing = self.collection.get(ids=[id])
                if existing and len(existing['ids']) > 0:
                    # Update existing document
                    self.collection.update(
                        ids=[id],
                        embeddings=[vector.tolist()],
                        metadatas=[metadata_copy]
                    )
                else:
                    # Add new document
                    self.collection.add(
                        ids=[id],
                        embeddings=[vector.tolist()],
                        metadatas=[metadata_copy]
                    )
            except Exception:
                # Add new document if checking existence fails
                self.collection.add(
                    ids=[id],
                    embeddings=[vector.tolist()],
                    metadatas=[metadata_copy]
                )
        except Exception as e:
            logger.error(f"Error storing embedding in ChromaDB: {e}")
            raise
    
    def search_similar(self, vector: np.ndarray, limit: int = 5) -> List[Any]:
        """
        Search for similar vectors in ChromaDB
        """
        try:
            # Normalize the query vector (ensure unit length)
            vector_norm = np.linalg.norm(vector)
            if vector_norm > 0:
                normalized_vector = vector / vector_norm
            else:
                normalized_vector = vector
            
            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=[normalized_vector.tolist()],
                n_results=limit
            )
            
            # Add debug logging
            logger.debug(f"ChromaDB query result keys: {results.keys()}")
            
            # Format results to match our standard structure
            search_results = []
            if results and 'ids' in results and len(results['ids']) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    # Get distance value - in ChromaDB, smaller distance means more similar
                    if 'distances' in results and len(results['distances']) > 0:
                        distance = results['distances'][0][i]
                        logger.debug(f"Raw distance for {doc_id}: {distance}")
                    else:
                        logger.warning("No distances in ChromaDB results - using default")
                        distance = 1.0  # Default to middle value
                    
                    # Get metadata
                    metadata = {}
                    if 'metadatas' in results and len(results['metadatas']) > 0:
                        metadata = results['metadatas'][0][i] or {}
                    
                    # Convert distance to similarity score based on distance metric
                    # For cosine distance (0 to 2 range), use: 1 - (distance/2)
                    similarity_score = max(0, 1.0 - (distance / 2.0))
                    
                    logger.debug(f"Converted similarity score: {similarity_score}")
                    
                    # Handle metadata
                    parsed_metadata = {}
                    for k, v in metadata.items():
                        if isinstance(v, (str, int, float, bool)) or v is None:
                            parsed_metadata[k] = v
                        elif isinstance(v, dict):
                            parsed_metadata.update(v)
                        else:
                            # Convert other types to string
                            parsed_metadata[k] = str(v)
                    
                    result = ChromaSearchResult(
                        id=doc_id,
                        score=similarity_score,
                        payload=parsed_metadata
                    )
                    search_results.append(result)
            
            return search_results
        except Exception as e:
            logger.error(f"Error searching in ChromaDB: {e}")
            raise
    
    def get_name(self) -> str:
        return "chroma"

# Create a global instance
chroma_service = ChromaVectorDBService()