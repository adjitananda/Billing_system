"""
FastAPI application for Billing_DC system.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from api.routes import clients, servers, prices, reports, web
from api.routes import calculator
from api.routes import physical_servers
from api.routes import quotes
from api.routes import competitors

# Create FastAPI instance
app = FastAPI(
    title="Billing_DC API",
    description="API для биллинговой системы виртуальных серверов в дата-центре",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "docExpansion": "none",
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
app.include_router(physical_servers.router, prefix="/api/v1/physical-servers", tags=["Физические серверы"])
app.include_router(web.router)
app.include_router(calculator.router, prefix="/api/v1/calculator", tags=["Калькулятор"])
app.include_router(quotes.router, prefix="", tags=["Коммерческое предложение"])
app.include_router(competitors.router, prefix="", tags=["Конкуренты"])


@app.get("/")
async def root():
    return {
        "message": "Billing_DC API",
        "version": "1.0.0",
        "docs": "/docs",
        "web": "/clients",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
