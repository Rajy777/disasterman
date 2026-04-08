"""
server/app.py — OpenEnv server entry point.
The openenv validator requires main() and if __name__ == '__main__' here.
"""
import os
from main import app  # re-export FastAPI app

__all__ = ["app"]


def main():
    """Start the FastAPI server. Called by openenv validate and [project.scripts]."""
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
