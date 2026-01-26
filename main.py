"""
AirWatch ASEAN API - Entry Point
Air Quality Monitoring for ASEAN region
"""
import os
import time
import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from threading import Thread

# App modules
from app.config import setup_logging
from app.db import init_db
from app.crawler import crawler_task

# Setup logging first
setup_logging()

# Initialize AQI database
try:
    init_db()
except Exception as e:
    logging.error(f"AQI DB init error: {e}")

# Initialize User database
try:
    from database import init_user_db
    init_user_db()
except Exception as e:
    logging.warning(f"User DB init skipped: {e}")

# Import routers
from app.routes import stations, predictions, location, evaluation, auth_routes, user

# Create FastAPI app
app = FastAPI(title="AirWatch ASEAN API", version="2.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"]
)


# Middleware to add security headers that allow inline scripts
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; script-src * 'unsafe-inline' 'unsafe-eval'; style-src * 'unsafe-inline';"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# Include routers
app.include_router(stations.router)
app.include_router(predictions.router)
app.include_router(location.router)
app.include_router(evaluation.router)
app.include_router(auth_routes.router)
app.include_router(user.router)


@app.on_event("startup")
async def startup_event():
    """Start crawler after app is fully ready"""
    logging.info("🚀 App started successfully!")
    
    def delayed_crawler():
        logging.info("⏳ Crawler will start in 60 seconds...")
        time.sleep(60)
        try:
            crawler_task()
        except Exception as e:
            logging.error(f"Crawler error: {e}")
    
    crawler_thread = Thread(target=delayed_crawler, daemon=True)
    crawler_thread.start()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)