import logging
import os
import time
from pathlib import Path

import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from app.models.schemas import SearchResponse, SearchResult
from app.services.embedding import embedding_service
from app.services.storage.gcs import gcs_storage_service
from app.services.vector_db import get_vector_db_service

APP_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/search_by_text/", response_model=SearchResponse)
async def search_by_text(
    request: Request,
    query: str, 
    limit: int = Query(5, ge=1, le=100)
):
    """
    Search for images similar to a text query
    """
    try:
        vector_db_service = get_vector_db_service()
        
        # Log the search query
        logger.info(f"Text search request: '{query}' with limit {limit}")
        
        # Create text embedding with retries
        start_time = time.time()
        text_embedding = embedding_service.create_text_embedding(query, max_retries=3)
        logger.info(f"Text embedding created in {time.time() - start_time:.2f}s")
        
        # Normalize the text embedding (critical for cosine similarity)
        vector_norm = np.linalg.norm(text_embedding)
        if vector_norm > 0:
            text_embedding = text_embedding / vector_norm
            
        logger.info(f"Created text embedding with shape {text_embedding.shape}, norm: {vector_norm}")
        
        # Search for similar images with normalized embedding
        search_results = vector_db_service.search_similar(
            vector=text_embedding,
            limit=limit
        )
        
        # Log search results
        logger.info(f"Text search returned {len(search_results)} results in {time.time() - start_time:.2f}s")
        if search_results:
            top_score = search_results[0].score if search_results else 0
            logger.info(f"Top result score: {top_score}")
        
        # Prepare results
        results = []
        for result in search_results:
            image_id = result.id
            filename = result.payload.get("filename", "unknown")
            score = result.score
            
            # gcs_path = gcs_storage_service.get_file_path(image_id, filename)
            # if gcs_path:
            #     image_url = gcs_storage_service.get_fresh_signed_url(gcs_path)
            # else:
            #     image_url = None
            image_url = f"/api/v1/proxy_image/{image_id}"
            
            if image_url:
                results.append(SearchResult(
                    id=image_id,
                    filename=filename,
                    similarity_score=score,
                    image_url=image_url
                ))
        
        # Handle HTMX request
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
                "partials/search_results.html",
                {"request": request, "results": results}
            )
        
        # Normal API response
        return SearchResponse(results=results)
    
    except Exception as e:
        logger.error(f"Error searching by text: {str(e)}")
        
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
    

@router.post("/search_by_image/", response_model=SearchResponse)
async def search_by_image(
    request: Request,
    file: UploadFile = File(...), 
    limit: int = Query(5, ge=1, le=100)
):
    """
    Search for images similar to an uploaded image
    
    - Takes an image file
    - Creates an image embedding using CLIP
    - Searches for similar image embeddings in the vector database
    
    Returns a list of similar images, sorted by similarity score
    """
    temp_file_path = None
    need_cleanup = False
    
    try:
        vector_db_service = get_vector_db_service()
        
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400, 
                detail=f"File {file.filename} is not an image"
            )
        
        # Save the uploaded file temporarily
        temp_file_path, need_cleanup = await gcs_storage_service.save_upload(file)
        
        # Create embedding
        image_embedding = embedding_service.create_image_embedding(temp_file_path)
        
        # Search for similar images
        search_results = vector_db_service.search_similar(
            vector=image_embedding,
            limit=limit
        )
        
        # Prepare results
        results = []
        for result in search_results:
            image_id = result.id
            filename = result.payload.get("filename", "unknown")
            score = result.score
            
            # gcs_path = gcs_storage_service.get_file_path(image_id, filename)
            # if gcs_path:
            #     image_url = gcs_storage_service.get_fresh_signed_url(gcs_path)
            # else:
            #     image_url = None

            image_url = f"/api/v1/proxy_image/{image_id}"
            
            if image_url:
                results.append(SearchResult(
                    id=image_id,
                    filename=filename,
                    similarity_score=score,
                    image_url=image_url
                ))
        
        results.sort(key=lambda x: x.similarity_score,reverse=True)
        # Handle HTMX request
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
                "partials/search_results.html",
                {"request": request, "results": results}
            )
        
        # Normal API response
        return SearchResponse(results=results)
    
    except Exception as e:
        logger.error(f"Error searching by image: {str(e)}")
        
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

# Optional endpoint to get search stats
@router.get("/search_stats/")
async def get_search_stats(request: Request):
    """
    Get statistics about the search system
    """
    try:
        vector_db_service = get_vector_db_service()
        
        # Return basic stats as HTML or JSON based on request type
        stats = {
            "vector_db_type": vector_db_service.get_name(),
            "embedding_model": "CLIP ViT-B/32",
            "status": "healthy"
        }
        
        if "HX-Request" in request.headers:
            return templates.TemplateResponse(
                "partials/search_stats.html",
                {"request": request, "stats": stats}
            )
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting search stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")
    
@router.get("/debug_search")
async def debug_search(query: str = "test", limit: int = 5):
    """Debug endpoint to test raw search queries"""
    vector_db_service = get_vector_db_service()
    
    # Create the text embedding
    text_embedding = embedding_service.create_text_embedding(query)
    norm = np.linalg.norm(text_embedding)
    logger.info(f"DEBUG Text embedding norm: {norm}")
    
    # Normalize explicitly
    if norm > 0:
        text_embedding = text_embedding / norm
    
    # Log vector stats
    result = {
        "query": query,
        "vector_db": vector_db_service.get_name(),
        "vector_stats": {
            "shape": text_embedding.shape,
            "norm": float(np.linalg.norm(text_embedding)),
            "mean": float(np.mean(text_embedding)),
            "min": float(np.min(text_embedding)),
            "max": float(np.max(text_embedding))
        }
    }
    
    if vector_db_service.get_name() == "postgres":
        # Test direct SQL query
        try:
            with vector_db_service.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM image_embeddings")
                    count = cur.fetchone()[0]
                    result["db_stats"] = {"total_rows": count}
                    
                    # Try a simple cosine similarity query
                    if count > 0:
                        vector_list = text_embedding.tolist()
                        cur.execute(
                            """
                            SELECT id, filename, 
                                   1 - (embedding <=> %s::vector) as similarity
                            FROM image_embeddings
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s
                            """,
                            (vector_list, vector_list, limit)
                        )
                        
                        rows = cur.fetchall()
                        result["direct_sql_results"] = [{
                            "id": row[0],
                            "filename": row[1],
                            "score": float(row[2])
                        } for row in rows]
        except Exception as e:
            result["sql_error"] = str(e)
    
    # Try regular search as well
    try:
        search_results = vector_db_service.search_similar(
            vector=text_embedding,
            limit=limit
        )
        result["api_results"] = [{
            "id": item.id,
            "filename": item.payload.get("filename", "unknown"),
            "score": item.score
        } for item in search_results]
    except Exception as e:
        result["api_error"] = str(e)
    
    return result
