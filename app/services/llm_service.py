
import logging
from typing import Any, Dict, Optional

from google import genai
from google.genai.types import GenerateContentConfig, Part, SafetySetting
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    """Service for generating image tags using an LLM"""
    
    def __init__(self):
        self.client = genai.Client(vertexai=True, project=settings.GCP_PROJECT_ID, location=settings.GCP_REGION)
        self.safety_settings = [SafetySetting(
                                category="HARM_CATEGORY_HATE_SPEECH",
                                threshold="OFF"
                                ),SafetySetting(
                                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                                threshold="OFF"
                                ),SafetySetting(
                                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                threshold="OFF"
                                ),SafetySetting(
                                category="HARM_CATEGORY_HARASSMENT",
                                threshold="OFF"
                                )]
        
    async def generate_image_tags(self, image_url: str, prompt:str, response_schema:dict) -> Optional[Dict[str, Any]]:
        """
        Generate tags for an image using an LLM
        
        Args:
            image_url: URL of the image to generate tags for
            
        Returns:
            JSON object with tags and description
        """
        try:
            image = Part.from_uri(file_uri=image_url, mime_type="image/jpg")
            # response_schema = {"type":"object","properties":{"tagline":{"type":"string","description":"Suggest a catchy line for the product"},"Color":{"type":"string","description":"What is the main color?"},"Name":{"type":"string","description":"Suggest a name?"},"product_description":{"type":"string","description":"A detailed description of the product"}},"required":["Name","Color","tagline","product_description"]}
            # prompt = """You are an retail merchandising expert capable of describing, categorizing, and answering questions about products for a retail catalog"""
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
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
        
    async def video_analysis(self,vid_path:str,prompt:str,response_schema:str):
        
        try:
            gcs_vid_path = f"gs://{settings.GCS_BUCKET_NAME}/{vid_path}"
            logger.info(f"Analyzing vid at {gcs_vid_path}")
            video_input = Part.from_uri(mime_type="video/*",file_uri=gcs_vid_path)
        
            response = self.client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[
                        gcs_vid_path,
                        prompt,
                    ],
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )
            tags = response.text
            logger.info(f"tags:{tags}")
            return tags
        
        except Exception as e:
            logger.error(f"Error analyzing video with LLM: {str(e)}")
            return {
                "error": f"Failed to analyze Youtube URL: {str(e)}",
                "title": "Error generating timestamps",
                "description": f"There was an error generating timestamps for this {vid_path}."
            }
    

    async def image_merge(self,subject_img:str,product_img:str):
        try:
            # subject_img_bytes = Image.open(BytesIO(open(subject_img, "rb").read()))
            subject_img_pil = Image.open(subject_img)
            product_img_pil = Image.open(product_img)
            subject_desc = await self.image_qna(subject_img_pil, prompt="Describe the room in one line")
            # product_img_bytes = Image.open(BytesIO(open(product_img, "rb").read()))
            product_desc = await self.image_qna(product_img_pil, prompt="Describe product in one line")

            
            # logger.info(f"Subject:{subject_desc} and Product:{product_desc}")

            instruction_set = f"""Instructions:
                                Carefully consider the style and layout of {subject_desc}.
                                The room also includes the product {product_desc}
                                Place the product in the room in a way that enhances the overall aesthetic.
                                The placement should look natural, as if the product belongs in the room.
                                Consider factors such as lighting, color scheme, and the rug when placing the product.
                                Ensure the exact product is used without any modifications."""
            model = "gemini-2.0-flash-exp"
            contents = ["""You will be provided with: Product Image:""",
                        product_img_pil,
                        """Empty Room Image:""",
                        subject_img_pil,
                        instruction_set
                        ]
                
            generate_content_config = GenerateContentConfig(
                                                    temperature = 1,
                                                    top_p = 0.95,
                                                    max_output_tokens = 8192,
                                                    response_modalities = ["TEXT", "IMAGE"],
                                                    safety_settings = self.safety_settings
                                                    )
            response= self.client.models.generate_content(
                        model = model,
                        contents = contents,
                        config = generate_content_config)
            
            return response
        except Exception as e:
            logger.error(f"Error create image with LLM: {str(e)}")
            return {
                "error": f"Failed create image by merging: {str(e)}",
                "title": "Error generating image",
                "description": f"There was an error generating image for {product_img}."
            }

    async def image_qna(self,img:Image,prompt:str):
        try:
            response = self.client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[prompt, img],
                    config = GenerateContentConfig(
                        temperature=0.1,
                        safety_settings=self.safety_settings,
                    )
                )
            return response.text
        except Exception as e:
            logger.error(f"Error unable to do visual QnA: {str(e)}")
            return {
                "error": f"Failed to do visual QnA: {str(e)}",
                "title": "Error doing visual QnA",
                "description": f"There was an error to do visual QnA {prompt}."
            }


llm_service = LLMService()