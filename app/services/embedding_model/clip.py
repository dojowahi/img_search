# import logging
# import os

# import clip
# import numpy as np
# import torch
# from PIL import Image

# from app.core.config import settings
# from app.services.embedding_model.base import EmbeddingModel

# logger = logging.getLogger(__name__)

# class CLIPEmbeddingModel(EmbeddingModel):
#     """
#     # Implementation of the EmbeddingModel interface for the CLIP model.
#     """
#     def __init__(self):
#         """Initializes the CLIPEmbeddingModel."""
#         self.model = None
#         self.preprocess = None
#         self.device = None

#     async def initialize(self):
#         """Initializes the CLIP model."""
#         self.device = "cuda" if torch.cuda.is_available() else "cpu"
#         logger.info(f"Using device: {self.device}")
#         self.model, self.preprocess = clip.load(settings.CLIP_MODEL, device=self.device)
#         logger.info(f"CLIP model {settings.CLIP_MODEL} loaded successfully")
        
#         dummy_text = "This is a warmup text to initialize the text encoder"
#         text_tokens = clip.tokenize([dummy_text]).to(self.device)
#         with torch.no_grad():
#             text_features = self.model.encode_text(text_tokens)
#             text_features /= text_features.norm(dim=-1, keepdim=True)
#             _ = text_features.cpu().numpy()
        
#         dummy_image = torch.zeros(1, 3, 224, 224).to(self.device)
#         with torch.no_grad():
#             image_features = self.model.encode_image(dummy_image)
#             image_features /= image_features.norm(dim=-1, keepdim=True)
#             _ = image_features.cpu().numpy()
        
#         logger.info("CLIP model warmup completed successfully")

#     def create_image_embedding(self, image_path: str) -> np.ndarray:
#         """
#         Creates an image embedding using the CLIP model.

#         Args:
#             image_path (str): Path to the image.

#         Returns:
#             np.ndarray: The image embedding.
#         """
#         image = Image.open(image_path)
#         image_input = self.preprocess(image).unsqueeze(0).to(self.device)
#         with torch.no_grad():
#             image_features = self.model.encode_image(image_input)
#             image_features /= image_features.norm(dim=-1, keepdim=True)
#             embedding = image_features.cpu().numpy().flatten()
#             norm = np.linalg.norm(embedding)
#             logger.debug(f"Image embedding for {os.path.basename(image_path)}: norm={norm:.4f}, shape={embedding.shape}")
#             return embedding

#     def create_text_embedding(self, text: str) -> np.ndarray:
#         """
#         Creates a text embedding using the CLIP model.

#         Args:
#             text (str): The text to embed.

#         Returns:
#             np.ndarray: The text embedding.
#         """
#         if not text.strip():
#             text = "empty query"
#         text_tokens = clip.tokenize([text]).to(self.device)
#         with torch.no_grad():
#             text_features = self.model.encode_text(text_tokens)
#             text_features /= text_features.norm(dim=-1, keepdim=True)
#             embedding = text_features.cpu().numpy().flatten()
#             norm = np.linalg.norm(embedding)
#             logger.debug(f"Text embedding for '{text[:30]}...': norm={norm:.4f}, shape={embedding.shape}")
#             return embedding
        
# clip_embedding = CLIPEmbeddingModel()