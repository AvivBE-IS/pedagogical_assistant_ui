import { useRef, useState } from "react";
import { BookOpen, CheckCircle, AlertCircle, Loader2, Upload } from "lucide-react";
import { useLang } from "../contexts/LanguageContext";
import { setupCourse } from "../api";

// course-id → name map (mirrors mockData + courseLabels)
const COURSE_OPTIONS = [
  { id: "course-1", en: "Introduction to Programming", he: "מבוא לתכנות" },
  { id: "course-2", en: "Networks",                   he: "רשתות" },
  { id: "course-3", en: "Principles",                 he: "עקרונות" },
  { id: "course-4", en: "Computer Architecture",      he: "ארכיטקטורת המחשב" },
];

const DEFAULT_N_LESSONS = 26; // 2 semesters × 13 lessons

function FilePicker({ id, label, required, file, onPick, t }) {
  const ref = useRef(null);
  return (
    <li className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/50">
      <div className="flex min-w-0 flex-1 items-center gap-2.5">
        <BookOpen
          size={16}
          className={`shrink-0 ${file ? "text-blue-600 dark:text-blue-400" : "text-slate-400"}`}
        />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            {label}
            {required && <span className="ms-1 text-red-500">*</span>}
          </p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">
            {file ? file.name : t.noFileUploaded}
          </p>
        </div>
      </div>
      <input
        ref={ref}
        id={id}
        type="file"
        accept=".pdf,.docx,.doc,.txt"
        className="sr-only"
        onChange={(e) => onPick(e.target.files[0] ?? null)}
      />
      <button
        type="button"
        onClick={() => ref.current?.click()}
        className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
      >
        <Upload size={13} />
        {file ? t.replaceFile : t.uploadFile}
      </button>
    </li>
  );
}

/**
 * CourseSetupPanel — manager-only panel.
 * Sends course book + syllabus to POST /api/courses which triggers
 * the course_setup_pipeline and creates a LangSmith trace.
 */
export default function CourseSetupPanel() {
  const { t, lang } = useLang();

  const [courseId, setCourseId]     = useState("course-1");
  const [nLessons, setNLessons]     = useState(DEFAULT_N_LESSONS);
  const [bookFile, setBookFile]     = useState(null);
  const [syllabusFile, setSylFile]  = useState(null);
  const [status, setStatus]         = useState(null);   // null | 'saving' | 'success' | 'error'
  const [error, setError]           = useState(null);
  const [traceId, setTraceId]       = useState(null);

  const selectedCourse = COURSE_OPTIONS.find((c) => c.id === courseId);
  const courseName = selectedCourse ? selectedCourse[lang] ?? selectedCourse.he : "";

  const handleSubmit = async () => {
    if (!bookFile) return;
    setStatus("saving");
    setError(null);
    setTraceId(null);
    try {
      const result = await setupCourse({
        courseId,
        courseName,
        nLessons,
        courseBookFile: bookFile,
        syllabusFile: syllabusFile ?? undefined,
      });
      setTraceId(result.langsmith_trace_id ?? null);
      setStatus("success");
    } catch (err) {
      setError(err.message ?? t.courseSetupError);
      setStatus("error");
    }
  };

  return (
    <section className="rounded-2xl border border-blue-200/70 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <h2 className="mb-1 text-base font-bold text-blue-950 dark:text-blue-100">
        {t.courseSetupTitle}
      </h2>
      <p className="mb-4 text-xs text-slate-500 dark:text-slate-400">
        {t.courseSetupSubtitle}
      </p>

      {/* Course selector */}
      <div className="mb-3 flex flex-col gap-1">
        <label className="text-xs font-semibold text-slate-600 dark:text-slate-300">
          {t.courseSetupCourseLabel}
        </label>
        <select
          value={courseId}
          onChange={(e) => { setCourseId(e.target.value); setStatus(null); }}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
        >
          {COURSE_OPTIONS.map((c) => (
            <option key={c.id} value={c.id}>
              {c[lang] ?? c.he}
            </option>
          ))}
        </select>
      </div>

      {/* n_lessons */}
      <div className="mb-4 flex flex-col gap-1">
        <label className="text-xs font-semibold text-slate-600 dark:text-slate-300">
          {t.courseSetupNLessons}
        </label>
        <input
          type="number"
          min={1}
          max={200}
          value={nLessons}
          onChange={(e) => setNLessons(Number(e.target.value))}
          className="w-24 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
        />
      </div>

      {/* File pickers */}
      <ul className="mb-4 space-y-2">
        <FilePicker
          id="course-book-file"
          label={t.courseSetupBookLabel}
          required
          file={bookFile}
          onPick={(f) => { setBookFile(f); setStatus(null); }}
          t={t}
        />
        <FilePicker
          id="syllabus-file"
          label={t.courseSetupSyllabusLabel}
          required={false}
          file={syllabusFile}
          onPick={(f) => { setSylFile(f); setStatus(null); }}
          t={t}
        />
      </ul>

      {/* Submit */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!bookFile || status === "saving"}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {status === "saving" ? (
          <Loader2 size={15} className="animate-spin" />
        ) : (
          <Upload size={15} />
        )}
        {status === "saving" ? t.courseSetupSaving : t.courseSetupBtn}
      </button>

      {/* Feedback */}
      {status === "success" && (
        <div className="mt-3 flex flex-col gap-1 rounded-xl bg-emerald-50 px-4 py-3 dark:bg-emerald-900/20">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-700 dark:text-emerald-300">
            <CheckCircle size={15} />
            {t.courseSetupSuccess}
          </div>
          {traceId && (
            <a
              href={`https://smith.langchain.com/o/public/projects/p/${traceId}`}
              target="_blank"
              rel="noreferrer"
              className="break-all text-xs text-blue-600 underline dark:text-blue-400"
            >
              LangSmith trace: {traceId}
            </a>
          )}
        </div>
      )}
      {status === "error" && (
        <div className="mt-3 flex items-start gap-2 rounded-xl bg-red-50 px-4 py-3 dark:bg-red-900/20">
          <AlertCircle size={15} className="mt-0.5 shrink-0 text-red-600" />
          <p className="text-sm text-red-700 dark:text-red-300">
            {error ?? t.courseSetupError}
          </p>
        </div>
      )}
    </section>
  );
}
