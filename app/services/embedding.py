import logging
import os
import tempfile
import time
import warnings

import clip
import numpy as np
import torch
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used."""

    def new_func(*args, **kwargs):
        warnings.simplefilter('always', DeprecationWarning)  # turn off filter
        warnings.warn(f"Call to deprecated function {func.__name__}.",
                      category=DeprecationWarning,
                      stacklevel=2)
        warnings.simplefilter('default', DeprecationWarning)  # reset filter
        return func(*args, **kwargs)

    new_func.__name__ = func.__name__
    new_func.__doc__ = func.__doc__
    new_func.__dict__.update(func.__dict__)
    return new_func

class EmbeddingService:
    def __init__(self):
        self.model = None
        self.preprocess = None
        self.device = None
        self._initialized = False  # Initialization flag
    
    @deprecated
    async def initialize(self):
        """Initialize the CLIP model with warmup"""
        try:
            logger.info("Starting CLIP model initialization...")
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {self.device}")
            
            # Load the model
            logger.info(f"Loading CLIP model {settings.CLIP_MODEL}...")
            self.model, self.preprocess = clip.load(settings.CLIP_MODEL, device=self.device)
            logger.info(f"CLIP model {settings.CLIP_MODEL} loaded successfully")
            
            # Perform warmup to ensure all model components are initialized
            logger.info("Performing model warmup...")
            
            # Warmup for text encoder
            dummy_text = "This is a warmup text to initialize the text encoder"
            text_tokens = clip.tokenize([dummy_text]).to(self.device)
            with torch.no_grad():
                text_features = self.model.encode_text(text_tokens)
                # Apply normalization like in regular use
                text_features /= text_features.norm(dim=-1, keepdim=True)
                # Ensure computation is complete (especially important for GPU)
                _ = text_features.cpu().numpy()
            
            # Warmup for image encoder with a blank image
            dummy_image = torch.zeros(1, 3, 224, 224).to(self.device)
            with torch.no_grad():
                image_features = self.model.encode_image(dummy_image)
                # Apply same normalization
                image_features /= image_features.norm(dim=-1, keepdim=True)
                _ = image_features.cpu().numpy()
            
            logger.info("Model warmup completed successfully")
            
            # Test the embeddings are in the same space
            similarity = self.validate_embeddings()
            if similarity is None or np.isnan(similarity):
                logger.warning("Embedding validation failed - text and image searches might not work together")
            else:
                logger.info(f"Embedding validation passed with similarity: {similarity}")
                
            self._initialized = True  # Set the initialized flag
            logger.info("CLIP model initialization complete")
        except Exception as e:
            logger.error(f"Error initializing CLIP model: {e}")
            # Re-raise to ensure the startup fails if model can't be loaded
            raise
        
    @deprecated
    def _check_initialized(self):
        """Check if the service is initialized"""
        if not self._initialized:
            logger.error("EmbeddingService used before initialization")
            raise RuntimeError("EmbeddingService must be initialized before use")
    
    @deprecated    
    def create_image_embedding(self, image_path):
        """Create an embedding from an image"""
        self._check_initialized()
        try:
            # Open and preprocess the image
            image = Image.open(image_path)
            image_input = self.preprocess(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                # Get features
                image_features = self.model.encode_image(image_input)
                
                # Apply same normalization as text embeddings
                image_features /= image_features.norm(dim=-1, keepdim=True)
                
                # Convert to numpy
                embedding = image_features.cpu().numpy().flatten()
                
                # Log norm for comparison with text embeddings
                norm = np.linalg.norm(embedding)
                logger.debug(f"Image embedding for {os.path.basename(image_path)}: norm={norm:.4f}, shape={embedding.shape}")
                
                return embedding
        except Exception as e:
            logger.error(f"Error creating image embedding for {image_path}: {e}")
            raise
    
    @deprecated   
    def create_text_embedding(self, text, max_retries=3):
        """Create an embedding from text with retry logic"""
        self._check_initialized()
        
        for attempt in range(max_retries):
            try:
                # Important: Use the same text normalization as CLIP uses internally
                if not text.strip():
                    text = "empty query"  # Handle empty strings
                    
                # Normalize and tokenize text
                text_tokens = clip.tokenize([text]).to(self.device)
                
                with torch.no_grad():
                    # Extract features and normalize
                    text_features = self.model.encode_text(text_tokens)
                    
                    # Apply model's own normalization (important!)
                    text_features /= text_features.norm(dim=-1, keepdim=True)
                    
                    # Convert to numpy
                    embedding = text_features.cpu().numpy().flatten()
                    
                    # Log some details to diagnose
                    norm = np.linalg.norm(embedding)
                    logger.debug(f"Text embedding for '{text[:30]}...': norm={norm:.4f}, shape={embedding.shape}")
                    
                    # Log success if we had retries
                    if attempt > 0:
                        logger.info(f"Text embedding created successfully after {attempt+1} attempts")
                    
                    return embedding
                    
            except Exception as e:
                logger.warning(f"Text embedding attempt {attempt+1} failed: {e}")
                # Short sleep before retry
                time.sleep(0.5 * (attempt + 1))
                
                # On last attempt, try to reinitialize the model
                if attempt == max_retries - 1:
                    logger.warning("Attempting to reinitialize CLIP model")
                    try:
                        self.model, self.preprocess = clip.load(settings.CLIP_MODEL, device=self.device)
                    except Exception as reinit_error:
                        logger.error(f"Model reinitialization failed: {reinit_error}")
        
        # If we get here, all retries failed
        logger.error(f"Failed to create text embedding after {max_retries} attempts")
        raise RuntimeError(f"Failed to create text embedding for: {text[:30]}...")
    
    @deprecated
    def validate_embeddings(self):
        """Test if text and image embeddings are in the same space"""
        try:
            # Create a test text embedding
            text = "a photo of a cat"
            text_emb = self.create_text_embedding(text)
            
            # Create a blank test image embedding
            temp_dir = tempfile.gettempdir()
            test_img_path = os.path.join(temp_dir, "test_cat.jpg")
            
            # Create a simple test image (or use a built-in one)
            try:
                # Try to create a blank image
                img = Image.new('RGB', (224, 224), color=(100, 100, 100))
                img.save(test_img_path)
                img_emb = self.create_image_embedding(test_img_path)
                
                # Calculate similarity (should be non-zero even for random image)
                similarity = np.dot(text_emb, img_emb) / (np.linalg.norm(text_emb) * np.linalg.norm(img_emb))
                
                # Log and return the result
                logger.info(f"Embedding validation - text/image similarity: {similarity}")
                return similarity
            finally:
                if os.path.exists(test_img_path):
                    os.unlink(test_img_path)
                    
        except Exception as e:
            logger.error(f"Embedding validation failed: {e}")
            return None

# Create a global instance
# embedding_service = EmbeddingService()