import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import (
    creator_routes,
    image_routes,
    llm_routes,
    product_routes,
    search_routes,
)
from app.core.brand import BRAND_CONFIG  # Import BRAND_CONFIG
from app.core.config import settings  # Import settings
from app.core.events import shutdown_event, startup_event

# Get the path to the app directory
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = os.path.join(APP_DIR, "static")
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

def create_application() -> FastAPI:
    """Create and configure the FastAPI application"""
    application = FastAPI(
        title=settings.APP_NAME,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # Register startup and shutdown events
    application.add_event_handler("startup", startup_event)
    application.add_event_handler("shutdown", shutdown_event)

    # Include API routes
    application.include_router(image_routes.router, prefix=settings.API_V1_STR, tags=["Images"])
    application.include_router(search_routes.router, prefix=settings.API_V1_STR, tags=["Search"])
    application.include_router(llm_routes.router, prefix=settings.API_V1_STR, tags=["LLM"])
    application.include_router(product_routes.router, prefix=settings.API_V1_STR, tags=["Target Product Search"])
    application.include_router(creator_routes.router, prefix=settings.API_V1_STR, tags=["UI creator"])


    # Debug information
    logger.info(f"Static directory path: {STATIC_DIR}")
    logger.info(f"Static directory exists: {os.path.exists(STATIC_DIR)}")

    # Mount static files with correct path
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return application

app = create_application()

@app.get("/target", response_class=HTMLResponse)
async def target_frontend(request: Request):
    """Target-branded frontend"""
    return templates.TemplateResponse(
        "target/index.html",
        {"request": request, "brand": "target", "brand_config": BRAND_CONFIG["target"]}
    )

@app.get("/wayfair", response_class=HTMLResponse)
async def wayfair_frontend(request: Request):
    """Wayfair-branded frontend"""
    return templates.TemplateResponse(
        "wayfair/index.html",
        {"request": request, "brand": "wayfair", "brand_config": BRAND_CONFIG["wayfair"]}
    )

@app.get("/walmart", response_class=HTMLResponse)
async def walmart(request: Request):
    """Walmart-branded frontend"""
    return templates.TemplateResponse(
        "walmart/index.html",
        {"request": request, "brand": "walmart", "brand_config": BRAND_CONFIG["walmart"]}
    )

@app.get("/thd", response_class=HTMLResponse)
async def thd(request: Request):
    """Home Depot-branded frontend"""
    return templates.TemplateResponse(
        "thd/index.html",
        {"request": request, "brand": "thd", "brand_config": BRAND_CONFIG["thd"]}
    )

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Serve the upload interface"""
    return templates.TemplateResponse(
        "base/upload.html",  # Path to your template in the templates folder
        {"request": request}
    )

# Redirect root to Target by default
@app.get("/", response_class=RedirectResponse)
async def redirect_to_default():
    return RedirectResponse(url="/target")

