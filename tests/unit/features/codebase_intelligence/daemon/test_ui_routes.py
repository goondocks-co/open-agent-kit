"""Tests for the daemon UI routes."""

from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.daemon.server import create_app


def test_ui_root_serves_html():
    """Test that the /ui endpoint serves the index.html file."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/ui")
    assert response.status_code == 200
    # The content-type might vary slightly depending on OS, but should be text/html
    assert "text/html" in response.headers["content-type"]
    assert "<!DOCTYPE html>" in response.text
    assert "Codebase Intelligence" in response.text


def test_root_redirects_or_serves_html():
    """Test that the root / endpoint also serves the UI."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_static_files_mounted():
    """Test that static files are correctly mounted and accessible."""
    app = create_app()
    client = TestClient(app)

    # Test CSS
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert ":root" in response.text

    # Test JS
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    assert (
        "javascript" in response.headers["content-type"]
        or "application/javascript" in response.headers["content-type"]
    )

    # Test index.html via static route
    response = client.get("/static/index.html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
