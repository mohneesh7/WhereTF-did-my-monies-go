"""Entry point – start the FastAPI server."""

import uvicorn

from money_manager.config import settings


def main():
    """Launch the FastAPI server."""
    uvicorn.run(
        "money_manager.ui.api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )


if __name__ == "__main__":
    main()
