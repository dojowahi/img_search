import json
import logging
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from moviepy.video.io.VideoFileClip import VideoFileClip
from PIL import Image

from app.core.brand import BRAND_CONFIG
from app.models.schemas import SearchResult, VideoSearchResponse
from app.services.embedding_model import get_embedding_service
from app.services.llm_service import llm_service
from app.services.storage.gcs import gcs_storage_service
from app.services.vector_db import get_vector_db_service

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


@router.post("/search_by_video_frame/")
async def video_analysis(request: Request,
    file: UploadFile = File(...), 
    limit: int = Query(3, ge=1, le=5)
):
   """ Generate tags for a video using an LLM
    
    - Takes a video
    - Calls an LLM to analyze video
    
    Returns HTML with the generated tags JSON
    
    """
   try:
        brand = request.headers.get("X-Brand", "target")
        if not file.content_type.startswith("video/"):
            logger.exception(f"File {file.filename} is not a video")
            
        # Save the uploaded file temporarily
        temp_file_path, need_cleanup = await gcs_storage_service.save_upload(file)
        vid_id = str(uuid.uuid4())
            
        # Store the image in GCS
        vid_id, gcs_path = gcs_storage_service.store_file(temp_file_path, file.filename, vid_id)
        logger.info(f"Vid path:{temp_file_path}")
        # Call the LLM to generate tags
        logger.info(f"Generating tags for video: {file.filename}")
        prompt = """You are an expert in content marketing.
                You have the ability to find best frames from a video which showcases the product being discussed.
                If there are multiple products being discussed  capture details about each one
                Consider the following rules while finding the best frame:

                - Frame should have clear focus on the product being discussed, less focus on background
                - Frame image should be high quality and bright, avoid blurry images
                - Product description: get all details that are discussed about the product in the video
                """
        prompt = """Analyze the provided video of an influencer showcasing different products. For each distinct product that is presented, identify the precise timestamp where the product is most clearly visible.

                Criteria for 'clearly visible' include:

                The product is in focus.
                The product is not significantly obscured by the influencer's hands or other objects.
                Key features or branding of the product are discernible.
                If multiple angles or presentations of the same product occur, please provide the timestamp for the instance where the product best meets these criteria. If multiple distinct products are shown, please list the timestamp for each product separately, clearly indicating which timestamp corresponds to which product (if possible to discern from the video).

                Please output your findings as a list of timestamps with brief descriptions of the product shown at that time (if identifiable).
                """
        # response_schema = {"type":"object","properties":{"video_description":{"type":"string","description":"What is this video about"},"transcribe":{"type":"string","description":"Complete audio to text transcription of the video"},"productable":{"type":"array","maxItems":3,"minItems":1,"items":{"type":"object","properties":{"name":{"type":"string","description":"Name of the product being discussed"},"timestamp":{"type":"string","description":"timestamp in the  video when the product is clearly visible"},"details":{"type":"string","description":"ALl details about the product mentioned in the video"}},"required":["name","timestamp","details"]},"description":"Table listing product details"}},"required":["video_description","productable"]}        
        fast_response_schema = {"type":"object","properties":{"video_description":{"type":"string","description":"What is this video about"},"productable":{"type":"array","maxItems":3,"minItems":1,"items":{"type":"object","properties":{"name":{"type":"string","description":"Name of the product being discussed"},"timestamp":{"type":"string","description":"timestamp in the  video when the product is clearly visible"},"details":{"type":"string","description":"ALl details about the product mentioned in the video"}},"required":["name","timestamp","details"]},"description":"Table listing product details"}},"required":["video_description","productable"]}        

        tags_json = await llm_service.video_analysis(gcs_path,prompt,fast_response_schema)
        data = json.loads(tags_json)
        total_product = len(data['productable'])

        if total_product > 1:
            pdct_dtl_1 = data['productable'][total_product -1]['details']
            pdct_tmstmp_1 = data['productable'][total_product -1]['timestamp']
            pdct_nm_1 = data['productable'][total_product -1]['name']
            video_description = data['video_description']
        else:
            pdct_dtl_1 = data['productable'][0]['details']
            pdct_tmstmp_1 = data['productable'][0]['timestamp']
            pdct_nm_1 = data['productable'][0]['name']
            video_description = data['video_description']

        with VideoFileClip(temp_file_path) as clip:
            frame = clip.get_frame(pdct_tmstmp_1)
            image = Image.fromarray(frame)
                
        frame_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        image.save(frame_file, format='JPEG')
        frame_file.close()
        frame_file_path = frame_file.name
        # Upload the frame to GCS
        frame_filename = f"{vid_id}-frame.jpg"
        frame_file_id, frame_gcs_path = gcs_storage_service.store_file(frame_file_path, frame_filename)
        
        logger.info(f"LLM output:{tags_json}") 
        logger.info(f"Frame path:{frame_file_path}") 
        logger.info(f"Frame GCS path:{frame_gcs_path}") 
        vector_db_service = get_vector_db_service()
        embedding_service = get_embedding_service()
        # Create embedding from the frame
        image_embedding = embedding_service.create_image_embedding(frame_file_path)
        frame_img_url =gcs_storage_service.get_public_url(frame_file_id, frame_filename)
        # Search for similar images
        logger.info(f"Frame Img URL:{frame_img_url}")
        search_results = vector_db_service.search_similar(
            vector=image_embedding,
            limit=limit
        )
        results = []
        for result in search_results:
            image_id = result.id
            filename = result.payload.get("filename", "unknown")
            score = result.score
            
            image_url = f"/api/v1/proxy_image/{image_id}"
            
            if image_url:
                results.append(SearchResult(
                    id=image_id,
                    filename=filename,
                    similarity_score=score,
                    image_url=image_url,
                ))
        
        results.sort(key=lambda x: x.similarity_score,reverse=True)
        # Handle HTMX request
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
            f"{brand}/partials/video_search_results.html",
            {"request": request, "results": results, "frame_img_url":frame_img_url,"brand_config": BRAND_CONFIG[brand]}
        )
        
        # # Normal API response
        return VideoSearchResponse(results=results,frame_img_url=frame_file_id)
   except Exception as e:
        logger.error(f"Error searching by video frame: {str(e)}")
        
        # If it's an HTMX request, return an HTML error message
        if "HX-Request" in request.headers:
            error_html = f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <div class="flex">
                    <div class="ml-3">
                        <p class="text-sm text-red-700">
                            Error searching: {str(e)}
                        </p>
                    </div>
                </div>
            </div>
            """
            return Response(content=error_html, media_type="text/html")
        
        # Otherwise, raise a standard FastAPI exception
        raise HTTPException(status_code=500, detail=f"Error searching: {str(e)}")
    
   finally:
        # Cleanup temporary file if needed
        if need_cleanup and temp_file_path and os.path.exists(temp_file_path):
            gcs_storage_service.cleanup_temp_file(temp_file_path)



@router.post("/room_builder/")
async def room_builder(request: Request,
    subj_img_file: UploadFile = File(...), 
    pdct_img_file: UploadFile = File(...)
):
   """ Takes in two images one of the subject and the other of the product
       And builds an image with the product in the subject
   """
   try:
        brand = request.headers.get("X-Brand", "target")
        if not (subj_img_file.content_type.startswith("image/") or pdct_img_file.content_type.startswith("image/")):
            logger.exception("File is not an image")

        temp_file_path = None
        need_cleanup = False   
        # Save the uploaded file temporarily
        subj_temp_file_path, need_cleanup = await gcs_storage_service.save_upload(subj_img_file)
        pdct_temp_file_path, need_cleanup = await gcs_storage_service.save_upload(pdct_img_file)
        desc = await llm_service.image_merge(subj_temp_file_path,pdct_temp_file_path)
        # Call the LLM to generate tags
        logger.info(f"Generating description: {desc}")

        
        # Handle HTMX request
        # if "HX-Request" in request.headers:
        #     return templates.TemplateResponse(
        #     f"{brand}/partials/video_search_results.html",
        #     {"request": request, "results": results, "frame_img_url":frame_img_url,"brand_config": BRAND_CONFIG[brand]}
        # )
        
        # # Normal API response
        return desc
   except Exception as e:
        logger.error(f"Error searching by video frame: {str(e)}")
        
        # If it's an HTMX request, return an HTML error message
        if "HX-Request" in request.headers:
            error_html = f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <div class="flex">
                    <div class="ml-3">
                        <p class="text-sm text-red-700">
                            Error searching: {str(e)}
                        </p>
                    </div>
                </div>
            </div>
            """
            return Response(content=error_html, media_type="text/html")
        
        # Otherwise, raise a standard FastAPI exception
        raise HTTPException(status_code=500, detail=f"Error searching: {str(e)}")
    
   finally:
        # Cleanup temporary file if needed
        if need_cleanup and temp_file_path and os.path.exists(temp_file_path):
            gcs_storage_service.cleanup_temp_file(temp_file_path)
