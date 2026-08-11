import asyncio
import time
from fastapi.testclient import TestClient

import urllib.request
import urllib.error
import grok_farmer.panel as panel
import grok_farmer.usage_db as usage_db

def mock_urlopen_hang(*args, **kwargs):
    # Instead of really sleeping, immediately raise TimeoutError to simulate urllib timeout
    # OR sleep a tiny bit and raise TimeoutError
    time.sleep(0.5)
    raise urllib.error.URLError(TimeoutError("mocked timeout"))

def test_timeout():
    usage_db.init_db()
    usage_db.update_usage("test_account_timeout", "test_timeout@example.com", 500000, 200)

    original_urlopen = urllib.request.urlopen
    urllib.request.urlopen = mock_urlopen_hang
    
    try:
        from grok_farmer.panel import app
        client = TestClient(app)
        
        print("Starting request...")
        t0 = time.time()
        # force=true bypasses the 30s quota cache to trigger the fetch
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

if __name__ == "__main__":
    test_timeout()
