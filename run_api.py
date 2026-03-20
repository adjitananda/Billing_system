#!/usr/bin/env python3
"""
Run script for FastAPI application.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes (development mode)
        log_level="info",
    )