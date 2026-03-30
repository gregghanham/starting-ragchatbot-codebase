"""
Tests for FastAPI API endpoints (POST /api/query, GET /api/courses).

Uses the `api_client` and `mock_rag_system` fixtures from conftest.py.
The test app mirrors app.py's routes but omits the static-files mount so
no real frontend directory is required.
"""
import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:

    def test_returns_200_on_valid_query(self, api_client):
        response = api_client.post("/api/query", json={"query": "What is backpropagation?"})
        assert response.status_code == 200

    def test_response_contains_answer(self, api_client):
        response = api_client.post("/api/query", json={"query": "What is backpropagation?"})
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_response_contains_sources_list(self, api_client):
        response = api_client.post("/api/query", json={"query": "Tell me about neural networks"})
        data = response.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_response_contains_session_id(self, api_client):
        response = api_client.post("/api/query", json={"query": "What is deep learning?"})
        data = response.json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)

    def test_session_id_generated_when_not_provided(self, api_client, mock_rag_system):
        api_client.post("/api/query", json={"query": "Hello"})
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_provided_session_id_is_preserved_in_response(self, api_client, mock_rag_system):
        response = api_client.post(
            "/api/query",
            json={"query": "Hello", "session_id": "existing-session"},
        )
        assert response.json()["session_id"] == "existing-session"

    def test_provided_session_id_skips_session_creation(self, api_client, mock_rag_system):
        api_client.post(
            "/api/query",
            json={"query": "Hello", "session_id": "existing-session"},
        )
        mock_rag_system.session_manager.create_session.assert_not_called()

    def test_query_text_forwarded_to_rag_system(self, api_client, mock_rag_system):
        api_client.post("/api/query", json={"query": "What is PyTorch?"})
        args, _ = mock_rag_system.query.call_args
        assert args[0] == "What is PyTorch?"

    def test_sources_have_label_field(self, api_client):
        response = api_client.post("/api/query", json={"query": "Neural networks"})
        sources = response.json()["sources"]
        if sources:
            assert "label" in sources[0]

    def test_sources_have_url_field(self, api_client):
        response = api_client.post("/api/query", json={"query": "Neural networks"})
        sources = response.json()["sources"]
        if sources:
            assert "url" in sources[0]

    def test_missing_query_field_returns_422(self, api_client):
        response = api_client.post("/api/query", json={})
        assert response.status_code == 422

    def test_empty_query_still_calls_rag(self, api_client, mock_rag_system):
        api_client.post("/api/query", json={"query": ""})
        mock_rag_system.query.assert_called_once()

    def test_returns_500_when_rag_raises(self, api_client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("Unexpected error")
        response = api_client.post("/api/query", json={"query": "Something"})
        assert response.status_code == 500

    def test_500_detail_contains_error_message(self, api_client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("Database connection failed")
        response = api_client.post("/api/query", json={"query": "Something"})
        assert "Database connection failed" in response.json()["detail"]

    def test_empty_sources_list_is_valid(self, api_client, mock_rag_system):
        mock_rag_system.query.return_value = ("Answer with no sources.", [])
        response = api_client.post("/api/query", json={"query": "General question"})
        assert response.status_code == 200
        assert response.json()["sources"] == []

    def test_multiple_sources_returned(self, api_client, mock_rag_system):
        mock_rag_system.query.return_value = (
            "Answer.",
            [
                {"label": "Course A - Lesson 1", "url": "https://example.com/1"},
                {"label": "Course B - Lesson 3", "url": "https://example.com/3"},
            ],
        )
        response = api_client.post("/api/query", json={"query": "Multi-source question"})
        assert len(response.json()["sources"]) == 2


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:

    def test_returns_200(self, api_client):
        response = api_client.get("/api/courses")
        assert response.status_code == 200

    def test_response_contains_total_courses(self, api_client):
        response = api_client.get("/api/courses")
        assert "total_courses" in response.json()

    def test_total_courses_is_integer(self, api_client):
        response = api_client.get("/api/courses")
        assert isinstance(response.json()["total_courses"], int)

    def test_response_contains_course_titles(self, api_client):
        response = api_client.get("/api/courses")
        data = response.json()
        assert "course_titles" in data
        assert isinstance(data["course_titles"], list)

    def test_total_courses_matches_analytics(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["Python Basics", "Advanced ML"],
        }
        response = api_client.get("/api/courses")
        assert response.json()["total_courses"] == 2

    def test_course_titles_match_analytics(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 2,
            "course_titles": ["Python Basics", "Advanced ML"],
        }
        response = api_client.get("/api/courses")
        titles = response.json()["course_titles"]
        assert "Python Basics" in titles
        assert "Advanced ML" in titles

    def test_empty_course_list_is_valid(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        response = api_client.get("/api/courses")
        assert response.status_code == 200
        assert response.json()["total_courses"] == 0
        assert response.json()["course_titles"] == []

    def test_returns_500_when_analytics_raises(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("Analytics failed")
        response = api_client.get("/api/courses")
        assert response.status_code == 500

    def test_500_detail_contains_error_message(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("ChromaDB error")
        response = api_client.get("/api/courses")
        assert "ChromaDB error" in response.json()["detail"]

    def test_get_course_analytics_called_once(self, api_client, mock_rag_system):
        api_client.get("/api/courses")
        mock_rag_system.get_course_analytics.assert_called_once()
