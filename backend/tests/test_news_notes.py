import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import CurrentUser, get_current_user
from backend.app.database import Base, get_session
from backend.app.main import app
from backend.app.parser import parse_note


class NewsNoteTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.session = sessionmaker(bind=engine)()

        def session_override():
            yield self.session

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("user-1", "user@example.com", "User")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()

    def test_news_note_keeps_optional_article_url_as_a_source_reference(self):
        response = self.client.post("/api/notes", json={
            "note_type": "news",
            "body": "Company announced a product update. $AAPL #product",
            "source_url": "https://EXAMPLE.com/news/product-update/",
        })
        self.assertEqual(response.status_code, 200)
        note = response.json()
        self.assertEqual(note["type"], "news")
        self.assertEqual(note["sources"], [{"id": note["sources"][0]["id"], "title": None, "url": "https://example.com/news/product-update"}])

        repeated = self.client.post("/api/notes", json={
            "note_type": "news", "body": "A second take on the same announcement.",
            "source_url": "https://example.com/news/product-update",
        })
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(len(self.client.get("/api/sources").json()), 1)

    def test_news_note_accepts_no_url_and_rejects_invalid_url(self):
        no_url = self.client.post("/api/notes", json={"note_type": "news", "body": "Headline without a link."})
        self.assertEqual(no_url.status_code, 200)
        self.assertEqual(no_url.json()["sources"], [])
        invalid = self.client.post("/api/notes", json={"note_type": "news", "body": "Bad link.", "source_url": "example.com"})
        self.assertEqual(invalid.status_code, 422)

    def test_human_friendly_type_shortcuts_are_parsed(self):
        for shortcut, note_type in [("/news", "news"), ("/idea", "idea"), ("/obs", "observation"), ("/th", "thesis")]:
            parsed = parse_note(f"{shortcut} Major development", "note")
            self.assertEqual(parsed["note_type"], note_type)
            self.assertEqual(parsed["clean_body"], "Major development")

    @patch("backend.app.main.YFinanceMarketDataProvider")
    def test_plain_capture_publishes_without_market_data(self, provider_class):
        response = self.client.post("/api/notes/publish", json={"note_type": "news", "body": "A headline worth saving."})
        self.assertEqual(response.status_code, 200)
        provider_class.assert_not_called()

    def test_capture_title_excludes_first_line_commands_and_metadata(self):
        response = self.client.post("/api/notes", json={
            "body": "/idea $AAPL #product Metadata-only first line https://example.com/article\nA clean title\nSupporting context stays in the body.",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["type"], "idea")
        self.assertEqual(response.json()["title"], "A clean title")


if __name__ == "__main__":
    unittest.main()
