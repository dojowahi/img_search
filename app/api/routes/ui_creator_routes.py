import json
import logging
import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.services.llm_service import llm_service

APP_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = os.path.join(APP_DIR, "templates")

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize templates with correct path
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/ui_creator/")
async def find_company(request:Request, comp_name:str):
    prompt = f"""Check if {comp_name} is valid, if not get the closest valid name."""
    logger.info(f"UI creator :{prompt}")
    response_schema = {"type":"object","properties":{"comp_name":{"type":"string","description":"Commonly used name of the company"},"comp_abbv":{"type":"string","description":"Create a 2 to 5 letter abbreviation for company in lower case"}},"required":["comp_name","comp_abbv"]}
    response = await llm_service.gemini_text(prompt=prompt,response_schema=response_schema)
    # Check if the shell script exists
    data = json.loads(response)
    comp_abbv = data.get("comp_abbv")
    comp_name = data.get("comp_name")
    logger.info(f"Company:{comp_name}")
    logger.info(f"Abbv:{comp_abbv}")
    script_path = f"{APP_DIR}/scripts/replicator.sh"
    logger.info(f"Script path:{script_path}")
    
    logger.info("Executing replicator...")
    if not os.path.exists(script_path):
        logger.error(f"Error: Shell script '{script_path}' not found.")
        return {"File not found": "Shell failure: {e}"}
    
    try:
        result = subprocess.run(
            ["bash", script_path, APP_DIR,comp_name,comp_abbv],
            capture_output=True,
            text=True,
            check=True,
        )
        return_code = result.returncode
        shell_output = result.stdout.strip()  # Remove leading/trailing whitespace

        logger.info(f"Shell script output:\n{shell_output}")

        if return_code==1:
            return {"error": f"Shell return code {return_code}: {shell_output}"}
        
    except Exception as e:
        logger.error(f"Replicator failure for {comp_name}: {e}")
        return {"error": f"Shell failure: {e}"}

    brand_path = f"{APP_DIR}/core/brand.py"
    logger.info(f"Brand path:{brand_path}")
    brand_content = None #Initialize to None
    try:
        with open(brand_path, 'r', encoding='utf-8') as file:
            brand_content = file.read()
    except Exception as e:
        logger.error(f"An error occurred while reading the file: {e}")

    brand_prompt = f"""Update the BRAND_CONFIG variable to have a key with {comp_name} colors, use {comp_abbv} as the key to refer {comp_name}. Don't give any explanation, just return the variable.{brand_content}"""
    brand_response = await llm_service.gemini_text(brand_prompt)
    brand_response = brand_response.replace("```python", "")
    brand_response = brand_response.replace("```", "")
    logger.info(brand_response)

    try:
        with open(brand_path, 'w', encoding='utf-8') as file:
            file.write(brand_response)
        logger.info(f"File '{brand_path}' overwritten successfully.")
        host_url = request.url.netloc
        scheme = request.url.scheme
        generated_url = f"{scheme}://{host_url}/{comp_abbv}"
        return templates.TemplateResponse("base/ui_results.html", {"request": request, "url": generated_url})
    
    except Exception as e:
        logger.error(f"An error occurred for {comp_abbv} while overwriting the file: {e}")
        return {"base_url": f"UI creator failed, contact Ankur Wahi with this code:{comp_abbv}"}

    