# Pedagogical Assistant

AI-powered grading and feedback system for cybersecurity & programming courses.
Teachers upload course materials; students submit code; the system grades automatically
using LangGraph, Gemini, ChromaDB (RAG), and MongoDB Atlas — with full observability
via LangSmith.

---

## Architecture

```
Frontend (React + Vite)
    └── FastAPI Backend
            ├── course_setup_pipeline    ← one-time per course
            ├── lesson_upload_pipeline   ← once per lesson
            └── LangGraph grading graph  ← per student submission
                    ├── analyze
                    ├── retrieve  (ChromaDB RAG)
                    ├── evaluate
                    ├── feedback  ┐ parallel
                    └── score     ┘

Storage
  MongoDB Atlas  — courses, lessons, submissions
  ChromaDB       — lesson vectors (les_*) + course book vectors (course_*)

Observability
  LangSmith — every pipeline + every LLM call is a named, structured trace
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Backend |
| Node.js | 18+ | Frontend |
| Ollama | latest | Embeddings (`nomic-embed-text`) |
| MongoDB Atlas | any | Document store |

---

## Setup

### 1. Clone & create virtual environment

```powershell
git clone <repo-url>
cd pedagogical_assistant_ui
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install Python dependencies

```powershell
cd backend
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```powershell
cd ..   # back to repo root
npm install
```

### 4. Configure environment

Copy `.env.example` to `.env` and fill in:

```dotenv
# MongoDB
MONGODB_URI=mongodb+srv://<user>:<pass>@cluster0.xxx.mongodb.net/
DB_NAME=pedagogical_assistant

# Gemini (primary LLM)
GOOGLE_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash

# Ollama fallback LLM
OLLAMA_MODEL=qwen2.5:7b

# LangSmith observability
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=pedagogical_assistant
```

### 5. Pull Ollama embedding model

```bash
ollama pull nomic-embed-text
```

---

## Running

### Backend

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs: http://localhost:8000/docs

### Frontend

```powershell
cd frontend
npm run dev
```

UI: http://localhost:5173 (or next available port)

---

## API Overview

### Course setup (one-time)

```
POST /api/courses
  course_id, course_name, n_lessons
  course_book_file  (PDF — can be 200+ pages)
  syllabus_file     (PDF/DOCX — topics auto-extracted per lesson via LLM)
```

What happens inside (`course_setup_pipeline`, visible in LangSmith):
1. Extract course book text
2. Extract syllabus text
3. **LLM call** — map every lesson number to its allowed topics
4. Index full course book into ChromaDB (`course_<id>` collection)
5. Save course document to MongoDB

### Lesson upload

```
POST /api/lessons
  course_id, lesson_key, lesson_number
  lecture_file, assignment_file, solution_file
  rubric_file  (optional — enables automatic numeric scoring)
```

What happens inside (`lesson_upload_pipeline`, visible in LangSmith):
1. Extract lecture / assignment / solution text (parallel)
2. Extract rubric text (if provided)
3. Resolve allowed topics from `courses.syllabus_topics` in MongoDB
4. Save lesson to MongoDB (stores `langsmith_upload_trace_id`)
5. Index lesson texts into ChromaDB (`les_<lesson_key>` collection)

### Student submission → AI grading

```
POST /api/submissions
  student_name, student_id
  lesson_id or lesson_key
  submission_file  (PDF/DOCX/TXT)
```

LangGraph graph (`grading_graph`, visible in LangSmith):
```
analyze → retrieve → evaluate ─┬→ feedback  (Hebrew sandwich feedback)
                                └→ score     (numeric 0-100, requires rubric)
```

`feedback` and `score` run **in parallel** after `evaluate`.
If no rubric was uploaded, `score` returns `null` immediately without an LLM call.

### Instructor approval

```
PATCH /api/submissions/{id}/approve
  final_feedback, final_score
```

---

## LangSmith Traces

Every pipeline is a named parent trace with typed child spans:

| Trace | Child spans |
|---|---|
| `course_setup_pipeline` | extract_course_book_text, extract_syllabus_text, **extract_all_lessons_topics** (LLM), index_course_book_to_chromadb, save_course_to_mongodb |
| `lesson_upload_pipeline` | extract_file_text ×3 (parallel), resolve_allowed_topics, save_lesson_to_mongodb, index_lesson_to_chromadb |
| `grading_graph` | analyze, retrieve, evaluate, **feedback** \|\| **score** (parallel) |

MongoDB documents store `langsmith_upload_trace_id` / `langsmith_setup_trace_id`
for direct navigation from DB → LangSmith trace.

---

## Project Structure

```
backend/app/
  config/
    database.py        — Motor client, lifespan, MongoDB indexes
    llm_config.py      — Gemini primary + Ollama fallback singleton
  graph/
    nodes.py           — analyze, retrieve, evaluate, feedback nodes
    score_node.py      — score node (parallel with feedback)
    workflow.py        — StateGraph compilation + run_grading_graph()
  prompts/
    system_prompts.py  — all ChatPromptTemplates in one place
  schemas/
    models.py          — GraphState TypedDict + Pydantic schemas
  services/
    course_pipeline.py — @traceable course setup pipeline
    lesson_pipeline.py — @traceable lesson upload pipeline
    file_processor.py  — PDF/DOCX/TXT text extraction
    vector_store.py    — ChromaDB index + retrieve (lesson + course)
src/                   — React frontend
```
