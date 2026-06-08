import unittest
import os
import tempfile
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from backend.main import app
from backend.config import settings
from backend.services import db_service

class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp()
        settings.database_path = self.db_path
        
        # Initialize the database schema
        schema_path = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")
        db_service.init_db(schema_path)
        
        self.client = TestClient(app)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_read_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Welcome", response.json()["message"])

    @patch("backend.api.routes.compiled_workflow.ainvoke")
    def test_verify_endpoint_creates_job(self, mock_ainvoke):
        # Mocking workflow return
        mock_ainvoke.return_value = {
            "article_title": "Fake Test Article Title",
            "article_content": "Factual body content",
            "summary": "Summary content",
            "final_verdict": "FALSE",
            "credibility_score": 10,
            "bias_rating": "Center",
            "tone_rating": "Sensational",
            "claims": [{"id": "c1", "claim_text": "Claim X"}],
            "verdicts": {"c1": {"verdict": "FALSE", "explanation": "Contradicted"}},
            "evidences": {"c1": []},
            "errors": []
        }
        
        # Request
        response = self.client.post(
            "/api/verify", 
            json={"url": "https://example.com/test-article"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("job_id", data)
        self.assertEqual(data["status"], "pending")
        
        # Test Job Status Polling
        job_id = data["job_id"]
        status_res = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(status_res.status_code, 200)
        # Should be either pending, running, or completed (since it runs in background task on the same process)
        status_data = status_res.json()
        self.assertIn(status_data["status"], ["pending", "running", "completed"])

    def test_get_history_empty(self):
        response = self.client.get("/api/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_sources(self):
        response = self.client.get("/api/sources")
        self.assertEqual(response.status_code, 200)
        sources = response.json()
        self.assertIn("apnews.com", sources)
        self.assertEqual(sources["apnews.com"]["credibility_score"], 0.95)

if __name__ == "__main__":
    unittest.main()
