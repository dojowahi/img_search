import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.models.schemas import HealthResponse, UploadResponse, UploadResult
from app.services.embedding import embedding_service
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

@router.post("/upload_images/", response_model=UploadResponse)
async def upload_images(request: Request, files: List[UploadFile] = File(...)):
    """
    Upload multiple images, create embeddings, and store in vector DB
    
    - Takes a list of image files
    - Creates embeddings using CLIP
    - Stores images in Google Cloud Storage
    - Stores embeddings in the configured vector database
    
    Returns a list of uploaded image IDs and their URLs
    """
    vector_db_service = get_vector_db_service()
    uploaded_ids = []
    
    for file in files:
        temp_file_path = None
        need_cleanup = False
        
        try:
            # Validate file type
            if not file.content_type.startswith("image/"):
                logger.warning(f"File {file.filename} is not an image")
                continue
            
            # Save the uploaded file temporarily
            temp_file_path, need_cleanup = await gcs_storage_service.save_upload(file)
            
            # Create embedding
            embedding = embedding_service.create_image_embedding(temp_file_path)
            
            # Generate a unique ID for the image
            image_id = str(uuid.uuid4())
            
            # Store the image in GCS
            image_id, gcs_path = gcs_storage_service.store_file(temp_file_path, file.filename, image_id)
            need_cleanup = False  # File has been moved, no need to clean up
            
            # Store the embedding and metadata in vector DB
            vector_db_service.store_embedding(
                id=image_id,
                vector=embedding,
                metadata={
                    "filename": file.filename,
                    "upload_time": time.time(),
                    "gcs_path": gcs_path
                }
            )
            
            uploaded_ids.append(UploadResult(id=image_id, filename=file.filename, url=gcs_path))
            logger.info(f"Successfully uploaded and processed {file.filename}")
        
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {str(e)}")
            
            # If it's an HTMX request, add this error to the results
            if "HX-Request" in request.headers:
                continue  # Skip the file but continue processing others
            
            raise HTTPException(status_code=500, detail=f"Error processing {file.filename}: {str(e)}")
        
        finally:
            # Cleanup temporary file if needed
            if need_cleanup and temp_file_path and os.path.exists(temp_file_path):
                gcs_storage_service.cleanup_temp_file(temp_file_path)
    
    # Handle HTMX request
    if "HX-Request" in request.headers:
        # If no files were processed successfully
        if len(uploaded_ids) == 0:
            error_html = """
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                <div class="flex">
                    <div class="ml-3">
                        <p class="text-sm text-red-700">
                            No images were uploaded successfully. Please check that you selected valid image files.
                        </p>
                    </div>
                </div>
            </div>
            """
            return Response(content=error_html, media_type="text/html")
        
        return templates.TemplateResponse(
            "partials/upload_results.html",
            {"request": request, "uploaded_images": uploaded_ids}
        )
    
    # Normal API response
    return UploadResponse(uploaded_images=uploaded_ids)

@router.post("/upload_folder/", response_model=UploadResponse)
async def upload_folder(request: Request, files: List[UploadFile] = File(...)):
    """
    Upload a folder of images
    
    - Similar to upload_images but intended for directory uploads
    - Processes all valid image files from the uploaded directory
    - Skips non-image files
    
    Returns a list of uploaded image IDs and their URLs
    """
    # Filter out any non-image files first
    image_files = [file for file in files if file.content_type.startswith("image/")]
    
    # Log information about the upload
    folder_name = files[0].filename.split('/')[0] if files and '/' in files[0].filename else "Unknown"
    logger.info(f"Processing folder upload: {folder_name} with {len(image_files)} image files")
    
    # Reuse the existing upload_images function
    return await upload_images(request=request, files=image_files)



@router.get("/proxy_image/{image_id}")
async def proxy_image(image_id: str, request: Request):
    """
    Proxy endpoint that serves GCS images directly through the application
    """
    try:
        # Get vector DB service to find metadata
        vector_db_service = get_vector_db_service()
        
        # Try to get metadata if available
        metadata = None
        try:
            metadata = vector_db_service.get_metadata_by_id(image_id)
        except:
            pass
        
        # Find the GCS path
        gcs_path = None
        if metadata and "gcs_path" in metadata:
            gcs_path = metadata["gcs_path"]
        
        if not gcs_path:
            # Find by listing objects with prefix
            blobs = list(gcs_storage_service.client.list_blobs(
                gcs_storage_service.bucket_name, 
                prefix=f"{gcs_storage_service.prefix}{image_id}_", 
                max_results=1
            ))
            
            if blobs:
                gcs_path = blobs[0].name
        
        if not gcs_path:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Download the blob
        blob = gcs_storage_service.bucket.blob(gcs_path)
        content = blob.download_as_bytes()
        
        # Determine content type based on filename
        filename = blob.name.split('/')[-1].lower()
        if filename.endswith('.jpg') or filename.endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif filename.endswith('.png'):
            content_type = 'image/png'
        elif filename.endswith('.gif'):
            content_type = 'image/gif'
        elif filename.endswith('.webp'):
            content_type = 'image/webp'
        else:
            content_type = 'application/octet-stream'
        
        # Return the image directly
        return Response(content=content, media_type=content_type)
    except Exception as e:
        logger.error(f"Error proxying image: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving image: {str(e)}")
    

@router.get("/get_image/{image_id}")
async def get_image(image_id: str, request: Request):
    """
    Retrieve an image by its ID
    """
    # Get the vector DB service
    vector_db_service = get_vector_db_service()
    
    try:
        # Get the object path from database
        # This requires implementing a method to get metadata by ID
        metadata = None
        try:
            # If you have a method to get metadata by ID
            metadata = vector_db_service.get_metadata_by_id(image_id)
        except:
            pass
        
        # Find the GCS object path
        object_path = None
        if metadata and "gcs_path" in metadata:
            object_path = metadata["gcs_path"]
        
        # Generate a fresh signed URL if we have the path
        if object_path:
            fresh_url = gcs_storage_service.get_fresh_signed_url(object_path)
            return RedirectResponse(url=fresh_url)
        
        # Fallback to the old method if needed
        public_url = gcs_storage_service.get_public_url(image_id)
        if public_url:
            return RedirectResponse(url=public_url)
    except Exception as e:
        logger.error(f"Error getting image: {e}")
    
    raise HTTPException(status_code=404, detail="Image not found")

@router.post("/generate_tags/{image_id}", response_class=HTMLResponse)
async def generate_tags(request: Request, image_id: str, simple: int =1):
    """
    Generate tags for an image using an LLM
    
    - Takes an image ID
    - Retrieves the image URL from storage
    - Calls an LLM to generate tags based on the image
    
    Returns HTML with the generated tags JSON
    """
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

@router.post("/bulk_upload/")
async def bulk_upload(request: Request, file: UploadFile = File(...)):
    """
    Bulk upload embeddings from a JSON file
    """
    try:
        # Ensure we're using PostgreSQL
        vector_db_service = get_vector_db_service()
        if vector_db_service.get_name() != "postgres":
            raise HTTPException(
                status_code=400,
                detail="Bulk upload is only supported for PostgreSQL"
            )
        
        # Parse the JSON file
        content = await file.read()
        data = json.loads(content)
        
        if not isinstance(data, list):
            raise HTTPException(
                status_code=400,
                detail="Expected a JSON array of image data"
            )
        
        # Process each item
        successful = 0
        failed = 0
        embeddings_batch = []
        
        for i, item in enumerate(data):
            try:
                # Show progress for large batches
                if i % 10 == 0:
                    logger.info(f"Processing item {i+1}/{len(data)}")
                
                image_path = item.get("image_path")
                if not image_path:
                    logger.warning(f"Skipping item {i+1}: Missing image_path")
                    failed += 1
                    continue
                
                # Check if file exists
                if not os.path.exists(image_path):
                    logger.warning(f"Skipping item {i+1}: File not found at {image_path}")
                    failed += 1
                    continue
                
                # Generate ID if not provided
                image_id = item.get("id", str(uuid.uuid4()))
                
                # Create embedding
                embedding = embedding_service.create_image_embedding(image_path)
                
                # Prepare metadata
                filename = os.path.basename(image_path)
                
                # Store image in GCS to get URL (if GCS is configured)
                gcs_url = None
                try:
                    _, gcs_url = gcs_storage_service.store_file(image_path, filename, image_id)
                    logger.info(f"Stored image {i+1} in GCS: {gcs_url}")
                except Exception as e:
                    logger.warning(f"Error storing image {i+1} in GCS: {e}")
                
                # Add metadata 
                metadata = item.get("metadata", {})
                metadata.update({
                    "filename": filename,
                    "upload_time": time.time(),
                    "original_path": image_path
                })
                
                # Add GCS URL if available
                if gcs_url:
                    metadata["gcs_url"] = gcs_url
                
                # Add to batch
                embeddings_batch.append({
                    "id": image_id,
                    "vector": embedding,
                    "metadata": metadata
                })
                
                successful += 1
                
            except Exception as e:
                logger.error(f"Error processing item {i+1}: {e}")
                failed += 1
        
        # Store embeddings in batch
        if embeddings_batch:
            logger.info(f"Saving batch of {len(embeddings_batch)} embeddings to database")
            vector_db_service.bulk_store_embeddings(embeddings_batch)
        
        return {
            "status": "complete",
            "successful": successful,
            "failed": failed,
            "total": len(data)
        }
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON format"
        )
    except Exception as e:
        logger.error(f"Error in bulk upload: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing bulk upload: {str(e)}"
        )

@router.get("/status")
async def check_status():
    """Check if all services are properly initialized"""
    try:
        # Check embedding service (by accessing the flag directly - not ideal but simple)
        embedding_initialized = getattr(embedding_service, "_initialized", False)
        
        # Check storage service
        storage_initialized = hasattr(gcs_storage_service, "bucket") and gcs_storage_service.bucket is not None
        
        # Check vector DB service
        vector_db_service = get_vector_db_service()
        if vector_db_service.get_name() == "postgres":
            # For Postgres, check if connection works
            vector_db_initialized = False
            try:
                with vector_db_service.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        vector_db_initialized = True
            except:
                vector_db_initialized = False
        else:
            # For Chroma, just check if collection exists
            vector_db_initialized = hasattr(vector_db_service, "collection") and vector_db_service.collection is not None
        
        return {
            "status": "ready" if all([embedding_initialized, storage_initialized, vector_db_initialized]) else "not_ready",
            "services": {
                "embedding": "ready" if embedding_initialized else "not_ready",
                "storage": "ready" if storage_initialized else "not_ready",
                "vector_db": "ready" if vector_db_initialized else "not_ready"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
    
@router.post("/clear_database")
async def clear_database(request: Request):
    """
    Clear all data from the ChromaDB database
    
    - Removes all embeddings and metadata
    - Provides a clean slate for new uploads
    
    Returns success or error message
    """
    try:
        # Get vector database service
        vector_db_service = get_vector_db_service()
        
        # Check if it's ChromaDB
        if vector_db_service.get_name() != "chroma":
            return templates.TemplateResponse(
                "partials/action_result.html",
                {
                    "request": request, 
                    "success": False,
                    "message": "This operation is only supported for ChromaDB"
                }
            )
        
        # Clear the database
        # Access the collection directly for ChromaDB
        if hasattr(vector_db_service, 'collection') and vector_db_service.collection:
            # Get all IDs to delete
            try:
                # Try to get all IDs
                query_result = vector_db_service.collection.query(
                    query_embeddings=[[0] * vector_db_service.vector_size],  # Dummy query
                    n_results=10000  # Get as many as possible
                )
                
                if query_result and 'ids' in query_result and len(query_result['ids']) > 0:
                    all_ids = query_result['ids'][0]
                    
                    # Delete all documents if IDs found
                    if all_ids:
                        vector_db_service.collection.delete(ids=all_ids)
                        logger.info(f"Cleared {len(all_ids)} documents from ChromaDB")
                    else:
                        logger.info("No documents found to delete")
                else:
                    # Alternative: reset the collection
                    vector_db_service.collection.delete(where={})
                    logger.info("Cleared ChromaDB using delete where")
            except Exception as inner_e:
                logger.error(f"Error during collection query: {str(inner_e)}")
                # Last resort: delete and recreate collection
                try:
                    # Get collection name
                    collection_name = vector_db_service.collection_name
                    # Delete collection
                    vector_db_service.client.delete_collection(collection_name)
                    # Recreate empty collection
                    vector_db_service.collection = vector_db_service.client.create_collection(
                        name=collection_name,
                        metadata={"description": "Image embeddings from CLIP model"}
                    )
                    logger.info(f"Recreated ChromaDB collection: {collection_name}")
                except Exception as recreation_e:
                    logger.error(f"Error recreating collection: {str(recreation_e)}")
                    raise
        else:
            logger.warning("Could not access ChromaDB collection directly")
            raise ValueError("ChromaDB collection not accessible")
        
        # Return success response
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
                "partials/action_result.html",
                {
                    "request": request, 
                    "success": True,
                    "message": "Database cleared successfully!"
                }
            )
        
        # Regular API response
        return {"status": "success", "message": "Database cleared successfully"}
        
    except Exception as e:
        logger.error(f"Error clearing database: {str(e)}")
        
        # HTMX response
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
                "partials/action_result.html",
                {
                    "request": request, 
                    "success": False,
                    "message": f"Error clearing database: {str(e)}"
                }
            )
        
        # API response
        raise HTTPException(status_code=500, detail=f"Error clearing database: {str(e)}")

@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    Health check endpoint
    
    Returns service status and configuration information
    """
    vector_db = get_vector_db_service()
    
    health_data = HealthResponse(
        status="healthy", 
        timestamp=time.time(),
        vector_db_type=vector_db.get_name(),
        gcp_project=settings.GCP_PROJECT_ID
    )
    
    # For HTMX requests, return HTML
    if "HX-Request" in request.headers:
        return templates.TemplateResponse(
            "partials/health_status.html",
            {"request": request, "health": health_data.dict()}
        )
    
    # For API requests, return JSON
    return health_data
