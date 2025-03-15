import os
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings  # Updated import

load_dotenv()
class VectorDBType(str, Enum):
    """Supported vector database types"""
    POSTGRES = "postgres"
    CHROMA = "chroma"


class EmbeddingType(str, Enum):
    """Supported embedding types"""
    VERTEX = "vertex"
    CLIP = "clip"

class VectorSize(int, Enum):
    """Supported vector sizes"""
    VERTEX = 512 # Try different dimenions: 128, 256, 512, 1408
    CLIP = 512 # Size of CLIP ViT-B/32 embeddings

class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "Image Search API"
    API_V1_STR: str = "/api/v1"
    
    # GCP settings
    GCP_PROJECT_ID: str = os.environ.get("GCP_PROJECT_ID", "gen-ai-4all")
    GCP_REGION: str = os.environ.get("GCP_REGION", "us-central1")
    GCS_SIGNED_URL_EXPIRATION_MINUTES: int = int(os.environ.get("GCS_SIGNED_URL_EXPIRATION_MINUTES", "2"))
    GCP_SERVICE_ACCOUNT_FILE: Optional[str] = os.environ.get("GCP_SERVICE_ACCOUNT_FILE")
    GCS_BUCKET_NAME: str = os.environ.get("GCS_BUCKET_NAME", "search_clip_img")
    GCS_IMAGES_PREFIX: str = os.environ.get("GCS_IMAGES_PREFIX", "images/")
    UPLOAD_DIR: str = os.environ.get("UPLOAD_DIR", "/home/ankurwahi/python_dev/img_search/tmp_uploads")  # For temporary storage
    # CLIP model settings
    CLIP_MODEL: str = os.environ.get("CLIP_MODEL", "ViT-B/32")
    VERTEX_EMBEDDING_MODEL: str = os.environ.get("VERTEX_EMBEDDING_MODEL", "multimodalembedding@001")

    # Vector DB settings
    VECTOR_DB_TYPE: VectorDBType = Field(
        default=VectorDBType.POSTGRES,
        description="Vector database implementation to use"
    )
    VECTOR_SIZE: VectorSize = Field(
        default=VectorSize.CLIP,
        description="Vector Size"
    )  
    
    EMBEDDING_TYPE: EmbeddingType = Field(
        default=EmbeddingType.VERTEX,
        description="Embedding implementation to use"
    )
    # Chroma DB settings
    CHROMA_PERSIST_DIRECTORY: str = os.environ.get("CHROMA_PERSIST_DIRECTORY", "/home/ankurwahi/python_dev/img_search/chroma")
    CHROMA_COLLECTION_NAME: str = os.environ.get("CHROMA_COLLECTION_NAME", "image_embeddings")
    
    # Cloud SQL settings (if using Postgres with pgvector)
    DB_INSTANCE_NAME: str = os.environ.get("DB_INSTANCE_NAME", "img-vector")
    DB_NAME: str = os.environ.get("DB_NAME", "embeddings")
    DB_USER: str = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD: str = os.environ.get("DB_PASSWORD")
    DB_HOST: str = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.environ.get("DB_PORT", 5432))
    INSTANCE_CONNECTION_NAME: Optional[str] = os.environ.get("INSTANCE_CONNECTION_NAME")
    
    
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
