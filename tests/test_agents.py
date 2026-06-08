import unittest
import os
import tempfile
import sqlite3
from unittest.mock import MagicMock, AsyncMock, patch

from backend.agents.state import AgentState
from backend.agents.workflow import route_after_verification, prepare_deep_search_node
from backend.services import db_service
from backend.config import settings

class TestWorkflowRouting(unittest.TestCase):
    def test_route_after_verification_no_claims(self):
        # Empty claims should route directly to detect_bias
        state: AgentState = {
            "claims": [],
            "verdicts": {},
            "evidences": {},
            "deep_search_done": False,
            "loop_count": 0,
            "errors": []
        }
        next_node = route_after_verification(state)
        self.assertEqual(next_node, "detect_bias")

    def test_route_after_verification_sufficient_evidence(self):
        # Claims that are verified (not UNVERIFIED) and have evidence should go to detect_bias
        state: AgentState = {
            "claims": [{"id": "c1", "claim_text": "Claim 1"}],
            "verdicts": {"c1": {"verdict": "TRUE", "explanation": "Confirmed"}},
            "evidences": {"c1": [{"snippet": "source"}]},
            "deep_search_done": False,
            "loop_count": 0,
            "errors": []
        }
        next_node = route_after_verification(state)
        self.assertEqual(next_node, "detect_bias")

    def test_route_after_verification_unverified_needs_deep_search(self):
        # Claim with UNVERIFIED status and no evidence should route to prepare_deep_search
        state: AgentState = {
            "claims": [{"id": "c1", "claim_text": "Claim 1"}],
            "verdicts": {"c1": {"verdict": "UNVERIFIED", "explanation": "No info"}},
            "evidences": {"c1": []},
            "deep_search_done": False,
            "loop_count": 0,
            "errors": []
        }
        next_node = route_after_verification(state)
        self.assertEqual(next_node, "prepare_deep_search")

    def test_route_after_verification_max_loops_reached(self):
        # If deep search was already done, we must not loop back (route to detect_bias)
        state: AgentState = {
            "claims": [{"id": "c1", "claim_text": "Claim 1"}],
            "verdicts": {"c1": {"verdict": "UNVERIFIED", "explanation": "No info"}},
            "evidences": {"c1": []},
            "deep_search_done": True,
            "loop_count": 1,
            "errors": []
        }
        next_node = route_after_verification(state)
        self.assertEqual(next_node, "detect_bias")

    def test_prepare_deep_search(self):
        state: AgentState = {
            "deep_search_done": False,
            "loop_count": 0
        }
        res = prepare_deep_search_node(state)
        self.assertTrue(res["deep_search_done"])
        self.assertEqual(res["loop_count"], 1)


class TestDatabaseService(unittest.TestCase):
    def setUp(self):
        # Set up a temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp()
        settings.database_path = self.db_path
        
        # Initialize schema in temp DB
        # Read the main schema sql file
        schema_path = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")
        db_service.init_db(schema_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_save_and_retrieve_article(self):
        article = {
            "id": "test-id-123",
            "url": "https://example.com/news",
            "title": "Test Article Title",
            "content": "This is the body of the test article.",
            "summary": "This is a summary.",
            "verdict": "TRUE",
            "credibility_score": 90,
            "bias_rating": "Center",
            "tone_rating": "Neutral"
        }
        claims = [
            {
                "id": "claim-1",
                "claim_text": "Test claim text",
                "verdict": "TRUE",
                "explanation": "Supported by science"
            }
        ]
        evidences = [
            {
                "id": "evidence-1",
                "claim_id": "claim-1",
                "source_domain": "apnews.com",
                "source_url": "https://apnews.com/ref",
                "source_title": "AP News Reference",
                "snippet": "Test claim text is absolutely correct.",
                "type": "SUPPORTING",
                "relevance_score": 0.95
            }
        ]
        
        # Save to DB
        saved_id = db_service.save_article(article, claims, evidences)
        self.assertEqual(saved_id, "test-id-123")
        
        # Fetch details
        details = db_service.get_article_details("test-id-123")
        self.assertIsNotNone(details)
        self.assertEqual(details["title"], "Test Article Title")
        self.assertEqual(len(details["claims"]), 1)
        self.assertEqual(details["claims"][0]["claim_text"], "Test claim text")
        self.assertEqual(len(details["claims"][0]["evidences"]), 1)
        self.assertEqual(details["claims"][0]["evidences"][0]["source_domain"], "apnews.com")

        # Fetch history
        history = db_service.get_articles_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], "test-id-123")

if __name__ == "__main__":
    unittest.main()
