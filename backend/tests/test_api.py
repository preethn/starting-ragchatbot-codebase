"""API endpoint tests for the FastAPI app (/api/query, /api/courses, /).

These tests run against the isolated app built in conftest.py's
create_test_app(), backed by a mocked RAGSystem, so they exercise real
request/response handling without touching ChromaDB, Anthropic, or the
frontend static files.
"""
import pytest


class TestQueryEndpoint:
    def test_query_with_session_id_returns_200(self, client, mock_rag_system):
        response = client.post("/api/query", json={"query": "What is ML?", "session_id": "abc-123"})

        assert response.status_code == 200
        mock_rag_system.query.assert_called_once_with("What is ML?", "abc-123")

    def test_query_without_session_id_creates_one(self, client, mock_rag_system):
        response = client.post("/api/query", json={"query": "What is ML?"})

        assert response.status_code == 200
        mock_rag_system.session_manager.create_session.assert_called_once()
        data = response.json()
        assert data["session_id"] == "test-session-1"

    def test_query_response_shape(self, client):
        response = client.post("/api/query", json={"query": "What is ML?", "session_id": "abc-123"})

        data = response.json()
        assert data["answer"] == "This is a test answer."
        assert data["sources"] == [{"text": "Course A - Lesson 1", "url": "https://example.com/lesson1"}]
        assert data["session_id"] == "abc-123"

    def test_query_missing_query_field_returns_422(self, client):
        response = client.post("/api/query", json={"session_id": "abc-123"})

        assert response.status_code == 422

    def test_query_rag_system_exception_returns_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("search failed")

        response = client.post("/api/query", json={"query": "What is ML?", "session_id": "abc-123"})

        assert response.status_code == 500
        assert "search failed" in response.json()["detail"]

    def test_query_sources_without_url(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("Answer", [{"text": "Course A - Lesson 2", "url": None}])

        response = client.post("/api/query", json={"query": "What is ML?", "session_id": "abc-123"})

        assert response.status_code == 200
        assert response.json()["sources"] == [{"text": "Course A - Lesson 2", "url": None}]


class TestCoursesEndpoint:
    def test_get_courses_returns_200(self, client):
        response = client.get("/api/courses")

        assert response.status_code == 200

    def test_get_courses_response_shape(self, client):
        response = client.get("/api/courses")

        data = response.json()
        assert data["total_courses"] == 2
        assert data["course_titles"] == ["Course A", "Course B"]

    def test_get_courses_exception_returns_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("db unavailable")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert "db unavailable" in response.json()["detail"]


class TestSessionEndpoint:
    def test_delete_session_returns_ok(self, client, mock_rag_system):
        response = client.delete("/api/session/abc-123")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_rag_system.session_manager.clear_session.assert_called_once_with("abc-123")


class TestRootEndpoint:
    def test_root_returns_200(self, client):
        response = client.get("/")

        assert response.status_code == 200
