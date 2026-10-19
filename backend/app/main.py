from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.init_db import init_db
from app.api.api_v1 import (
    auth,
    dashboard,
    reports,
    guests,
    records,
    review,
    settings as settings_api,
    audit
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB on startup (safely caught so server never hangs if DB is connecting)
    try:
        init_db()
    except Exception as e:
        print(f"[Lifespan Warning] Database initialization deferred: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=f"{settings.PROJECT_NAME} - {settings.TAGLINE}",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration - supports local dev, Vercel production and preview URLs
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://stay-track-eight.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# API Routes
api_prefix = settings.API_V1_STR
app.include_router(auth.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
app.include_router(guests.router, prefix=api_prefix)
app.include_router(records.router, prefix=api_prefix)
app.include_router(review.router, prefix=api_prefix)
app.include_router(settings_api.router, prefix=api_prefix)
app.include_router(audit.router, prefix=api_prefix)

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Mount frontend build static files if present
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {
            "name": settings.PROJECT_NAME,
            "tagline": settings.TAGLINE,
            "status": "healthy",
            "api_docs": "/docs"
        }
