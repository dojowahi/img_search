import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import image_routes, search_routes
from app.core.config import settings
from app.core.events import shutdown_event, startup_event

# Get the path to the app directory
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = os.path.join(APP_DIR, "static")
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")

# Configure logging
import logging

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
    )
    
    # Register startup and shutdown events
    application.add_event_handler("startup", startup_event)
    application.add_event_handler("shutdown", shutdown_event)
    
    # Include API routes
    application.include_router(
        image_routes.router, 
        prefix=f"{settings.API_V1_STR}", 
        tags=["Images"]
    )
    application.include_router(
        search_routes.router, 
        prefix=f"{settings.API_V1_STR}", 
        tags=["Search"]
    )
    
    # Debug information
    logger.info(f"Static directory path: {STATIC_DIR}")
    logger.info(f"Static directory exists: {os.path.exists(STATIC_DIR)}")
    
    # Mount static files with correct path
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    
    # Root route for the frontend
    @application.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})
    
    return application

app = create_application()