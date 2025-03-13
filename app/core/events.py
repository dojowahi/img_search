import logging

from app.services.embedding import embedding_service
from app.services.storage.gcs import gcs_storage_service
from app.services.vector_db import get_vector_db_service

logger = logging.getLogger(__name__)

async def startup_event():
    """Application startup: initialize all services"""
    logger.info("Initializing application services...")
    
    # Initialize services with better error handling
    try:
        # Initialize embedding service
        logger.info("Initializing embedding service...")
        await embedding_service.initialize()
        
        # Initialize storage service
        logger.info("Initializing storage service...")
        await gcs_storage_service.initialize()
        
        # Initialize the configured vector DB service
        logger.info("Initializing vector database service...")
        vector_db_service = get_vector_db_service()
        await vector_db_service.initialize()
        
        logger.info(f"All services initialized successfully. Using {vector_db_service.get_name()} as vector database.")
    except Exception as e:
        logger.error(f"Error during application startup: {e}")
        # Re-raise to prevent the application from starting with uninitialized services
        raise

async def shutdown_event():
    """Application shutdown: cleanup resources"""
    logger.info("Shutting down application...")
    # Add any cleanup operations here if needed