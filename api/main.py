"""
FastAPI application for Billing_DC system.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from api.routes import clients, servers, prices, reports, web
from api.routes import physical_servers

# Create FastAPI instance
app = FastAPI(
    title="Billing_DC API",
    description="API для биллинговой системы виртуальных серверов в дата-центре",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,  # Скрыть модели по умолчанию
        "docExpansion": "none",  # Свернуть все эндпоинты
    }
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (CSS, JS)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(clients.router, prefix="/api/v1/clients", tags=["Клиенты"])
app.include_router(servers.router, prefix="/api/v1/servers", tags=["Серверы"])
app.include_router(prices.router, prefix="/api/v1/prices", tags=["Цены"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Отчеты"])
# Include physical servers router
app.include_router(physical_servers.router, prefix="/api/v1/physical-servers", tags=["Физические серверы"])

# Web interface router (without prefix)
app.include_router(web.router)


@app.get("/")
async def root():
    """Корневой эндпоинт."""
    return {
        "message": "Billing_DC API",
        "version": "1.0.0",
        "docs": "/docs",
        "web": "/clients",
    }


@app.get("/health")
async def health():
    """Проверка работоспособности."""
    return {"status": "healthy"}
