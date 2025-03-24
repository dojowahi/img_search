from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SearchResult(BaseModel):
    id: str
    filename: str
    similarity_score: float
    image_url: str

class SearchResponse(BaseModel):
    results: List[SearchResult]

class VideoSearchResponse(BaseModel):
    results: List[SearchResult]
    frame_img_url: str

class UploadResult(BaseModel):
    id: str
    filename: str
    url: Optional[str] = None

class UploadResponse(BaseModel):
    uploaded_images: List[UploadResult]

class ChatMessageRequest(BaseModel):
    question: str
    prod_specific_info: str
    tcin:str
    
class HealthResponse(BaseModel):
    status: str
    timestamp: float
    vector_db_type: str
    gcp_project: str
