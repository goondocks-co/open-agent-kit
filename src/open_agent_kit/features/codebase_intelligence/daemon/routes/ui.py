from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(tags=["ui"])

static_path = Path(__file__).parent.parent / "static"
# We'll need to mount this on the main app instance, but APIRouter doesn't support .mount()
# So we have to expose a way for the main app to mount it, or use a workaround.
# Actually, the best way for the daemon is to check the main server.py
# BUT `server.py` likely imports this router.
# Let's see if we can just serve the specific files we know about as routes first,
# OR we rely on the main server mounting it.
# Check server.py first before editing further?
# Actually, let's just add specific routes for favicon and logo if mounting IS hard here.


def _get_cache_version() -> str:
    """Get cache version based on JS file modification time."""
    js_path = Path(__file__).parent.parent / "static" / "js" / "app.js"
    if js_path.exists():
        return str(int(js_path.stat().st_mtime))
    return "1"


@router.get("/logo.png")
async def logo() -> FileResponse:
    path = Path(__file__).parent.parent / "static" / "logo.png"
    return FileResponse(path, media_type="image/png")


@router.get("/favicon.png")
async def favicon() -> FileResponse:
    path = Path(__file__).parent.parent / "static" / "favicon.png"
    return FileResponse(path)


@router.get("/", response_class=HTMLResponse)
@router.get("/ui", response_class=HTMLResponse)
@router.get("/search", response_class=HTMLResponse)
@router.get("/logs", response_class=HTMLResponse)
@router.get("/config", response_class=HTMLResponse)
@router.get("/help", response_class=HTMLResponse)
@router.get("/activity", response_class=HTMLResponse)
@router.get("/devtools", response_class=HTMLResponse)
@router.get("/team", response_class=HTMLResponse)
@router.get("/agents", response_class=HTMLResponse)
# Catch-all for activity sub-routes (e.g., /activity/sessions/123)
@router.get("/activity/{rest:path}", response_class=HTMLResponse)
# Catch-all for agents sub-routes (e.g., /agents/runs)
@router.get("/agents/{rest:path}", response_class=HTMLResponse)
# Catch-all for team sub-routes (e.g., /team/sharing, /team/backups)
@router.get("/team/{rest:path}", response_class=HTMLResponse)
async def dashboard(rest: str | None = None) -> HTMLResponse:
    """Serve the web dashboard with cache-busted assets."""
    # static/index.html is sibling to routes/ directory's parent (daemon/)
    index_path = Path(__file__).parent.parent / "static" / "index.html"

    # Read index content (Vite handles cache busting via hashed filenames)
    content = index_path.read_text()
    return HTMLResponse(content=content)
