"""
End-to-end flow test for the Pedagogical Assistant backend.

Steps:
  1. Health check
  2. Upload lesson context (lecture + assignment + solution PDFs)
  3. Submit a student file for AI grading
  4. Verify the submission result fields
  5. Approve a review (instructor sign-off)
  6. Fetch approved reviews for the lesson

Run:
    python e2e_flow_test.py
"""

import io
import sys
import textwrap
import requests

BASE = "http://localhost:8000"
LESSON_KEY = "e2e-test-c1-s1-l1"

# ---------------------------------------------------------------------------
# Minimal PDF bytes (valid single-page PDF with text)
# ---------------------------------------------------------------------------
def make_pdf(text: str) -> bytes:
    content = textwrap.dedent(f"""\
        %PDF-1.4
        1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
        2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
        3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
        4 0 obj<</Length {len(text) + 50}>>
        stream
        BT /F1 12 Tf 72 720 Td ({text}) Tj ET
        endstream
        endobj
        5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
        xref
        0 6
        0000000000 65535 f
        trailer<</Size 6/Root 1 0 R>>
        startxref
        0
        %%EOF
    """)
    return content.encode("latin-1")


LECTURE_PDF   = make_pdf("Lecture: Python basics - variables, loops, functions")
EXERCISE_PDF  = make_pdf("Exercise: Write a function that returns the sum of a list")
SOLUTION_PDF  = make_pdf("Solution: def sum_list(lst): return sum(lst)")
STUDENT_PDF   = make_pdf("Student answer: def add(lst): total=0 \n for x in lst: total+=x \n return total")

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
errors = []


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        print(f"{PASS} {label}")
    else:
        msg = f"{FAIL} {label}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(label)


# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------
print("\n=== 1. Health check ===")
r = requests.get(f"{BASE}/health", timeout=5)
check("GET /health returns 200", r.status_code == 200)
check("status == ok", r.json().get("status") == "ok", str(r.json()))

# ---------------------------------------------------------------------------
# 2. Upload lesson context
# ---------------------------------------------------------------------------
print("\n=== 2. Upload lesson context ===")
r = requests.post(
    f"{BASE}/api/lessons",
    data={
        "lesson_key":    LESSON_KEY,
        "course_id":     "course-1",
        "lesson_number": "1",
        "grading_rubric": "בדוק נכונות, קריאות קוד ושימוש בפונקציות.",
        "allowed_topics": "לולאות, פונקציות, רשימות",
    },
    files={
        "lecture_file":    ("lecture.pdf",    io.BytesIO(LECTURE_PDF),  "application/pdf"),
        "assignment_file": ("exercise.pdf",   io.BytesIO(EXERCISE_PDF), "application/pdf"),
        "solution_file":   ("solution.pdf",   io.BytesIO(SOLUTION_PDF), "application/pdf"),
    },
    timeout=30,
)
check("POST /api/lessons returns 200", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}")
lesson_id = r.json().get("_id") or r.json().get("id") or r.json().get("lesson_id", "")
check("Response contains lesson id", bool(lesson_id), str(r.json())[:100])

# ---------------------------------------------------------------------------
# 3. Submit student file
# ---------------------------------------------------------------------------
print("\n=== 3. Submit student file for AI grading ===")
r = requests.post(
    f"{BASE}/api/submissions",
    data={
        "lesson_key":   LESSON_KEY,
        "student_id":   "student-e2e-001",
        "student_name": "תלמיד בדיקה",
    },
    files={
        "submission_file": ("student_solution.pdf", io.BytesIO(STUDENT_PDF), "application/pdf"),
    },
    timeout=120,  # AI grading can take time
)
check("POST /api/submissions returns 200", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}")

if r.status_code == 200:
    result = r.json()
    check("Has ai_feedback_draft",   bool(result.get("ai_feedback_draft")),  str(result.get("ai_feedback_draft", ""))[:80])
    check("Has recommended_score",   "recommended_score" in result,          str(result))
    check("Score is 0-100",          0 <= int(result.get("recommended_score", -1)) <= 100)
    check("Has cheating_flag field", "cheating_flag" in result)
    check("Has ai_provider field",   bool(result.get("ai_provider")),        str(result.get("ai_provider")))
    submission_id = result.get("id", "")
    print(f"  score={result.get('recommended_score')}  provider={result.get('ai_provider')}  cheating={result.get('cheating_flag')}")
    print(f"  feedback preview: {str(result.get('ai_feedback_draft',''))[:120]}")
else:
    submission_id = ""

# ---------------------------------------------------------------------------
# 4. Approve a review
# ---------------------------------------------------------------------------
print("\n=== 4. Approve review ===")
r = requests.post(
    f"{BASE}/api/reviews",
    data={
        "lesson_key":   LESSON_KEY,
        "student_id":   "student-e2e-001",
        "student_name": "תלמיד בדיקה",
        "file_name":    "student_solution.pdf",
        "score":        "85",
        "cheating_risk":"low",
        "feedback":     "עבודה טובה! שפר את הניקוד.",
    },
    timeout=10,
)
check("POST /api/reviews returns 200", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}")
check("ok == True", r.json().get("ok") is True, str(r.json()))

# ---------------------------------------------------------------------------
# 5. Fetch reviews for lesson
# ---------------------------------------------------------------------------
print("\n=== 5. Fetch reviews for lesson ===")
r = requests.get(f"{BASE}/api/reviews/lesson/{LESSON_KEY}", timeout=10)
check("GET /api/reviews/lesson returns 200", r.status_code == 200, f"HTTP {r.status_code}")
reviews = r.json()
check("At least 1 review returned", len(reviews) >= 1, f"got {len(reviews)}")
if reviews:
    rev = reviews[0]
    check("Review has score field",    "score"    in rev)
    check("Review has feedback field", "feedback" in rev)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
if errors:
    print(f"\033[91m{len(errors)} test(s) FAILED:\033[0m {', '.join(errors)}")
    sys.exit(1)
else:
    print("\033[92mAll tests passed!\033[0m")
