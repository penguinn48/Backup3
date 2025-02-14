from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse
import os
from typing import Optional
import uvicorn

# Import existing functions from app.py
from app import (
    get_food_image,
    get_nutrition_info,
    get_food_predictions,
    analyze_nutrition,
    allowed_file
)

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Configuration
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.get("/", response_class=HTMLResponse)
async def upload_file(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/search")
async def search_food(request: Request, food_name: str = Form(...)):
    try:
        # Get food image from Pexels
        image_info = get_food_image(food_name)
        
        food_info = {
            'name': food_name,
            'confidence': 1.0,
            'nutrition': get_nutrition_info(food_name),
            'image': image_info
        }
        return templates.TemplateResponse(
            "result.html", 
            {
                "request": request,
                "foods": [food_info], 
                "uploaded_image": None
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "upload.html", 
            {
                "request": request,
                "error": f'An error occurred: {str(e)}'
            }
        )

@app.post("/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):
    try:
        if not allowed_file(file.filename):
            return templates.TemplateResponse(
                "upload.html", 
                {
                    "request": request,
                    "error": 'Invalid file type. Please upload an image (PNG, JPG, JPEG, GIF)'
                }
            )

        # Create secure filename and save file
        filename = file.filename
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Save the file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Get food predictions with nutrition info
        predictions = get_food_predictions(file_path)
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "foods": predictions,
                "uploaded_image": filename
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "error": f'An error occurred: {str(e)}'
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