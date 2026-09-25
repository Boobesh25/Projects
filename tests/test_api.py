import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from httpx import AsyncClient, ASGITransport
from src.api.app import create_app


class TestHealthEndpoint(unittest.IsolatedAsyncioTestCase):
    """Smoke test to verify FastAPI initializes and /health endpoint responds."""

    async def test_health_check_endpoint(self):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertIn("model", data)


if __name__ == "__main__":
    unittest.main()
