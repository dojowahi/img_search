
import logging
from typing import Any, Dict, Optional

from google import genai
from google.genai.types import GenerateContentConfig, Part

from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    """Service for generating image tags using an LLM"""
    
    def __init__(self):
        pass
        
    async def generate_image_tags(self, image_url: str) -> Optional[Dict[str, Any]]:
        """
        Generate tags for an image using an LLM
        
        Args:
            image_url: URL of the image to generate tags for
            
        Returns:
            JSON object with tags and description
        """
        try:
            client = genai.Client(vertexai=True, project=settings.GCP_PROJECT_ID, location=settings.GCP_REGION)

            image = Part.from_uri(file_uri=image_url, mime_type="image/jpg")
            response_schema = {"type": "object", "properties": {"TagLine": {"type": "string", "description": "Suggest a tag line"}, "Color": {"type": "string", "description": "What is the main color?"}, "Name": {"type": "string", "description": "Suggest a name?"}},"required": ["Name","Color","TagLine"]}
            prompt = "Analyze this image"
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[
                    image,
                    prompt,
                ],
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )
            tags = response.text
            return tags
        
        except Exception as e:
            logger.error(f"Error generating tags with LLM: {str(e)}")
            return {
                "error": f"Failed to generate tags: {str(e)}",
                "title": "Error generating tags",
                "description": "There was an error generating tags for this image."
            }

llm_service = LLMService()