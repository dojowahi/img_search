
import logging

import numpy as np

logger = logging.getLogger(__name__)

class EmbeddingModel:
    """
    Base class for embedding models.  Defines the interface.
    """
    async def initialize(self):
        """Initializes the model.  Must be overridden by subclasses."""
        raise NotImplementedError

    def create_image_embedding(self, image_path: str) -> np.ndarray:
        """
        Creates an embedding from an image.  Must be overridden.
        """
        raise NotImplementedError

    def create_text_embedding(self, text: str) -> np.ndarray:
        """
        Creates an embedding from text.  Must be overridden.
        """
        raise NotImplementedError