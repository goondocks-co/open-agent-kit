from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])


def _get_cache_version() -> str:
    """Get cache version based on JS file modification time."""
    js_path = Path(__file__).parent.parent / "static" / "js" / "app.js"
    if js_path.exists():
        return str(int(js_path.stat().st_mtime))
    return "1"


@router.get("/", response_class=HTMLResponse)
@router.get("/ui", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Serve the web dashboard with cache-busted assets."""
    # static/index.html is sibling to routes/ directory's parent (daemon/)
    index_path = Path(__file__).parent.parent / "static" / "index.html"

    # Read and inject cache version
    content = index_path.read_text()
    cache_version = _get_cache_version()
    content = content.replace(
        'src="/static/js/app.js"', f'src="/static/js/app.js?v={cache_version}"'
    ).replace('href="/static/css/style.css"', f'href="/static/css/style.css?v={cache_version}"')

    return HTMLResponse(content=content)
