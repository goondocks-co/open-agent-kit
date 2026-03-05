import logging
from html import escape
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response

from open_agent_kit.features.team.cli_command import (
    resolve_ci_cli_command,
)
from open_agent_kit.features.team.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ui"])

static_path = Path(__file__).parent.parent / "static"

_STALE_INSTALL_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html><head><title>OAK CI - Restarting</title>
<meta http-equiv="refresh" content="10">
<style>body{{font-family:system-ui;max-width:600px;margin:80px auto;padding:0 20px}}
code{{background:#f0f0f0;padding:2px 6px;border-radius:3px}}
.spinner{{display:inline-block;width:16px;height:16px;border:2px solid #ccc;
border-top-color:#333;border-radius:50%;animation:spin 1s linear infinite;
vertical-align:middle;margin-right:8px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}</style></head>
<body><h1>Daemon Restarting</h1>
<p>The OAK package was upgraded. The daemon is restarting to pick up the new version.</p>
<p><span class="spinner"></span>This page will refresh automatically.</p>
<p><small>If this takes more than a minute, run <code>{cli_command} team restart</code> manually.</small></p>
</body></html>"""


def _render_stale_install_html() -> str:
    """Render stale install HTML with the configured CLI command."""
    state = get_state()
    cli_command = "oak"
    if state.project_root:
        try:
            cli_command = resolve_ci_cli_command(state.project_root)
        except (OSError, ValueError):
            logger.debug("Could not resolve CLI command, using default", exc_info=True)
    return _STALE_INSTALL_HTML_TEMPLATE.format(cli_command=escape(cli_command))


def _get_cache_version() -> str:
    """Get cache version based on JS file modification time."""
    js_path = Path(__file__).parent.parent / "static" / "js" / "app.js"
    if js_path.exists():
        return str(int(js_path.stat().st_mtime))
    return "1"


@router.get("/logo.png", response_class=Response)
async def logo() -> Response:
    path = Path(__file__).parent.parent / "static" / "logo.png"
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/png")


@router.get("/favicon.png", response_class=Response)
async def favicon() -> Response:
    path = Path(__file__).parent.parent / "static" / "favicon.png"
    if not path.exists():
        return Response(status_code=404)
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
@router.get("/cloud", response_class=HTMLResponse)
@router.get("/agents", response_class=HTMLResponse)
# Catch-all for activity sub-routes (e.g., /activity/sessions/123)
@router.get("/activity/{rest:path}", response_class=HTMLResponse)
# Catch-all for agents sub-routes (e.g., /agents/runs)
@router.get("/agents/{rest:path}", response_class=HTMLResponse)
# Catch-all for team sub-routes (e.g., /team/sharing, /team/backups)
@router.get("/team/{rest:path}", response_class=HTMLResponse)
# Governance page and sub-routes
@router.get("/governance", response_class=HTMLResponse)
@router.get("/governance/{rest:path}", response_class=HTMLResponse)
async def dashboard(rest: str | None = None) -> HTMLResponse:
    """Serve the web dashboard with cache-busted assets."""
    # static/index.html is sibling to routes/ directory's parent (daemon/)
    index_path = Path(__file__).parent.parent / "static" / "index.html"

    # Read index content (Vite handles cache busting via hashed filenames)
    try:
        content = index_path.read_text()
    except (FileNotFoundError, OSError):
        return HTMLResponse(content=_render_stale_install_html())

    # Inject auth token as meta tag so the UI JS can read it
    state = get_state()
    if state.auth_token:
        content = content.replace(
            "</head>",
            f'<meta name="oak-auth-token" content="{state.auth_token}" />\n</head>',
        )

    return HTMLResponse(
        content=content,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )
