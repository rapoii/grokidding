import asyncio
import time
from fastapi.testclient import TestClient
import urllib.request
import urllib.error
import grok_farmer.panel as panel

def mock_urlopen_hang(*args, **kwargs):
    time.sleep(0.5)
    raise urllib.error.URLError(TimeoutError("mocked timeout"))

def mock_get_connections():
    # Return just one fake connection to avoid a huge loop!
    return [{"name": "Fake1", "email": "fake1@example.com", "token": "abc"}]

def test_timeout():
    original_urlopen = urllib.request.urlopen
    original_get_conns = panel._get_all_grok_connections
    
    urllib.request.urlopen = mock_urlopen_hang
    panel._get_all_grok_connections = mock_get_connections
    
    try:
        from grok_farmer.panel import app
        client = TestClient(app)
        
        print("Starting request with 1 connection...")
        t0 = time.time()
        response = client.get("/api/quota?force=true")
        t1 = time.time()
        
        elapsed = t1 - t0
        print(f"Time elapsed: {elapsed:.2f}s")
        assert elapsed < 5.5, f"Endpoint took too long: {elapsed} seconds, expected < 5.5s"
        assert response.status_code == 200
        
        data = response.json()
        print("Response:", data)
        assert data.get("status") == "db_fallback" or "db_usage" in data
        
    finally:
        urllib.request.urlopen = original_urlopen
        panel._get_all_grok_connections = original_get_conns

if __name__ == "__main__":
    test_timeout()
