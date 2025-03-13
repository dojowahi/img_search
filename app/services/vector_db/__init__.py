from app.core.config import settings, VectorDBType
from app.services.vector_db.postgres import postgres_service
from app.services.vector_db.chroma import chroma_service

# Factory function to get the configured vector DB service
def get_vector_db_service():
    if settings.VECTOR_DB_TYPE == VectorDBType.POSTGRES:
        return postgres_service
    elif settings.VECTOR_DB_TYPE == VectorDBType.CHROMA:
        return chroma_service
    else:
        raise ValueError(f"Unsupported vector database type: {settings.VECTOR_DB_TYPE}")