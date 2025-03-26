
import logging
import random
import uuid
from typing import Any, Dict, Optional

from google import genai
from google.genai.types import (
    GenerateContentConfig,
    GoogleSearch,
    Part,
    SafetySetting,
    Tool,
)
from PIL import Image

from app.core.config import settings
from app.services.storage.gcs import gcs_storage_service

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
        self.google_search_tool = Tool(
    google_search = GoogleSearch()
)
        
    async def gemini_text(self, prompt:str,response_schema:Optional[dict] = None, system_instruction:str = None):
        try:
            if response_schema is None:
                # logger.info(f"Prompt:{prompt}")
                # logger.info(f"System instruction:{system_instruction}")
                response = self.client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[
                        prompt
                    ],
                    config=GenerateContentConfig(
                        temperature = 0,
                        system_instruction =system_instruction
                ))
                answer = response.text
                return answer
            else:
                logger.info("Schema detected")
                response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    prompt,
                ],
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema
                    ),
                )
                answer = response.text
                return answer
        
        except Exception as e:
            logger.error(f"Error response LLM: {str(e)}")
            return {
                "error": f"Failed to generate response: {str(e)}",
                "title": "Error generating  response",
                "description": f"There was an error generating grounded response for {prompt}."
            }
    
        
    async def grounded_gemini(self,image_url:str, prompt:str):
        try:
            image = Part.from_uri(file_uri=image_url, mime_type="image/*")
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    image,
                    prompt,
                ],
                config=GenerateContentConfig(
                    tools=[self.google_search_tool] ),
            )
            tags = response.text
            return tags
        
        except Exception as e:
            logger.error(f"Error grounded response LLM: {str(e)}")
            return {
                "error": f"Failed to generate grounded response: {str(e)}",
                "title": "Error generating grounded response",
                "description": f"There was an error generating grounded response for {prompt}."
            }
        
    async def generate_image_tags(self, image_url: str, prompt:str, response_schema:dict) -> Optional[Dict[str, Any]]:
        """
        Generate tags for an image using an LLM
        
        Args:
            image_url: URL of the image to generate tags for
            
        Returns:
            JSON object with tags and description
        """
        try:
            image = Part.from_uri(file_uri=image_url, mime_type="image/*")
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
    

    async def gemini_image_merge(self,subject_img:str,product_img:str):
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

    async def imagen_image_merge(self,subject_img:str,product_img:str):
        
        try:
            from PIL import Image
            # subject_img_bytes = Image.open(BytesIO(open(subject_img, "rb").read()))
            subject_img_pil = Image.open(subject_img)
            product_img_pil = Image.open(product_img)
            subject_desc = await self.image_qna(subject_img_pil, prompt="Describe the room in a few lines")
            # product_img_bytes = Image.open(BytesIO(open(product_img, "rb").read()))
            product_desc = await self.image_qna(product_img_pil, prompt="Describe product in few lines")

            
            logger.info(f"Subject:{subject_desc} and Product:{product_desc}")
          
            # logger.info(f"Room prompt:{subject_desc}")
            bkg_img_id = str(uuid.uuid4())
            # img = os.path.basename(img_path)
            output_file = f"gs://{settings.GCS_BUCKET_NAME}/{settings.GCS_BKG_IMG_PREFIX}{bkg_img_id}"
            
            from vertexai.preview.vision_models import Image, ImageGenerationModel
            model = ImageGenerationModel.from_pretrained(settings.IMAGEN_MODEL)
            base_img = Image.load_from_file(location=product_img)
            instruction_set = f"""Instructions:
                                Carefully consider the style and layout of {subject_desc}
                                Place the product in the room in a way that enhances the overall aesthetic.
                                The placement should look natural, as if the product belongs in the room.
                                Consider factors such as lighting, color scheme, when placing the product.
                                Ensure the exact product is used without any modifications."""
            images =  model.edit_image(
                base_image=base_img,
                prompt=instruction_set,
                edit_mode="product-image",
                output_gcs_uri=output_file
            )

            logger.info(f"Created output image using {len(images[0]._image_bytes)} bytes")

            virtual_img_signed_url = gcs_storage_service.find_full_bkg_img_gcs_path(output_file)
            # images[0].save(location=output_file, include_generation_parameters=False)
            # logger.info(f"Output file:{bkg_img_path}")
            return virtual_img_signed_url
        except Exception as e:
            logger.error(f"Error unable to create new image : {str(e)}")
            return {
                "error": f"Failed to do merge the images: {str(e)}",
                "title": "Error creating new image",
                "description": "There was an error in creating image."
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
        
    async def change_img_bkgnd(self,img_path:str):
        from vertexai.preview.vision_models import Image, ImageGenerationModel
        
        try:
            background_prompt = [
                    """Display a vibrant, high-resolution background illuminated by a combination of soft, diffused light and a touch of dramatic side lighting.The background consists of a clean, minimalist setting with subtle geometric patterns""",
                    """Nature's Touch Neutral beige background with a subtle gradient from a light brown to an off-white A faint, organic pattern of leaves and branches creates a natural and serene ambiance The pattern is intentionally blurred to prevent it from overpowering the product""",
                    """Modern Simplicity Clean, white background with a soft gradient from a light blue to a pale gray Minimalistic lines form an abstract, geometric pattern in the background The pattern is subtle and fades into the background, allowing the product to take center stage""",
                    """Neutral Paper with Faint Linen Texture A neutral beige background resembling paper or canvas, providing a warm and inviting backdrop. A faint linen texture adds a touch of sophistication and depth, creating a subtle visual interest. The background conveys a sense of timeless elegance and quality, reflecting Company's commitment to craftsmanship and enduring products.""",
                    """Light of the Future"*** **Minimalist Design:** Simple, flowing curves convey a sense of progress and fluidity.* **Subtle Gradient:** A subtle gradient from light blue to white creates a luminous backdrop, suggesting a bright future ahead.* **Neutral Colors:** Light blue and white provide a clean and airy neutral background.* **Subtle Pattern:** A faint geometric pattern of hexagons symbolizes technology and connectivity, reflecting Company's problem-solving nature.* **Company's Philosophy:** The flowing curves evoke a sense of optimism and a journey toward a brighter tomorrow.""",
                    ]
            prompt = random.choice(background_prompt)
            logger.info(f"Background prompt:{prompt}")
            bkg_img_id = str(uuid.uuid4())
            # img = os.path.basename(img_path)
            output_file = f"gs://{settings.GCS_BUCKET_NAME}/{settings.GCS_BKG_IMG_PREFIX}{bkg_img_id}"
            
            model = ImageGenerationModel.from_pretrained(settings.IMAGEN_MODEL)
            base_img = Image.load_from_file(location=img_path)

            images =  model.edit_image(
                base_image=base_img,
                prompt=prompt,
                edit_mode="product-image",
                output_gcs_uri=output_file
            )

            logger.info(f"Created output image using {len(images[0]._image_bytes)} bytes")

            bkg_img_signed_url = gcs_storage_service.find_full_bkg_img_gcs_path(output_file)
            # images[0].save(location=output_file, include_generation_parameters=False)
            # logger.info(f"Output file:{bkg_img_path}")
            return bkg_img_signed_url
        except Exception as e:
            logger.error(f"Error unable to create image with new background: {str(e)}")
            return {
                "error": f"Failed to do change background image: {str(e)}",
                "title": "Error creating new background",
                "description": f"There was an error in creating image {background_prompt}."
            }


llm_service = LLMService()