"""
AirWatch ASEAN API - Entry Point
Air Quality Monitoring for ASEAN region
"""
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

# Database (SQLAlchemy for users)
from database import init_user_db

# Import routers
from app.routes import stations, predictions, location, evaluation, auth_routes, user

# Setup logging
setup_logging()

# Initialize databases on import (for Railway/production)
init_db()          # Init AQI database (SQLite - creates measurements table)
init_user_db()     # Init User database (PostgreSQL/SQLite)

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
    # Allow inline scripts and eval for the app to work
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

# Start crawler in background thread
crawler_thread = Thread(target=crawler_task, daemon=True)
crawler_thread.start()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)