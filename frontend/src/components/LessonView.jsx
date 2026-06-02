import { useLang } from "../contexts/LanguageContext";
import SubmissionRow from "./SubmissionRow";

const COURSE_MATERIAL_TYPES = [
  "courseBook",
  "syllabus",
  "overview",
  "reference",
];
const LESSON_MATERIAL_TYPES = [
  "lecture",
  "exercise",
  "solution",
  "rubric",
  "extra",
];

function normalizeFileData(v) {
  if (!v) return null;
  if (typeof v === "string")
    return { name: v, size: null, mimeType: null, dataUrl: null };
  return v;
}

function fileIcon(mimeType) {
  if (!mimeType) return "📄";
  if (mimeType === "application/pdf") return "📕";
  if (mimeType.startsWith("image/")) return "🖼️";
  if (mimeType.startsWith("video/")) return "🎬";
  if (mimeType.startsWith("audio/")) return "🔊";
  if (mimeType.startsWith("text/")) return "📝";
  if (
    mimeType ===
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    mimeType === "application/msword"
  )
    return "📝";
  return "📄";
}

function formatSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function MaterialSlot({ type, rawValue, onUpload, t }) {
  const inputId = `material-${type}`;
  const labelKey = `material${type.charAt(0).toUpperCase() + type.slice(1)}`;
  const fileData = normalizeFileData(rawValue);

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-100 bg-white px-3 py-2 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-center gap-2 min-w-[110px]">
        <span className="text-base leading-none">
          {fileIcon(fileData?.mimeType)}
        </span>
        <span className="text-sm font-medium text-blue-950 dark:text-blue-100">
          {t[labelKey]}
        </span>
      </div>
      <div className="flex items-center gap-2">
        {fileData ? (
          <>
            <div className="flex flex-col items-end">
              <span
                className="max-w-[160px] truncate text-xs font-semibold text-emerald-700 dark:text-emerald-400"
                title={fileData.name}
              >
                ✓ {fileData.name}
              </span>
              {fileData.size && (
                <span className="text-xs text-slate-400">
                  {formatSize(fileData.size)}
                </span>
              )}
            </div>
            {fileData.dataUrl && (
              <a
                href={fileData.dataUrl}
                download={fileData.name}
                className="rounded-lg bg-emerald-700 px-2 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-600"
                title={t.downloadFile}
              >
                ↓
              </a>
            )}
          </>
        ) : (
          <span className="text-xs text-slate-400 dark:text-slate-500">
            {t.noFileUploaded}
          </span>
        )}
        {onUpload && (
          <>
            <label
              htmlFor={inputId}
              className="cursor-pointer rounded-lg bg-blue-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-blue-800"
            >
              {fileData ? t.replaceFile : t.uploadFile}
            </label>
            <input
              id={inputId}
              type="file"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onUpload(type, file);
                e.target.value = "";
              }}
            />
          </>
        )}
      </div>
    </div>
  );
}

function MaterialsSection({
  title,
  subtitle,
  types,
  materials,
  onUpload,
  t,
  borderColor,
}) {
  return (
    <div
      className={`rounded-xl border ${borderColor} bg-white/60 p-4 dark:bg-slate-900/40`}
    >
      <p className="mb-1 text-sm font-semibold text-blue-900 dark:text-blue-200">
        {title}
      </p>
      <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
        {subtitle}
      </p>
      <div className="space-y-2">
        {types.map((type) => (
          <MaterialSlot
            key={type}
            type={type}
            rawValue={materials[type]}
            onUpload={onUpload}
            t={t}
          />
        ))}
      </div>
    </div>
  );
}

function LessonView({
  groupName,
  selectedLesson,
  selectedLessonId,
  selectedCourseId,
  students,
  onUpload,
  reviewsByStudent,
  onManageStudents,
  isManager,
  selectedYear,
  onYearChange,
  currentMaterials,
  onUploadMaterial,
  currentCourseMaterials,
  onUploadCourseMaterial,
  submissionsLoading,
  submissionsError,
  gradingStudents,
  onViewReview,
}) {
  const { t } = useLang();

  const currentYear = new Date().getFullYear();
  const yearOptions = [currentYear - 1, currentYear, currentYear + 1];

  const showMaterials = isManager;

  return (
    <section className="flex-1 rounded-2xl border border-blue-200/70 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-xl font-bold text-blue-950 dark:text-blue-100">
            {t.lessonViewTitle}
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            {groupName} · {selectedLesson}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isManager && (
            <select
              value={selectedYear}
              onChange={(e) => onYearChange(Number(e.target.value))}
              className="rounded-lg border border-blue-300/70 bg-blue-50 px-2 py-1.5 text-xs font-semibold text-blue-900 transition hover:bg-blue-100 dark:border-slate-600 dark:bg-slate-900 dark:text-blue-100"
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>
                  {t.academicYear} {y}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={onManageStudents}
            className="shrink-0 rounded-lg border border-blue-300/70 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-900 transition hover:bg-blue-100 dark:border-slate-600 dark:bg-slate-900 dark:text-blue-100 dark:hover:bg-slate-700"
          >
            {t.manageStudents}
          </button>
        </div>
      </div>

      {showMaterials && (
        <div className="mt-4 space-y-3">
          <MaterialsSection
            title={t.courseMaterialsTitle}
            subtitle={`${t.courseMaterialsSubtitle} · ${t.academicYear} ${selectedYear}`}
            types={COURSE_MATERIAL_TYPES}
            materials={currentCourseMaterials}
            onUpload={onUploadCourseMaterial}
            t={t}
            borderColor="border-indigo-200 dark:border-slate-600"
          />
          <MaterialsSection
            title={t.lessonMaterialsTitle}
            subtitle={`${t.lessonMaterialsSubtitle} · ${selectedLesson} · ${t.academicYear} ${selectedYear}`}
            types={LESSON_MATERIAL_TYPES}
            materials={currentMaterials}
            onUpload={onUploadMaterial}
            t={t}
            borderColor="border-blue-200 dark:border-slate-600"
          />
        </div>
      )}

      <ul className="mt-4 space-y-3">
        {submissionsLoading && (
          <li className="flex items-center gap-2 rounded-lg border border-blue-100 bg-blue-50/50 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
            Loading submissions…
          </li>
        )}
        {submissionsError && !submissionsLoading && (
          <li className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-700/40 dark:bg-amber-900/20 dark:text-amber-300">
            ⚠ Could not reach backend: {submissionsError}
          </li>
        )}
        {students.map((student) => (
          <SubmissionRow
            key={student.id}
            student={student}
            onUpload={onUpload}
            existingReview={reviewsByStudent[student.id]}
            isGrading={gradingStudents?.[student.id] ?? false}
            onViewReview={onViewReview}
          />
        ))}
      </ul>
    </section>
  );
}

export default LessonView;
