"""
Dependencies for FastAPI routes.
Provides database connection and other shared dependencies.
"""

from config.database import get_db_connection

def get_db():
    """
    Dependency that yields a database connection.
    Connection is automatically closed after the request.
    """
    connection = get_db_connection()
    try:
        yield connection
    finally:
        connection.close()