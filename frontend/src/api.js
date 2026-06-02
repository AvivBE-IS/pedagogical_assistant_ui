const BASE_URL = "http://localhost:8000";

/**
 * One-time course initialisation — uploads the course book + syllabus to the
 * backend, triggers the course_setup_pipeline, and stores LangSmith trace id.
 */
export async function setupCourse({
  courseId,
  courseName,
  nLessons,
  courseBookFile,
  syllabusFile = null,
}) {
  const form = new FormData();
  form.append("course_id", courseId);
  form.append("course_name", courseName);
  form.append("n_lessons", String(nLessons));
  form.append("course_book_file", courseBookFile);
  if (syllabusFile) form.append("syllabus_file", syllabusFile);

  const res = await fetch(`${BASE_URL}/api/courses`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail).catch(() => null);
    throw new Error(detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Fetch all instructor-approved reviews for a given frontend lesson key.
 * Returns an array of review objects from MongoDB.
 * Throws on network or HTTP error.
 */
export async function fetchReviewsForLesson(lessonKey, signal) {
  const res = await fetch(
    `${BASE_URL}/api/reviews/lesson/${encodeURIComponent(lessonKey)}`,
    { signal },
  );
  if (!res.ok) throw new Error(`GET /api/reviews/lesson — HTTP ${res.status}`);
  return res.json();
}

/**
 * Persist an instructor-approved review to MongoDB.
 * Uses upsert so re-approvals overwrite the previous entry.
 */
export async function saveReview({
  lessonKey,
  studentId,
  studentName,
  fileName,
  score,
  cheatingRisk,
  feedback,
}) {
  const form = new FormData();
  form.append("lesson_key", lessonKey);
  form.append("student_id", studentId);
  form.append("student_name", studentName);
  form.append("file_name", fileName);
  form.append("score", String(score));
  form.append("cheating_risk", cheatingRisk);
  form.append("feedback", feedback);

  const res = await fetch(`${BASE_URL}/api/reviews`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`POST /api/reviews — HTTP ${res.status}`);
  return res.json();
}

/**
 * Upload a student submission PDF to the backend for AI grading.
 * Returns the full submission document including ai_feedback_draft,
 * recommended_score, and cheating_flag (boolean).
 */
export async function submitStudentFile({
  lessonKey,
  studentId,
  studentName,
  file,
}) {
  const form = new FormData();
  form.append("lesson_key", lessonKey);
  form.append("student_id", studentId);
  form.append("student_name", studentName);
  form.append("submission_file", file);

  const res = await fetch(`${BASE_URL}/api/submissions`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const detail = await res
      .json()
      .then((d) => d.detail)
      .catch(() => null);
    throw new Error(detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Push lesson context files (rebuilt from IndexedDB dataUrls) to MongoDB.
 * Uses upsert — safe to call every time materials are updated.
 * rubricFile: grading rubric file — its text is extracted server-side.
 * syllabusFile: course syllabus — the backend auto-infers allowed topics from it.
 */
export async function syncLessonContext({
  lessonKey,
  courseId,
  lessonNumber,
  lectureFile,
  assignmentFile,
  solutionFile,
  rubricFile = null,
  syllabusFile = null,
}) {
  const form = new FormData();
  form.append("course_id", courseId);
  form.append("lesson_key", lessonKey);
  form.append("lesson_number", String(lessonNumber));
  form.append("lecture_file", lectureFile);
  form.append("assignment_file", assignmentFile);
  form.append("solution_file", solutionFile);
  if (rubricFile) form.append("rubric_file", rubricFile);
  if (syllabusFile) form.append("syllabus_file", syllabusFile);

  const res = await fetch(`${BASE_URL}/api/lessons`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((d) => d.detail)
      .catch(() => null);
    throw new Error(detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}
