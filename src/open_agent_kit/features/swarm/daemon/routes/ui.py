"""UI routes for the swarm daemon -- serves the React SPA."""

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response

from open_agent_kit.features.swarm.daemon.state import get_swarm_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ui"])

static_path = Path(__file__).parent.parent / "static"


@router.get("/logo.png", response_class=Response)
async def logo() -> Response:
    path = static_path / "logo.png"
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/png")


@router.get("/favicon.png", response_class=Response)
async def favicon() -> Response:
    path = static_path / "favicon.png"
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path)


@router.get("/", response_class=HTMLResponse)
@router.get("/search", response_class=HTMLResponse)
@router.get("/nodes", response_class=HTMLResponse)
@router.get("/deploy", response_class=HTMLResponse)
@router.get("/agents", response_class=HTMLResponse)
@router.get("/logs", response_class=HTMLResponse)
@router.get("/config", response_class=HTMLResponse)
# Catch-all for sub-routes
@router.get("/deploy/{rest:path}", response_class=HTMLResponse)
@router.get("/agents/{rest:path}", response_class=HTMLResponse)
async def dashboard(rest: str | None = None) -> HTMLResponse:
    """Serve the web dashboard."""
    index_path = static_path / "index.html"
    try:
        content = index_path.read_text()
    except (FileNotFoundError, OSError):
        return HTMLResponse(
            content="<html><body><h1>UI not built</h1>"
            "<p>Run <code>make swarm-ui-build</code> to build the swarm UI.</p></body></html>",
            status_code=503,
        )

    # Inject auth token as meta tag so the UI JS can read it
    state = get_swarm_state()
    if state.auth_token:
        content = content.replace(
            "</head>",
            f'<meta name="oak-auth-token" content="{state.auth_token}" />\n</head>',
        )

    return HTMLResponse(
        content=content,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )
