# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Management

Always use `uv` for all dependency and environment management — never `pip` directly.

```bash
uv sync          # install/update dependencies
uv add <pkg>     # add a new dependency
uv remove <pkg>  # remove a dependency
uv run <cmd>     # run a command in the project environment
uv run python <file>.py  # run a Python file
```

## Running the Application

```bash
# Install dependencies (always use uv, never pip)
uv sync

# Start the server (from project root)
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000
```

Requires a `.env` file in the project root:
```
ANTHROPIC_API_KEY=your_key_here
```

- Web UI: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

On startup, the server loads all `.txt`/`.pdf`/`.docx` files from `../docs` into ChromaDB automatically (skipping courses already indexed).

## Architecture

This is a RAG (Retrieval-Augmented Generation) system. The backend is a FastAPI app in `backend/`; the frontend is static HTML/JS in `frontend/` served by FastAPI.

### Query flow

1. `frontend/script.js` POSTs `{ query, session_id }` to `POST /api/query`
2. `app.py` creates a session if needed, then calls `RAGSystem.query()`
3. `rag_system.py` fetches conversation history from `SessionManager`, then calls `AIGenerator.generate_response()`
4. `ai_generator.py` makes a first Claude API call with the `search_course_content` tool available
5. If Claude decides to search (course-specific questions), it invokes `CourseSearchTool.execute()` → `VectorStore.search()` → ChromaDB semantic search → results injected into a second Claude API call
6. If Claude answers directly (general knowledge), no second call is made
7. Sources and response return up the chain; session history is updated

### Key design decisions

- **Agentic tool use**: Claude autonomously decides when to search. There is no pre-fetch of context — retrieval only happens if Claude determines it's needed.
- **Two ChromaDB collections**: `course_catalog` (course-level metadata for fuzzy course name resolution) and `course_content` (chunked lesson text for semantic search). Course name in a query is resolved via vector search against `course_catalog` before filtering `course_content`.
- **Session history is in-memory only**: `SessionManager` stores sessions in a plain dict; history is lost on server restart. `MAX_HISTORY=2` means only the last 2 exchanges are kept.
- **Conversation history is injected into the system prompt** (not as message turns) — see `ai_generator.py:61`.
- **Document deduplication on startup**: `add_course_folder()` checks `get_existing_course_titles()` and skips courses already in ChromaDB, so restarting the server is safe.

### Document format

Course `.txt` files must follow this structure:
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <title>
Lesson Link: <url>
<lesson content>

Lesson 1: <title>
...
```

`DocumentProcessor` chunks lesson text into ~800-character sentence-aware segments with 100-character overlap. The first chunk of each lesson is prefixed with `"Lesson N content: ..."` for retrieval context.

### Configuration

All tuneable values live in `backend/config.py`:

| Setting | Default | Purpose |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Claude model |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer for embeddings |
| `CHUNK_SIZE` | 800 | Max characters per chunk |
| `CHUNK_OVERLAP` | 100 | Overlap between consecutive chunks |
| `MAX_RESULTS` | 5 | Max chunks returned per search |
| `MAX_HISTORY` | 2 | Conversation exchanges retained per session |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistence directory (relative to `backend/`) |

### Adding a new tool

1. Subclass `Tool` in `backend/search_tools.py`, implementing `get_tool_definition()` and `execute()`
2. Register it in `RAGSystem.__init__()` via `self.tool_manager.register_tool(your_tool)`
3. Claude will automatically have access to it on the next query
