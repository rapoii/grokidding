import asyncio
import time
from fastapi.testclient import TestClient
import urllib.request
import urllib.error
import grok_farmer.panel as panel

def test_exception_fallback():
    original_urlopen = urllib.request.urlopen
    original_get_conns = panel._get_all_grok_connections

    def mock_urlopen_exception(*args, **kwargs):
        raise urllib.error.URLError("Network unreachable")

    def mock_get_connections():
        return [{"name": "Fake1", "email": "fake1@example.com", "token": "abc"}]

    urllib.request.urlopen = mock_urlopen_exception
    panel._get_all_grok_connections = mock_get_connections
    
    try:
        from grok_farmer.panel import app
        client = TestClient(app)
        
        t0 = time.time()
        response = client.get("/api/quota?force=true")
        t1 = time.time()
        
        elapsed = t1 - t0
        print(f"Elapsed: {elapsed:.2f}s")
        print(f"Status Code: {response.status_code}")
        print("Response JSON:", response.json())
        
        # In current logic, an immediate URLError caught at `_fetch_quota_sync` loop returns active=False/error. 
        # But we specifically want to test `asyncio.wait_for` timing out at the `get_quota` level.
    finally:
        urllib.request.urlopen = original_urlopen
        panel._get_all_grok_connections = original_get_conns

if __name__ == "__main__":
    test_exception_fallback()