"""Shared pytest fixtures for the backend test suite."""
from typing import List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from models import Course, CourseChunk, Lesson


# ---------------------------------------------------------------------------
# API request/response models, mirrored from app.py.
#
# app.py mounts StaticFiles(directory="../frontend") at import time, which
# doesn't exist in the test environment and would raise on import. Rather
# than importing the real app, we rebuild the API surface here against a
# mock RAGSystem so endpoint behavior can be tested in isolation.
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class Source(BaseModel):
    text: str
    url: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


def create_test_app(rag_system) -> FastAPI:
    """Build a FastAPI app exposing the same routes as app.py, backed by the given rag_system."""
    app = FastAPI(title="Course Materials RAG System")

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()

            answer, sources = rag_system.query(request.query, session_id)

            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        rag_system.session_manager.clear_session(session_id)
        return {"status": "ok"}

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/")
    async def root():
        # Stands in for the static frontend index served by app.py's StaticFiles mount.
        return {"message": "Course Materials RAG System API"}

    return app


@pytest.fixture
def mock_rag_system():
    """A MagicMock standing in for RAGSystem, pre-wired with sane default return values."""
    mock = MagicMock()
    mock.session_manager.create_session.return_value = "test-session-1"
    mock.query.return_value = (
        "This is a test answer.",
        [{"text": "Course A - Lesson 1", "url": "https://example.com/lesson1"}],
    )
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    return mock


@pytest.fixture
def test_app(mock_rag_system):
    return create_test_app(mock_rag_system)


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Shared course data fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_lesson():
    return Lesson(lesson_number=1, title="Introduction", lesson_link="https://example.com/lesson1")


@pytest.fixture
def sample_course(sample_lesson):
    return Course(
        title="Course A",
        course_link="https://example.com/course-a",
        instructor="Jane Doe",
        lessons=[sample_lesson],
    )


@pytest.fixture
def sample_course_chunks(sample_course):
    return [
        CourseChunk(
            content="Introductory content about Course A.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="More content about Course A.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=1,
        ),
    ]
