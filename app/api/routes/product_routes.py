import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.services.llm_service import llm_service
from app.services.shopping.product_search import target_service

APP_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")
import html

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=TEMPLATES_DIR)
# Create router
router = APIRouter() # Update this path to your templates directory

def decode_html_entities(s):
    """Decodes HTML entities in a string."""
    return html.unescape(s)

# Add the filter to the Jinja2 environment
templates.env.filters["decode_html"] = decode_html_entities

@router.get("/search/")
async def search_products_endpoint(request: Request, query: str,storeId:str, count:int =3):

    brand = request.headers.get("X-Brand", "target")

    if not query.strip():
        return templates.TemplateResponse(
            f"{brand}/partials/product_results.html", 
            {"request": request, "products": [], "error": "Please enter a search keyword"}
        )
    
    try:
        # Attempt to get products from the service
        logger.info(f"Store from UI:{storeId}")
        results = target_service.search_products(query, str(count),str(storeId))
        
        # Validate response structure
        if not results:
            logger.warning(f"Empty results returned for keyword: '{query}'")
            return templates.TemplateResponse(
                f"{brand}/partials/product_results.html", 
                {"request": request, "products": [], "error": f"No results found at {storeId} for '{query}'"}
            )
            
        if not isinstance(results, dict) or 'data' not in results:
            logger.error(f"Unexpected response format: {type(results)}")
            return templates.TemplateResponse(
                f"{brand}/partials/product_results.html", 
                {"request": request, "products": [], "error": "Unexpected response format from service"}
            )
            
        # Extract products from response
        products_data = results.get('data', {}).get('search', {}).get('products', [])
        # logger.info(f"Products Data :{products_data}")

        if not products_data:
            logger.info(f"No products found for keyword: '{query}'")
            return templates.TemplateResponse(
                f"{brand}/partials/product_results.html", 
                {"request": request, "products": [], "error": f"No products found at {storeId} for '{query}'"}
            )
        
        # Process product data
        products = []
        for product in products_data:
            try:
                product_info = target_service.extract_product_info(product)
                
                if product_info:
                    products.append(product_info)
                    # logger.info(f"Info***********$$$$$$#########:{product_info}")
            except Exception as e:
                logger.error(f"Error processing product: {e}")
        
        if not products:
            return templates.TemplateResponse(
                f"{brand}/partials/product_results.html", 
                {"request": request, "products": [], "error": "Could not extract product information"}
            )
            
        logger.info(f"Found {len(products)} products for keyword: '{query}'")
        
        
        return templates.TemplateResponse(
            f"{brand}/partials/product_results.html", 
            {"request": request, "products": products,"storeId":storeId}
        )
        
        
    except Exception as e:
        logger.exception(f"Error searching for products with keyword '{query}': {str(e)}")
        return templates.TemplateResponse(
            f"{brand}/partials/product_results.html", 
            {"request": request, "products": [], "error": "An error occurred during search. Please try again."}
        )

@router.get("/chat-product/{tcin}")
async def get_product_details_endpoint(request: Request,tcin:str,storeId:str = Query(None)):
    try:
        logger.info(f"Store from chat product:{storeId}")
        brand = request.headers.get("X-Brand", "target")
        details = target_service.get_product_details(tcin,store_id=storeId)
        prod_specific_info = target_service.extract_product_details(details)
        # logger.info(f"Prod Info :{prod_specific_info}")
        # logger.info(f"TCIN details:  {details}")
        # details = json.loads(details)
        
        prompt = f"""Use the product details to generate a FAQ. Product details:{prod_specific_info} """
        response_schema = {"type":"object","properties":{"FAQ":{"type":"array","maxItems":5,"minItems":5,"items":{"type":"object","properties":{"Question":{"type":"string","description":"Generate a single question based on product details"},"Answer":{"type":"string","description":"Generate an answer for the question based on product details"}},"description":"Generate question and answer based on the product details"},"required":["Question","Answer"]}},"required":["FAQ"]}
        # response_schema = {"type":"object","properties":{"ProductText":{"type":"string","description":"ANalyze the JSON which is part of the prompt and convert it to a coherent report with all the details. No details in the JSON should be skipped"},"FAQ":{"type":"array","maxItems":5,"minItems":5,"items":{"type":"object","properties":{"Question":{"type":"string"},"Answer":{"type":"string"}},"description":"Generate questions and answers based on the product details"},"required":["Question","Answer"]}},"required":["FAQ","ProductText"]}        
        response = await llm_service.gemini_text(prompt=prompt,response_schema=response_schema)
        # faq_data = {
        #     "FAQ": [
        #         {"Question": "What is the return policy for this item?"},
        #         {"Question": "What material is this dress made of?"},
        #         {"Question": "What sizes are available for this dress?"},
        #         {"Question": "How do I care for this dress?"},
        #         {"Question": "Is this dress eligible for financing options?"}
        #     ]
        # }
        faq_data = json.loads(response)
        logger.info(f"FAQ:{faq_data}")
        response = templates.TemplateResponse(
            f"{brand}/partials/chat_modal.html", 
            {
                "request": request, 
                "tcin": tcin, 
                "faqs": faq_data["FAQ"],
                # "prod_specific_info": prod_specific_info,
                "storeId": storeId
            }
        )
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response
    
    except Exception as e:
        logger.error(f"Error in chat-product endpoint: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            f"{brand}/partials/chat_modal.html", 
            {"request": request, "faqs": [], "error": "An error occurred during chatting. Please try again."}
        )

@router.get("/chat-message", response_class=HTMLResponse)
async def chat_message(question: str = Query(...), tcin: str = Query(...),storeId: str = Query(...)):
    try:
        logger.info(f"Store in FAQ:{storeId}")
        details = target_service.get_product_details(tcin,store_id=storeId)
        prod_specific_info = target_service.extract_product_details(details)
        prompt = f"""Answer this question {question} from these product details:{prod_specific_info}.
        If answer cannot be found DO NOT MAKE UP an answer, just say No information available """

        answer = await llm_service.gemini_text(prompt=prompt)

        response_content = f"{answer}</p>"
        return Response(content=response_content, media_type="text/html")
    except Exception as e:
        logger.info(f"An error occurred: {e}")
        return Response(content=f"<p>Error loading message: {e}</p>", media_type="text/html")

# @router.get("/chat-message", response_class=HTMLResponse)
# async def chat_message(question: str = Query(None), tcin: str = Query(...)):
#     try:
#         response_content = f"<p>Received question: {question} for tcin: {tcin}</p>"
#         return HTMLResponse(content=response_content)
#     except Exception as e:
#         logger.info(f"An error occurred: {e}")
#         return HTMLResponse(content=f"<p>Error loading message: {e}</p>")