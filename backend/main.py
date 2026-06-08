import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from backend.config import settings
from backend.services.db_service import init_db
from backend.api.routes import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NewsCheck AI API",
    description="Multi-agent, RAG-powered Fact-Checking & Credibility Analysis Engine",
    version="1.0.0"
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router
app.include_router(api_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    logger.info("Initializing NewsCheck AI database...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")

@app.get("/")
def read_root():
    return {"message": "Welcome to NewsCheck AI API. Navigate to /docs for Swagger documentation."}

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app", 
        host=settings.host, 
        port=settings.port, 
        reload=True
    )
