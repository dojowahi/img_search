import logging

import numpy as np
import vertexai
from vertexai.vision_models import Image, MultiModalEmbeddingModel

from app.core.config import settings
from app.services.embedding_model.base import EmbeddingModel

logger = logging.getLogger(__name__)

class VertexAIEmbeddingModel(EmbeddingModel):
    """
    Implementation of the EmbeddingModel interface for the Vertex AI model.
    """
    def __init__(self):
        """Initializes the VertexAIEmbeddingModel."""

        vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_REGION)
        self.model = MultiModalEmbeddingModel.from_pretrained(settings.VERTEX_EMBEDDING_MODEL)

    async def initialize(self):
        """Initializes the Vertex AI model."""
        logger.info(f"Vertex AI model {settings.VERTEX_EMBEDDING_MODEL} initialized.")
        # No explicit warmup needed for Vertex AI in this implementation
    
    def create_image_embedding(self, image_path: str) -> np.ndarray:
        """
        Creates an image embedding using the Vertex AI model.

        Raises:
            NotImplementedError: Vertex AI does not support image embeddings.
        """
        try:
            image = Image.load_from_file(image_path)

            embeddings = self.model.get_embeddings(
                image=image,
                dimension=settings.VECTOR_SIZE,
            )
            return embeddings.image_embedding
        except Exception as e:
            logger.error(f"Error creating image embedding for {image_path}: {e}")
            raise

    
    def create_text_embedding(self, text: str) -> np.ndarray:
        """
        Creates a text embedding using the Vertex AI model.

        Args:
            text (str): The text to embed.

        Returns:
            np.ndarray: The text embedding.
        """
        try:
           

            embeddings = self.model.get_embeddings(
                contextual_text=text,
                dimension=settings.VECTOR_SIZE,
            )
            return embeddings.text_embedding
        except Exception as e:
            logger.error(f"Error creating text embedding for {text}: {e}")
            raise

vertex_embedding = VertexAIEmbeddingModel()