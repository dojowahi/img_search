from typing import List, Optional
from pydantic import BaseModel, HttpUrl

class SearchResult(BaseModel):
    id: str
    filename: str
    similarity_score: float
    image_url: str

class SearchResponse(BaseModel):
    results: List[SearchResult]

class UploadResult(BaseModel):
    id: str
    filename: str
    url: Optional[str] = None

class UploadResponse(BaseModel):
    uploaded_images: List[UploadResult]

class HealthResponse(BaseModel):
    status: str
    timestamp: float
    vector_db_type: str
    gcp_project: str