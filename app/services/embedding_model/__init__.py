from app.core.config import settings, EmbeddingType
from app.services.embedding_model.clip import clip_embedding
from app.services.embedding_model.vertex_multimodal import vertex_embedding

# Factory function to get the configured embedding service
def get_embedding_service():
    if settings.EMBEDDING_TYPE == EmbeddingType.VERTEX:
        return vertex_embedding
    elif settings.EMBEDDING_TYPE == EmbeddingType.CLIP:
        return clip_embedding
    else:
        raise ValueError(f"Unsupported vector database type: {settings.EMBEDDING_TYPE}")