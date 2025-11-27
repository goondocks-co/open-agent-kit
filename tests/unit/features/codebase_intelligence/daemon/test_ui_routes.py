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
    # Vite generates lowercase doctype
    assert "<!doctype html>" in response.text.lower()
    # New UI uses "Oak CI" title
    assert "oak ci" in response.text.lower()


def test_root_redirects_or_serves_html():
    """Test that the root / endpoint also serves the UI."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_static_files_mounted():
    """Test that static files are correctly mounted and accessible.

    Note: The UI is now built with Vite, so assets are in /static/assets/
    with hashed filenames. We test that static mount works by checking
    for known static files.
    """
    app = create_app()
    client = TestClient(app)

    # Test that index.html is accessible via static mount
    response = client.get("/static/index.html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    # Test that logo.png is accessible
    response = client.get("/logo.png")
    assert response.status_code == 200
    assert "image/png" in response.headers["content-type"]

    # Test that favicon.png is accessible
    response = client.get("/favicon.png")
    assert response.status_code == 200
