"""
FastAPI application for Billing_DC system.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import clients, servers, prices

# Create FastAPI instance
app = FastAPI(
    title="Billing_DC API",
    description="API for billing system for virtual servers in data center",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(clients.router, prefix="/api/v1/clients", tags=["Clients"])
app.include_router(servers.router, prefix="/api/v1/servers", tags=["Servers"])
app.include_router(prices.router, prefix="/api/v1/prices", tags=["Prices"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Billing_DC API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}