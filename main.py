"""Main application entry point."""
import uvicorn
from config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.api:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

