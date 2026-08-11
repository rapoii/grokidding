import asyncio
import time
import pytest
from fastapi.testclient import TestClient

# Mock urllib.request.urlopen to simulate a timeout
import urllib.request
import urllib.error
import grok_farmer.panel as panel
import grok_farmer.usage_db as usage_db

def test_quota_timeout():
    # Setup some fake data in the DB first
    usage_db.init_db()
    usage_db.update_usage("test1", "test1@example.com", 1000000, 500)
    usage_db.update_usage("test2", "test2@example.com", 1000000, 1000)
    
    original_urlopen = urllib.request.urlopen
    
    def mock_urlopen_hang(*args, **kwargs):
        # Simulate a hang longer than the 5s strict timeout
        time.sleep(6)
        return original_urlopen(*args, **kwargs)
        
    urllib.request.urlopen = mock_urlopen_hang
    
    try:
        from grok_farmer.panel import app
        client = TestClient(app)
        
        start_time = time.time()
        # force=true bypasses the 30s quota cache to trigger the fetch
        response = client.get("/api/quota?force=true")
        end_time = time.time()
        
        elapsed = end_time - start_time
        assert elapsed < 5.5, f"Endpoint took too long: {elapsed} seconds, expected < 5.5s"
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "db_fallback"
        assert "accounts" in data
        assert "total_limit" in data
        
        # Verify db logic parsed the mocked rows correctly (assuming db_usage is structured as list/dict)
        print("TEST PASSED: Timeout handled correctly and fallback data served.")
    finally:
        urllib.request.urlopen = original_urlopen

if __name__ == "__main__":
    test_quota_timeout()
