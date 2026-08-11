import asyncio
import time
from fastapi.testclient import TestClient
import urllib.request
import urllib.error

def test_quota_fallback():
    # Setup our mocked logic
    original_urlopen = urllib.request.urlopen
    
    def mock_urlopen_hang(*args, **kwargs):
        time.sleep(0.1)
        raise urllib.error.URLError(TimeoutError("mocked network timeout"))

    urllib.request.urlopen = mock_urlopen_hang
    
    try:
        from grok_farmer.panel import app
        client = TestClient(app)
        
        # We know there are 78 connections in the DB.
        # This will time out fast via our URLError override and hit DB fallback.
        print("Sending request...")
        t0 = time.time()
        response = client.get("/api/quota?force=true")
        t1 = time.time()
        
        elapsed = t1 - t0
        print(f"Elapsed: {elapsed:.2f}s")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print("Response data keys:", data.keys())
        
        # It's okay if it timed out in urllib.request.urlopen, we just want to ensure it works.
        assert "accounts" in data or "db_usage" in data
        assert elapsed < 5.5, f"Timeout was {elapsed}s, expected < 5.5s"

    finally:
        urllib.request.urlopen = original_urlopen

if __name__ == "__main__":
    test_quota_fallback()