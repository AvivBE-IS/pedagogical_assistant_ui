"""
Pedagogical Assistant — FastAPI Backend
Architecture: 4-node LangGraph state machine for modular, debuggable grading.
  analyze -> retrieve -> evaluate -> feedback -> END
"""

import os
from dotenv import load_dotenv

# Load .env from the project root (one level above backend/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

import re
import io
from datetime import datetime, timezone
from typing import TypedDict

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
import motor.motor_asyncio
from bson import ObjectId
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Configuration — hard-coded for demo purposes
# ---------------------------------------------------------------------------
MONGODB_URI = (
    "mongodb+srv://avivbe95_db_user:aviv147"
    "@pedalogicalassisstant.fqwfon4.mongodb.net/"
    "?retryWrites=true&w=majority"
)
DB_NAME = "pedagogical_assistant"

# Ollama — sole LLM engine (runs locally, no API key required)
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"

# ---------------------------------------------------------------------------
# App + CORS (allow all origins for local development)
# ---------------------------------------------------------------------------
app = FastAPI(title="Pedagogical Assistant API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# MongoDB (motor — async)
# ---------------------------------------------------------------------------
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = mongo_client[DB_NAME]

# ---------------------------------------------------------------------------
# Shared LLM instance — used by all 4 graph nodes
# temperature=0.0 -> deterministic output (prevents language / token collapse)
# ---------------------------------------------------------------------------
_llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.0,
    num_ctx=16384,
)

# ===========================================================================
# LANGGRAPH STATE MACHINE
# ===========================================================================

# ---------------------------------------------------------------------------
# Graph state — carries all data between nodes
# ---------------------------------------------------------------------------
class GraphState(TypedDict):
    # Input fields: populated once before the graph is invoked
    code: str
    assignment_text: str
    official_solution: str
    grading_rubric: str
    allowed_topics: str
    lesson_number: int
    # Pipeline stage outputs: each node writes its own field
    analysis: str
    retrieved_context: str
    evaluation: str
    feedback: str


# ---------------------------------------------------------------------------
# Node 1: analyze — structural code analysis
# ---------------------------------------------------------------------------
_analyze_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are an expert code reviewer. Your only task is to analyze a "
            "student's code submission and describe its structure, patterns, "
            "and any obvious issues. Be brief, factual, and objective. "
            "Do NOT grade or give pedagogical feedback yet."
        ),
    ),
    (
        "human",
        (
            "=== ASSIGNMENT ===\n{assignment_text}\n\n"
            "=== STUDENT CODE ===\n{code}\n\n"
            "Analyze the structure of this submission:\n"
            "1. What does the code attempt to do?\n"
            "2. Which programming concepts and patterns are used?\n"
            "3. Are there syntax errors, logic errors, or missing parts?\n"
            "Keep your analysis under 300 words."
        ),
    ),
])


async def analyze(state: GraphState) -> dict:
    """Node 1: Perform initial structural analysis of the student's code."""
    chain = _analyze_prompt | _llm
    result = await chain.ainvoke(
        {
            "assignment_text": state["assignment_text"],
            "code": state["code"],
        }
    )
    return {"analysis": result.content.strip()}


# ---------------------------------------------------------------------------
# Node 2: retrieve — package rubric and context for the evaluator
# Placeholder: assembles a structured string from already-extracted fields.
# Future extension: replace with a vector-store lookup against lecture files.
# ---------------------------------------------------------------------------
async def retrieve(state: GraphState) -> dict:
    """
    Node 2: Retrieve and assemble all grading context into a single string.
    Currently a structured formatter; extend with vector store RAG if needed.
    """
    ctx = (
        f"=== ALLOWED TOPICS (lessons 1-{state['lesson_number']}) ===\n"
        f"{state['allowed_topics']}\n\n"
        f"=== OFFICIAL SOLUTION ===\n{state['official_solution']}\n\n"
        f"=== GRADING RUBRIC ===\n{state['grading_rubric']}"
    )
    return {"retrieved_context": ctx}


# ---------------------------------------------------------------------------
# Node 3: evaluate — assess quality and cheating risk
# ---------------------------------------------------------------------------
_evaluate_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a generous and encouraging senior instructor at a high school "
            "cybersecurity and programming program. "
            "Evaluate the student's submission using the code analysis and grading context. "
            "Your evaluation must have an encouraging and generous bias — assume the student "
            "tried their best and look for partial credit opportunities wherever possible. "
            "Be specific about what the student got right and what needs improvement."
        ),
    ),
    (
        "human",
        (
            "=== CODE ANALYSIS ===\n{analysis}\n\n"
            "=== GRADING CONTEXT ===\n{retrieved_context}\n\n"
            "=== STUDENT CODE ===\n{code}\n\n"
            "Evaluate this submission:\n"
            "1. What did the student do well? Give specific examples.\n"
            "2. What needs improvement? Be constructive.\n"
            "3. What is a good next step for this student?\n"
            "4. Did the student use any forbidden topics NOT listed in the allowed topics?\n\n"
            "End your evaluation with exactly one of these lines (no other text after it):\n"
            "CHEATING_VERDICT: YES\n"
            "CHEATING_VERDICT: NO"
        ),
    ),
])


async def evaluate(state: GraphState) -> dict:
    """Node 3: Evaluate the submission against the rubric with an encouraging bias."""
    chain = _evaluate_prompt | _llm
    result = await chain.ainvoke(
        {
            "analysis": state["analysis"],
            "retrieved_context": state["retrieved_context"],
            "code": state["code"],
        }
    )
    return {"evaluation": result.content.strip()}


# ---------------------------------------------------------------------------
# Node 4: feedback — format final output as Hebrew 3-section markdown
# ---------------------------------------------------------------------------
_feedback_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "אתה מדריך בכיר בתוכנית סייבר ותכנות לתיכון מצוין.\n"
            "משימתך: לעצב את הערכת הקוד כמשוב פדגוגי בעברית תקנית.\n\n"
            "===== חוק שפה מוחלט =====\n"
            "כתוב את כל התגובה בעברית בלבד.\n"
            "אסור לחלוטין: תווים סיניים, אנגלית, ערבית, ספרדית, יפנית, או כל שפה אחרת.\n"
            "אם אתה מוצא את עצמך חושב בשפה אחרת — תרגם מיד לעברית ואז כתוב.\n"
            "===========================\n\n"
            "מבנה חובה (שיטת הסנדוויץ'):\n"
            "פרק 1 בכותרת ### דברים טובים בפתרון\n"
            "פרק 2 בכותרת ### נקודות לשיפור\n"
            "פרק 3 בכותרת ### המשך עבודה\n\n"
            "לאחר שלושת הפרקים, בשורה נפרדת בלבד, כתוב:\n"
            "CHEATING_VERDICT: YES\n"
            "או\n"
            "CHEATING_VERDICT: NO\n\n"
            "חוקי סגנון:\n"
            "אל תשתמש במקפים. השתמש בפסיקים ונקודות.\n"
            "טון מעודד ומקצועי לבני נוער.\n"
            "אל תזכיר שאתה בינה מלאכותית."
        ),
    ),
    (
        "human",
        (
            "=== EVALUATION ===\n{evaluation}\n\n"
            "Based on the evaluation above, write the full pedagogical feedback in Hebrew "
            "following the required 3-section sandwich format.\n"
            "Preserve the CHEATING_VERDICT from the evaluation exactly as-is on the final line."
        ),
    ),
])


async def feedback(state: GraphState) -> dict:
    """Node 4: Format the evaluation into the strict 3-section Hebrew markdown structure."""
    chain = _feedback_prompt | _llm
    result = await chain.ainvoke({"evaluation": state["evaluation"]})
    return {"feedback": result.content.strip()}


# ---------------------------------------------------------------------------
# Build and compile the LangGraph state machine
# ---------------------------------------------------------------------------
_workflow = StateGraph(GraphState)
_workflow.add_node("analyze", analyze)
_workflow.add_node("retrieve", retrieve)
_workflow.add_node("evaluate", evaluate)
_workflow.add_node("feedback", feedback)

_workflow.set_entry_point("analyze")
_workflow.add_edge("analyze", "retrieve")
_workflow.add_edge("retrieve", "evaluate")
_workflow.add_edge("evaluate", "feedback")
_workflow.add_edge("feedback", END)

grading_graph = _workflow.compile()


# ---------------------------------------------------------------------------
# Graph runner — called by the submissions endpoint
# ---------------------------------------------------------------------------
async def run_grading_graph(
    student_code: str,
    assignment_text: str,
    official_solution: str,
    grading_rubric: str,
    allowed_topics: str = "general",
    lesson_number: int = 1,
    run_name: str = "grading_graph",
    metadata: dict | None = None,
) -> tuple[str, bool]:
    """
    Execute the 4-node grading graph and return (feedback_text, cheating_flag).
    run_name -> LangSmith trace label (set to the submitted filename).
    metadata -> key/value evidence visible in the LangSmith Metadata tab.
    """
    initial_state: GraphState = {
        "code": student_code,
        "assignment_text": assignment_text,
        "official_solution": official_solution,
        "grading_rubric": grading_rubric,
        "allowed_topics": allowed_topics,
        "lesson_number": lesson_number,
        # Output fields start empty; nodes populate them in sequence
        "analysis": "",
        "retrieved_context": "",
        "evaluation": "",
        "feedback": "",
    }

    final_state = await grading_graph.ainvoke(
        initial_state,
        config={
            "run_name": run_name,
            "metadata": metadata or {},
        },
    )

    raw_feedback = final_state["feedback"]

    # Parse cheating verdict embedded by the feedback node
    cheating_flag = bool(re.search(r"CHEATING_VERDICT:\s*YES", raw_feedback, re.IGNORECASE))

    # Strip the verdict line — internal metadata, not shown to students
    clean_fb = re.sub(
        r"\nCHEATING_VERDICT:\s*(YES|NO)\s*$", "", raw_feedback, flags=re.IGNORECASE
    ).strip()

    # Post-process: remove any stray non-Hebrew characters that are not
    # digits, punctuation, whitespace, or Markdown markers (#, *, etc.)
    clean_fb = re.sub(
        r"[^\u05d0-\u05ea\u05f0-\u05f4\s\d.,!?()'\"\\[\]#/:*\-\u2013\u2014\n]",
        "",
        clean_fb,
    )

    return clean_fb, cheating_flag


# ---------------------------------------------------------------------------
# Utility: clean extracted text
# ---------------------------------------------------------------------------
def clean_text(raw: str) -> str:
    """
    Post-process extracted text:
    - Normalize line endings (CRLF / CR -> LF)
    - Collapse runs of spaces/tabs within a line to a single space
    - Drop lines that contain no Hebrew/Latin letters and no digits
      (page numbers, separator lines, lone punctuation, etc.)
    - Collapse 3+ consecutive blank lines to one blank line
    - Strip leading/trailing whitespace
    """
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in raw.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        # Keep the line only if it has at least one real character
        if line and not re.search(r"[\u05d0-\u05eaa-zA-Z0-9]", line):
            continue
        lines.append(line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return text.strip()


# ---------------------------------------------------------------------------
# Utility: extract plain text from a PDF byte stream
# ---------------------------------------------------------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Use PyMuPDF (fitz) to extract all text from a PDF.
    Returns a single concatenated, cleaned string.
    Raises ValueError if the bytes are not a valid PDF.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text() for page in doc]
        return clean_text("\n\n".join(pages))
    except Exception as exc:
        raise ValueError(f"Failed to parse PDF: {exc}") from exc


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Dispatch text extraction based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext == "txt":
        try:
            raw = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw = file_bytes.decode("latin-1")
        return clean_text(raw)
    elif ext in ("docx", "doc"):
        try:
            doc = DocxDocument(io.BytesIO(file_bytes))
            raw = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return clean_text(raw)
        except Exception as exc:
            raise ValueError(f"Failed to parse DOCX: {exc}") from exc
    else:
        # Fallback: try PDF first, then plain text
        try:
            return extract_text_from_pdf(file_bytes)
        except ValueError:
            try:
                raw = file_bytes.decode("utf-8")
                return clean_text(raw)
            except Exception as exc:
                raise ValueError(f"Unsupported file type: {filename}") from exc


async def extract_topics_from_syllabus(syllabus_text: str, lesson_number: int) -> str:
    """
    Use the LLM to infer the topics taught up to lesson_number from the syllabus.
    Returns a comma-separated Hebrew list of topic names.
    """
    _topic_prompt = ChatPromptTemplate.from_messages([
        ("system", "אנה עוזר מדויק. החזר רשימה בעברית של נושאים ללא נוסף. אנגלית אסור."),
        ("human", (
            "הסילבוס הבא:\n\n{syllabus}\n\n"
            "רשום את כל הנושאים שנלמדו בשיעורים 1 עד {n} בלבד. "
            "החזר רשימה מופרדתבפסיקים בעברית בלבד. ללא הסברות."
        )),
    ])
    _topic_chain = _topic_prompt | _llm
    try:
        res = await _topic_chain.ainvoke({"syllabus": syllabus_text[:8000], "n": lesson_number})
        topics = res.content.strip()
        # Keep only Hebrew, digits, commas, spaces
        topics = re.sub(r"[^\u05d0-\u05ea\u05f0-\u05f4\s,\d]", "", topics).strip()
        return topics if topics else "general"
    except Exception:
        return "general"


# ---------------------------------------------------------------------------
# Utility: make a MongoDB document JSON-serialisable
# ---------------------------------------------------------------------------
def serialise(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    return doc


# ===========================================================================
# LESSON ROUTES
# ===========================================================================


@app.post("/api/lessons", summary="Upload a new lesson with PDF materials")
async def create_lesson(
    course_id: str = Form(..., description="e.g. 'course-1'"),
    lesson_key: str = Form(..., description="Frontend lesson ID, e.g. 'c1-s1-l1'"),
    lesson_number: int = Form(0, description="Leave 0 to auto-derive from lesson_key"),
    grading_rubric: str = Form(
        "\u05d1\u05d3\u05d5\u05e7 \u05e0\u05db\u05d5\u05e0\u05d5\u05ea, \u05e9\u05d9\u05de\u05d5\u05e9 \u05d1\u05e0\u05d5\u05e9\u05d0\u05d9\u05dd \u05de\u05d5\u05ea\u05e8\u05d9\u05dd \u05d5\u05d0\u05d9\u05db\u05d5\u05ea \u05d4\u05e7\u05d5\u05d3.",
        description="Free-text rubric for the AI",
    ),
    allowed_topics: str = Form(
        "general", description="Comma-separated list, e.g. 'recursion,base-case'"
    ),
    lecture_file: UploadFile = File(..., description="Lecture file (PDF/DOCX/TXT)"),
    assignment_file: UploadFile = File(..., description="Assignment file"),
    solution_file: UploadFile = File(..., description="Solution file"),
    rubric_file: UploadFile = File(None, description="Grading rubric file (optional)"),
    syllabus_file: UploadFile = File(None, description="Syllabus file — topics auto-inferred"),
):
    """
    Accepts three PDF files (lecture, assignment, solution), extracts their
    text, and upserts the lesson document in MongoDB keyed by lesson_key.
    Re-uploading materials for the same lesson_key updates the existing record.
    """
    # Auto-derive lesson_number from key when not provided (c1-s1-l3 -> 3)
    if lesson_number == 0:
        try:
            lesson_number = int(lesson_key.rsplit("-l", 1)[-1])
        except (ValueError, IndexError):
            lesson_number = 0

    # Read uploaded files
    lecture_bytes = await lecture_file.read()
    assignment_bytes = await assignment_file.read()
    solution_bytes = await solution_file.read()

    # Extract text from files (PDF, DOCX, or TXT)
    try:
        lecture_text = extract_text(lecture_bytes, lecture_file.filename or "")
        assignment_text = extract_text(assignment_bytes, assignment_file.filename or "")
        solution_text = extract_text(solution_bytes, solution_file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Extract rubric text from uploaded file if provided (overrides form field)
    if rubric_file and rubric_file.filename:
        rubric_bytes = await rubric_file.read()
        try:
            grading_rubric = extract_text(rubric_bytes, rubric_file.filename or "")
        except ValueError:
            pass  # keep the form field value

    # Auto-infer allowed topics from syllabus if provided
    if syllabus_file and syllabus_file.filename:
        syllabus_bytes = await syllabus_file.read()
        try:
            syllabus_text = extract_text(syllabus_bytes, syllabus_file.filename or "")
            allowed_topics = await extract_topics_from_syllabus(syllabus_text, lesson_number)
        except ValueError:
            pass  # keep the form field value

    lesson_doc = {
        "course_id": course_id,
        "lesson_key": lesson_key,
        "lesson_number": lesson_number,
        "lecture_file_url": lecture_file.filename,
        "assignment_file_url": assignment_file.filename,
        "solution_file_url": solution_file.filename,
        "lecture_context": lecture_text,
        "assignment_context": assignment_text,
        "solution_context": solution_text,
        "grading_rubric": grading_rubric,
        "allowed_topics": [t.strip() for t in allowed_topics.split(",")],
        "updated_at": datetime.now(timezone.utc),
    }

    # Upsert: update if lesson_key already exists, insert otherwise
    await db.lessons.update_one(
        {"lesson_key": lesson_key},
        {"$set": lesson_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    saved = await db.lessons.find_one({"lesson_key": lesson_key})
    return serialise(saved)


@app.get("/api/lessons/{lesson_id}", summary="Get a lesson by ID")
async def get_lesson(lesson_id: str):
    try:
        oid = ObjectId(lesson_id)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid lesson_id format")

    lesson = await db.lessons.find_one({"_id": oid})
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return serialise(lesson)


@app.get("/api/lessons", summary="List all lessons (optionally filter by course)")
async def list_lessons(course_id: str | None = None):
    query = {"course_id": course_id} if course_id else {}
    cursor = db.lessons.find(query, {"lecture_context": 0})  # omit large field
    lessons = await cursor.to_list(length=200)
    return [serialise(l) for l in lessons]


# ===========================================================================
# SUBMISSION ROUTES
# ===========================================================================


@app.post("/api/submissions", summary="Submit a student file for AI review")
async def create_submission(
    student_name: str = Form(...),
    student_id: str = Form(...),
    lesson_id: str = Form(None, description="MongoDB ObjectId of the lesson"),
    lesson_key: str = Form(None, description="Frontend lesson ID, e.g. 'c1-s1-l1'"),
    submission_file: UploadFile = File(..., description="Student work PDF"),
):
    """
    1. Resolves the lesson by lesson_id (ObjectId) or lesson_key (frontend string).
    2. Runs the single LangChain grading pipeline (ChatPromptTemplate | ChatOllama).
    3. Saves the submission document to MongoDB.
    """
    # Resolve lesson by ObjectId or lesson_key
    lesson = None
    if lesson_id:
        try:
            oid = ObjectId(lesson_id)
            lesson = await db.lessons.find_one({"_id": oid})
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid lesson_id format")
    elif lesson_key:
        lesson = await db.lessons.find_one({"lesson_key": lesson_key})
    else:
        raise HTTPException(status_code=422, detail="Provide lesson_id or lesson_key")

    if not lesson:
        raise HTTPException(
            status_code=404,
            detail="Lesson not found. Create it first via POST /api/lessons.",
        )

    # Extract lesson context fields
    assignment_ctx = lesson.get("assignment_context", "")
    solution_ctx = lesson.get("solution_context", "")
    lesson_rubric = lesson.get(
        "grading_rubric", "Check correctness, use of allowed topics, and code quality."
    )

    # Extract text from the student's submitted file (PDF, DOCX, or TXT)
    file_bytes = await submission_file.read()
    try:
        extracted_code = extract_text(file_bytes, submission_file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    resolved_lesson_key = lesson.get("lesson_key") or lesson_key or ""

    # LangSmith metadata — visible in every trace as evidence that each
    # context file was loaded and its extracted text was sent to the LLM.
    langsmith_metadata = {
        "student_name":     student_name,
        "student_file":     submission_file.filename,
        "lesson_key":       resolved_lesson_key,
        "lecture_file":     lesson.get("lecture_file_url", "—"),
        "lecture_chars":    len(lesson.get("lecture_context", "")),
        "assignment_file":  lesson.get("assignment_file_url", "—"),
        "assignment_chars": len(assignment_ctx),
        "solution_file":    lesson.get("solution_file_url", "—"),
        "solution_chars":   len(solution_ctx),
        "rubric_chars":     len(lesson_rubric),
        "rubric_preview":   lesson_rubric[:120].replace("\n", " "),
        "allowed_topics":   ", ".join(lesson.get("allowed_topics", ["general"])),
        "submission_chars": len(extracted_code),
    }

    ai_provider = "ollama"
    cheating_flag = False
    try:
        ai_feedback, cheating_flag = await run_grading_graph(
            student_code=extracted_code,
            assignment_text=assignment_ctx,
            official_solution=solution_ctx,
            grading_rubric=lesson_rubric,
            allowed_topics=", ".join(lesson.get("allowed_topics", ["general"])),
            lesson_number=lesson.get("lesson_number", 1),
            run_name=submission_file.filename,
            metadata=langsmith_metadata,
        )
    except Exception as exc:
        ai_feedback = f"שגיאה בתהליך הבדיקה האוטומטית. אנא פנה למדריך. ({exc})"
        ai_provider = "error"

    submission_doc = {
        "student_name": student_name,
        "student_id": student_id,
        "lesson_id": lesson_id or "",
        "lesson_key": resolved_lesson_key,
        "submitted_file_url": submission_file.filename,
        "extracted_code": extracted_code,
        "ai_feedback_draft": ai_feedback,
        "recommended_score": 0,   # score is set by instructor during approval
        "cheating_flag": cheating_flag,
        "ai_provider": ai_provider,
        "instructor_final_feedback": None,
        "approved_at": None,
        "created_at": datetime.now(timezone.utc),
    }

    result = await db.submissions.insert_one(submission_doc)
    submission_doc["_id"] = str(result.inserted_id)
    return submission_doc


@app.patch(
    "/api/submissions/{submission_id}/approve",
    summary="Instructor approves and finalises feedback",
)
async def approve_submission(
    submission_id: str,
    final_feedback: str = Form(...),
    final_score: int = Form(...),
):
    try:
        oid = ObjectId(submission_id)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid submission_id format")

    result = await db.submissions.update_one(
        {"_id": oid},
        {
            "$set": {
                "instructor_final_feedback": final_feedback,
                "recommended_score": final_score,
                "approved_at": datetime.now(timezone.utc),
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"message": "Submission approved", "submission_id": submission_id}


@app.get(
    "/api/submissions/lesson/{lesson_id}",
    summary="Get all submissions for a lesson",
)
async def get_submissions_by_lesson(lesson_id: str):
    cursor = db.submissions.find({"lesson_id": lesson_id})
    submissions = await cursor.to_list(length=200)
    return [serialise(s) for s in submissions]


@app.get(
    "/api/submissions/{submission_id}",
    summary="Get a single submission by ID",
)
async def get_submission(submission_id: str):
    try:
        oid = ObjectId(submission_id)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid submission_id format")

    submission = await db.submissions.find_one({"_id": oid})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return serialise(submission)


# ===========================================================================
# REVIEW ROUTES (instructor-approved reviews, keyed by frontend lesson ID)
# ===========================================================================


@app.post("/api/reviews", summary="Save an instructor-approved review")
async def create_review(
    lesson_key: str = Form(..., description="Frontend lesson ID, e.g. 'c1-s1-l1'"),
    student_id: str = Form(...),
    student_name: str = Form(...),
    file_name: str = Form(...),
    score: int = Form(...),
    cheating_risk: str = Form(...),
    feedback: str = Form(...),
):
    """Persists an approved review without requiring a pre-created lesson document."""
    doc = {
        "lesson_key": lesson_key,
        "student_id": student_id,
        "student_name": student_name,
        "file_name": file_name,
        "score": score,
        "cheating_risk": cheating_risk,
        "feedback": feedback,
        "approved_at": datetime.now(timezone.utc),
    }
    # Upsert: one approved review per (lesson_key, student_id) pair
    await db.reviews.update_one(
        {"lesson_key": lesson_key, "student_id": student_id},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True}


@app.get(
    "/api/reviews/lesson/{lesson_key:path}",
    summary="Fetch all approved reviews for a lesson",
)
async def get_reviews_by_lesson(lesson_key: str):
    cursor = db.reviews.find({"lesson_key": lesson_key})
    reviews = await cursor.to_list(length=500)
    return [serialise(r) for r in reviews]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "db": DB_NAME, "ai_model": OLLAMA_MODEL}


# ---------------------------------------------------------------------------
# Entry point (python main.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
