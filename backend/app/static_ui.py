"""Serves the built UI from the run image (specs/features/app-container.md, PC2)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# /app/static in the run image. The development container has no such folder.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def add_static_ui(app: FastAPI, static_dir: Path) -> None:
    """Serve the UI in `static_dir`; does nothing when it holds no built UI.

    Call it after every other route is added: its route matches every path.
    """
    index = static_dir / "index.html"
    if not index.is_file():
        return
    # The image's files never change, so a fixed list works, and a requested path is only
    # looked up in it: no path can name a file outside the folder.
    files = {
        file.relative_to(static_dir).as_posix(): file
        for file in static_dir.rglob("*")
        if file.is_file()
    }

    def serve_ui(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(404)
        # The UI's own paths, such as /kuitit/12, are resolved in the browser.
        return FileResponse(files.get(path, index))

    app.add_api_route("/{path:path}", serve_ui, methods=["GET"], include_in_schema=False)
