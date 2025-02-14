from fastapi import FastAPI, File, UploadFile, Form, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER
import os
from typing import Optional
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import json
from redis_config import redis_client, CACHE_EXPIRATION, SessionManager, cleanup_task
import uuid
import asyncio

# Import existing functions from app.py
from app import (
    get_food_image,
    get_nutrition_info,
    get_food_predictions,
    analyze_nutrition,
    allowed_file
)

# Load environment variables
load_dotenv()

# Get secret key from environment variable
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY set in environment variables")

app = FastAPI()
app.add_middleware(
    SessionMiddleware, 
    secret_key=SECRET_KEY,
    max_age=3600,  # Session expires after 1 hour
    same_site="lax",  # Protects against CSRF
    https_only=True  # Cookies only sent over HTTPS
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Configuration
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.on_event("startup")
async def startup_event():
    """Start background tasks when app starts"""
    asyncio.create_task(cleanup_task())

@app.get("/", response_class=HTMLResponse)
async def upload_file(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/search")
async def search_food(request: Request, food_name: str = Form(...)):
    try:
        image_info = get_food_image(food_name)
        
        food_info = {
            'name': food_name,
            'confidence': 1.0,
            'nutrition': get_nutrition_info(food_name),
            'image': image_info
        }
        
        # Store data using SessionManager
        session_id = SessionManager.create_session({
            'predictions': [food_info],
            'uploaded_image': None
        })

        return RedirectResponse(
            url=f"/results/{session_id}",
            status_code=HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return templates.TemplateResponse(
            "upload.html", 
            {"request": request, "error": f'An error occurred: {str(e)}'}
        )

@app.post("/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):
    try:
        if not allowed_file(file.filename):
            return templates.TemplateResponse(
                "upload.html", 
                {"request": request, "error": 'Invalid file type'}
            )

        filename = file.filename
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        predictions = get_food_predictions(file_path)
        
        # Store data using SessionManager
        session_id = SessionManager.create_session({
            'predictions': predictions,
            'uploaded_image': filename
        })

        return RedirectResponse(
            url=f"/results/{session_id}",
            status_code=HTTP_303_SEE_OTHER
        )
    except Exception as e:
        return templates.TemplateResponse(
            "upload.html",
            {"request": request, "error": f'An error occurred: {str(e)}'}
        )

@app.get("/results/{session_id}")
async def show_results(request: Request, session_id: str):
    data = SessionManager.get_session(session_id)
    
    if not data:
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "foods": data['predictions'],
            "uploaded_image": data['uploaded_image']
        }
    )

@app.get("/suggestions")
async def get_suggestions(q: str):
    """Get food name suggestions"""
    if not q or len(q) < 2:
        return []
    
    try:
        # Search USDA database for suggestions
        search_url = f"{USDA_BASE_URL}/foods/search"
        params = {
            'api_key': USDA_API_KEY,
            'query': q,
            'dataType': ['Survey (FNDDS)'],
            'pageSize': 10
        }
        
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        suggestions = [food['description'] for food in data.get('foods', [])]
        return suggestions
    except Exception as e:
        print(f"Error fetching suggestions: {str(e)}")
        return []

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 