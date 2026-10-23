"""
Batch 03 Tests: Static Asset Delivery, Cache Headers, SPA Fallback, and Response Compression
Verifies:
1. Hashed JS asset returns 'Cache-Control: public, max-age=31536000, immutable'
2. Hashed CSS asset returns 'Cache-Control: public, max-age=31536000, immutable'
3. HTML entry document returns 'Cache-Control: no-cache'
4. SPA fallback returns index.html with 'Cache-Control: no-cache'
5. Gzip compression when client sends 'Accept-Encoding: gzip'
6. No stale index caching
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app, client_dist

@pytest.fixture
def test_client():
    return TestClient(app)

def test_html_entry_document_no_cache(test_client):
    """HTML entry document must return Cache-Control: no-cache."""
    res = test_client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    cache_control = res.headers.get("cache-control", "")
    assert "no-cache" in cache_control
    assert "immutable" not in cache_control

def test_spa_fallback_no_cache(test_client):
    """Unknown client routes must fallback to index.html with Cache-Control: no-cache."""
    res = test_client.get("/some/deep/client/route?param=123")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    cache_control = res.headers.get("cache-control", "")
    assert "no-cache" in cache_control
    assert "immutable" not in cache_control

def test_api_routes_not_captured_by_spa_fallback(test_client):
    """Non-existent API routes must return 404 JSON, not HTML SPA fallback."""
    res = test_client.get("/api/nonexistent-endpoint")
    assert res.status_code == 404
    assert res.headers.get("content-type", "").startswith("application/json")

def test_hashed_js_asset_cache_headers(test_client):
    """Hashed JavaScript assets in /assets must have immutable 1-year cache headers."""
    if not client_dist:
        pytest.skip("client_dist not present")
    assets_dir = client_dist / "assets"
    js_files = list(assets_dir.glob("*.js"))
    if not js_files:
        pytest.skip("No JS assets found in client_dist/assets")

    sample_js = js_files[0].name
    res = test_client.get(f"/assets/{sample_js}")
    assert res.status_code == 200
    assert "javascript" in res.headers.get("content-type", "")
    cache_control = res.headers.get("cache-control", "")
    assert "public" in cache_control
    assert "max-age=31536000" in cache_control
    assert "immutable" in cache_control

def test_hashed_css_asset_cache_headers(test_client):
    """Hashed CSS assets in /assets must have immutable 1-year cache headers."""
    if not client_dist:
        pytest.skip("client_dist not present")
    assets_dir = client_dist / "assets"
    css_files = list(assets_dir.glob("*.css"))
    if not css_files:
        pytest.skip("No CSS assets found in client_dist/assets")

    sample_css = css_files[0].name
    res = test_client.get(f"/assets/{sample_css}")
    assert res.status_code == 200
    assert "css" in res.headers.get("content-type", "")
    cache_control = res.headers.get("cache-control", "")
    assert "public" in cache_control
    assert "max-age=31536000" in cache_control
    assert "immutable" in cache_control

def test_gzip_compression_active(test_client):
    """Gzip compression is applied when client accepts gzip for compressible responses."""
    # Test with index.html or large endpoint
    res = test_client.get("/", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200
    # When content size >= 1000 bytes, GZipMiddleware adds Content-Encoding: gzip
    if len(res.content) >= 1000:
        assert res.headers.get("content-encoding") == "gzip"

def test_gzip_compression_on_static_asset(test_client):
    """Gzip compression is applied to JS bundle when Accept-Encoding: gzip is sent."""
    if not client_dist:
        pytest.skip("client_dist not present")
    assets_dir = client_dist / "assets"
    js_files = [f for f in assets_dir.glob("*.js") if f.stat().st_size > 2000]
    if not js_files:
        pytest.skip("No JS files larger than 2KB found")

    sample_js = js_files[0].name
    res = test_client.get(f"/assets/{sample_js}", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200
    assert res.headers.get("content-encoding") == "gzip"
