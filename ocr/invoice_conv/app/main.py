import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.routers.api import api_router
from app.db.session import engine, Base
from app.core.deps import get_db


# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set up CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


# Front-end routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Home page."""
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("auth/login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register page."""
    return templates.TemplateResponse("auth/register.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page."""
    return templates.TemplateResponse("dashboard/index.html", {"request": request})


@app.get("/invoice/upload", response_class=HTMLResponse)
async def upload_invoice(request: Request):
    """Upload invoice page."""
    return templates.TemplateResponse("dashboard/upload.html", {"request": request})


@app.get("/invoice/list", response_class=HTMLResponse)
async def list_invoices(request: Request):
    """List invoices page."""
    return templates.TemplateResponse("dashboard/invoices.html", {"request": request})


@app.get("/subscription", response_class=HTMLResponse)
async def subscription_page(request: Request):
    """Subscription page."""
    return templates.TemplateResponse("dashboard/subscription.html", {"request": request})


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """Profile page."""
    return templates.TemplateResponse("dashboard/profile.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)