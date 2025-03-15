import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.brand import BRAND_CONFIG
from app.services.llm_service import llm_service
from app.services.storage.gcs import gcs_storage_service

APP_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize templates with correct path
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@router.post("/generate_tags/{image_id}", response_class=HTMLResponse)
async def generate_tags(request: Request, image_id: str, simple: int =1):
    """
    Generate tags for an image using an LLM
    
    - Takes an image ID
    - Retrieves the image URL from storage
    - Calls an LLM to generate tags based on the image
    
    Returns HTML with the generated tags JSON
    """
    brand = request.headers.get("X-Brand", "target")
    try:
        # Get the GCS URL for the image
        image_url = gcs_storage_service.get_public_url(image_id)
        logger.info(f"Image URL for tag generation:{image_url}")
        if not image_url:
            if "HX-Request" in request.headers:
                return templates.TemplateResponse(
                    "partials/image_tags.html",
                    {"request": request, "error": "Image not found"}
                )
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Call the LLM to generate tags
        logger.info(f"Generating tags for image: {image_id}")
        prompt = """You are an retail merchandising expert capable of describing, categorizing, and answering questions about products for a retail catalog"""
        
        if simple==1:
            response_schema = {"type":"object","properties":{"tagline":{"type":"string","description":"Suggest a catchy line for the product"},"Color":{"type":"string","description":"What is the main color?"},"Name":{"type":"string","description":"Suggest a name?"},"product_description":{"type":"string","description":"A detailed description of the product"}},"required":["Name","Color","tagline","product_description"]}
        else:
            response_schema={"type":"object","properties":{"product_category":{"type":"string","description":"Suggest the top category and its top 50 to 80 retail selling and supply chain attributes from the image.The category hierarchy must be 4 levels deep, separated by >  character"},"attribute_table":{"type":"array","items":{"type":"object","properties":{"attr_name":{"type":"string","description":"Name of the product attribute which will be analyzed"},"attr_desc":{"type":"string","description":"Describe the attribute"},"value_range":{"type":"string","description":"Is a list of values the attribute can have.Display it as array of string"}},"required":["attr_desc","attr_name","value_range"]},"description":"Table listing product attributes and details."}},"required":["product_category","attribute_table"]}

        tags_json = await llm_service.generate_image_tags(image_url,prompt,response_schema)
    
        
        # Return the tags template
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
                f"{brand}/partials/image_tags.html",
                {"request": request, "tags": tags_json,"brand_config": BRAND_CONFIG[brand]}
            )
            
        # If it's not an HTMX request, return JSON
        return tags_json
        
    except Exception as e:
        logger.error(f"Error generating tags: {str(e)}")
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
                f"{brand}/partials/image_tags.html",
                {"request": request, "error": f"Error generating tags: {str(e)}"}
            )
        raise HTTPException(status_code=500, detail=f"Error generating tags: {str(e)}")


@router.post("/yt_analysis", response_class=HTMLResponse)
async def yt_analysis(request: Request, yt_url: str):
    """
    Generate tags for an youtube url using an LLM
    
    - Takes a Youtube URL
    - Calls an LLM to generate tags based on the image
    
    Returns HTML with the generated tags JSON
    """
    try:
        if not yt_url:
            if "HX-Request" in request.headers:
                return templates.TemplateResponse(
                    "partials/image_tags.html",
                    {"request": request, "error": "URL not found"}
                )
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Call the LLM to generate tags
        logger.info(f"Generating tags for image: {yt_url}")
        prompt = """You are an expert in content marketing.
                You have the ability to find best frames from a video which showcases the product clearly.
                Your task is to find the best frame from a given video along with sclearly show the product/brand that is being discussed in the video.
                Consider the following rules while finding the best frame:

                - Frame should have clear focus on the product being discussed, less focus on background
                - Frame image should be high quality and bright, avoid blurry images
                """
        response_schema={"type":"object","properties":{"timestamp":{"type":"string","description":"timestamp in the youtube video when the product is clearly visible"},"product":{"type":"string","description":"Name of product and brand"}},"required":["timestamp","product"]}

        tags_json = await llm_service.video_analysis(yt_url,prompt,response_schema)
    
        
        # Return the tags template
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
                "partials/image_tags.html",
                {"request": request, "tags": tags_json}
            )
            
        # If it's not an HTMX request, return JSON
        return tags_json
        
    except Exception as e:
        logger.error(f"Error generating tags: {str(e)}")
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
                "partials/image_tags.html",
                {"request": request, "error": f"Error generating tags: {str(e)}"}
            )
        raise HTTPException(status_code=500, detail=f"Error generating tags: {str(e)}")
