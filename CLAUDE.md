# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Install dependencies (uses uv, Python 3.13+)
uv sync

# Start the server (from project root)
./run.sh

# Or manually from backend directory
cd backend && uv run uvicorn app:app --reload --port 8000
```

The app serves at `http://localhost:8000` (web UI) and `http://localhost:8000/docs` (API docs).

## Environment Setup

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. The backend also reads from `backend/.env` — both are loaded.

## Architecture

This is a **full-stack RAG (Retrieval-Augmented Generation) chatbot** for querying course materials:

- **Frontend** (`frontend/`): Static HTML/CSS/JS served directly by FastAPI
- **Backend** (`backend/`): FastAPI app with RAG pipeline, runs from the `backend/` directory (all imports are relative to that directory)

### RAG Pipeline Flow

```
User Query → RAGSystem.query()
  → AIGenerator.generate_response() [Claude API with tool_choice=auto]
    → If stop_reason=="tool_use": CourseSearchTool.execute()
      → VectorStore.search() [ChromaDB semantic search]
    → Final Claude response with retrieved context
  → SessionManager.add_exchange() [stores conversation history]
```

### Key Components

| File | Responsibility |
|------|---------------|
| `app.py` | FastAPI routes (`POST /api/query`, `GET /api/courses`), startup doc loading |
| `rag_system.py` | Orchestrator — wires together all components |
| `ai_generator.py` | Anthropic API calls; handles the tool-use loop (one search max per query) |
| `vector_store.py` | ChromaDB wrapper with two collections: `course_catalog` (metadata) and `course_content` (chunks) |
| `document_processor.py` | Parses `.txt`/`.pdf`/`.docx` course files into `Course`/`Lesson`/`CourseChunk` objects |
| `search_tools.py` | `CourseSearchTool` (Anthropic tool definition + execution) and `ToolManager` registry |
| `session_manager.py` | In-memory conversation history, keyed by session ID |
| `models.py` | Pydantic models: `Course`, `Lesson`, `CourseChunk` |
| `config.py` | `Config` dataclass loaded from env vars; singleton `config` imported by `app.py` |

### Course Document Format

Documents in `docs/` must follow this structure for `DocumentProcessor` to parse them correctly:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <lesson title>
Lesson Link: <url>
<lesson content...>

Lesson 1: <lesson title>
Lesson Link: <url>
<lesson content...>
```

The course title serves as the unique ID in ChromaDB. Duplicate titles are skipped on reload.

### ChromaDB Storage

The vector DB persists to `backend/chroma_db/` (relative to where uvicorn runs). Course metadata (titles, links, instructor) goes into `course_catalog`; chunked lesson text goes into `course_content`. The `all-MiniLM-L6-v2` sentence-transformer model handles embeddings locally.

### Tool-Based Search Design

The AI does **not** pre-fetch context before calling Claude. Instead, `search_course_content` is registered as a Claude tool. Claude decides autonomously whether and how to search. The system enforces one search per query via the system prompt. After tool execution, `ToolManager.get_last_sources()` retrieves source attributions for the API response.

### Extending the System

To add a new tool: subclass `Tool` in `search_tools.py`, implement `get_tool_definition()` (returning an Anthropic tool schema) and `execute()`, then register with `tool_manager.register_tool()` in `rag_system.py`.
