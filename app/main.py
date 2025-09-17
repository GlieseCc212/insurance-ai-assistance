"""
Insurance AI Assistant - Main FastAPI Application
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from pathlib import Path

from .config import get_settings
from .routers import documents, queries, claims, health
from .database import init_db

# Get settings
settings = get_settings()

# Initialize FastAPI app
app = FastAPI(
    title="Insurance AI Assistant",
    description="AI-powered insurance document analysis and claim processing system",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# Include routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(queries.router, prefix="/api/v1")
app.include_router(claims.router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    await init_db()

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend application"""
    frontend_path = Path("../frontend/index.html")
    if frontend_path.exists():
        return frontend_path.read_text()
    return """
    <html>
        <head><title>Insurance AI Assistant</title></head>
        <body>
            <h1>Insurance AI Assistant</h1>
            <p>Welcome to the Insurance AI Assistant API</p>
            <p><a href="/api/docs">API Documentation</a></p>
        </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.environment == "development" else False
    )