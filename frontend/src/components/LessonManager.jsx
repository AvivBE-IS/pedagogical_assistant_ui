import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle,
  CloudUpload,
  FileText,
  Loader2,
  Trash2,
  Upload,
} from "lucide-react";
import { useLang } from "../contexts/LanguageContext";
import { dbSave, STORE_LESSON_MATERIALS } from "../db";
import { syncLessonContext } from "../api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * The three required PDF slots for every lesson.
 * `key`      — matches the property name stored in IndexedDB / currentMaterials.
 * `labelKey` — translation key for the slot's display name.
 */
const FILE_SLOTS = [
  { key: "lecture",  labelKey: "materialLecture" },
  { key: "exercise", labelKey: "materialExercise" },
  { key: "solution", labelKey: "materialSolution" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Reconstruct a File object from a base64 dataUrl string saved in IndexedDB.
 * syncLessonContext expects real multipart File objects, not raw base64.
 */
function dataUrlToFile(dataUrl, fileName) {
  const [header, base64Data] = dataUrl.split(",");
  const mimeType = header.match(/:(.*?);/)[1];
  const bytes = atob(base64Data);
  const buffer = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) buffer[i] = bytes.charCodeAt(i);
  return new File([buffer], fileName, { type: mimeType });
}

// ---------------------------------------------------------------------------
// Sub-component: individual file slot row
// ---------------------------------------------------------------------------

/**
 * FileSlotRow renders a single file slot with:
 *   - file name (or "no file" placeholder)
 *   - uploaded / missing status badge
 *   - upload / replace button
 *   - delete button (only when a file is present)
 */
function FileSlotRow({ slotKey, labelKey, fileData, inputId, t, onFileChange, onDelete }) {
  return (
    <li className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900/50">
      {/* Icon + label + filename */}
      <div className="flex min-w-0 flex-1 items-center gap-2.5">
        <FileText
          size={16}
          className={`shrink-0 ${
            fileData
              ? "text-blue-600 dark:text-blue-400"
              : "text-slate-400 dark:text-slate-500"
          }`}
        />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            {t[labelKey]}
          </p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">
            {fileData ? fileData.name : t.noFileUploaded}
          </p>
        </div>
      </div>

      {/* Status badge */}
      <span
        className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
          fileData
            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
            : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
        }`}
      >
        {fileData ? <CheckCircle size={12} /> : <AlertCircle size={12} />}
        {fileData ? t.fileUploaded : t.noFileUploaded}
      </span>

      {/* Upload / Replace + Delete */}
      <div className="flex shrink-0 items-center gap-1.5">
        <label
          htmlFor={inputId}
          className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-blue-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-blue-800"
        >
          <Upload size={12} />
          {fileData ? t.replaceFile : t.uploadFile}
        </label>
        <input
          id={inputId}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={onFileChange}
        />

        {/* Delete button — visible only when a file is already uploaded */}
        {fileData && (
          <button
            type="button"
            aria-label={`Delete ${t[labelKey]}`}
            onClick={onDelete}
            className="rounded-lg border border-red-200 p-1.5 text-red-500 transition hover:bg-red-50 dark:border-red-800/50 dark:hover:bg-red-950/40"
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * LessonManager — manager-only panel for uploading, storing, and syncing
 * lesson context PDFs (Lecture, Exercise, Solution) to the backend.
 *
 * Props:
 *   selectedLessonId   {string}    Frontend lesson key, e.g. 'c1-s1-l3'
 *   selectedCourseId   {string}    Parent course ID, e.g. 'course-1'
 *   selectedYear       {number}    Academic year — part of the IndexedDB composite key
 *   currentMaterials   {object}    { lecture?, exercise?, solution? } driven by parent state
 *   onUploadMaterial   {function}  (type: string, file: File) → void
 *                                  Parent handles FileReader → IndexedDB → auto-sync
 *   onDeleteMaterial   {function}  [optional] (type: string) → void
 *                                  Parent removes slot from its state + IndexedDB.
 *                                  When omitted the component handles deletion locally.
 */
function LessonManager({
  selectedLessonId,
  selectedCourseId,
  selectedYear,
  currentMaterials = {},
  onUploadMaterial,
  onDeleteMaterial,
}) {
  const { t } = useLang();

  // Local deletions: used as a client-side overlay when onDeleteMaterial is not provided.
  // Keys are slot names ('lecture' | 'exercise' | 'solution'), value is true when deleted.
  const [localDeleted, setLocalDeleted] = useState({});

  const [rubric, setRubric] = useState("");
  const [topics, setTopics] = useState("");

  // Sync state: null | 'syncing' | 'success' | 'error'
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncError, setSyncError] = useState(null);

  // Reset transient state whenever the active lesson changes
  useEffect(() => {
    setLocalDeleted({});
    setSyncStatus(null);
    setSyncError(null);
  }, [selectedLessonId, selectedYear]);

  // Effective materials: parent state minus any local deletions
  const materials = { ...currentMaterials };
  Object.keys(localDeleted).forEach((k) => {
    if (localDeleted[k]) delete materials[k];
  });

  const allFilesPresent =
    Boolean(materials.lecture) &&
    Boolean(materials.exercise) &&
    Boolean(materials.solution);

  // The IndexedDB key used by this lesson slot
  const dbKey = `${selectedYear}-${selectedLessonId}`;

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  /** Handle a new file selection for the given slot. */
  const handleFileChange = (slotKey, e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Clear any local deletion override so the newly uploaded file is visible
    setLocalDeleted((prev) => ({ ...prev, [slotKey]: false }));

    onUploadMaterial(slotKey, file);

    // Reset the input so the same filename can be re-selected after a delete
    e.target.value = "";

    // A file change invalidates a previous successful sync
    setSyncStatus(null);
  };

  /** Remove a file from its slot. Updates IndexedDB and notifies parent or local state. */
  const handleDelete = async (slotKey) => {
    // Persist the removal to IndexedDB immediately
    const updated = { ...currentMaterials };
    delete updated[slotKey];
    await dbSave(STORE_LESSON_MATERIALS, dbKey, updated).catch(() => {});

    if (onDeleteMaterial) {
      // Delegate state update to parent
      onDeleteMaterial(slotKey);
    } else {
      // Parent does not manage deletions — apply a local overlay instead
      setLocalDeleted((prev) => ({ ...prev, [slotKey]: true }));
    }

    setSyncStatus(null);
  };

  /** Push all three files to the backend together with rubric and topics metadata. */
  const handleSync = async () => {
    if (!allFilesPresent) return;

    setSyncStatus("syncing");
    setSyncError(null);

    try {
      // Derive a numeric lesson number from the lesson key (e.g. 'c1-s1-l3' → 3)
      const lessonNumber = parseInt(selectedLessonId.split("-l")[1] ?? "1", 10);

      await syncLessonContext({
        lessonKey: selectedLessonId,
        courseId: selectedCourseId,
        lessonNumber,
        lectureFile:    dataUrlToFile(materials.lecture.dataUrl,  materials.lecture.name),
        assignmentFile: dataUrlToFile(materials.exercise.dataUrl, materials.exercise.name),
        solutionFile:   dataUrlToFile(materials.solution.dataUrl, materials.solution.name),
        gradingRubric: rubric,
        allowedTopics: topics,
      });

      setSyncStatus("success");
    } catch (err) {
      setSyncStatus("error");
      setSyncError(err.message ?? "Unknown error");
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <section className="rounded-2xl border border-blue-200/70 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
      {/* Header */}
      <div className="mb-5">
        <h2 className="text-base font-bold text-blue-950 dark:text-blue-100">
          {t.lessonMaterialsTitle}
        </h2>
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
          {t.lessonMaterialsSubtitle}
        </p>
      </div>

      {/* File slots */}
      <ul className="space-y-3">
        {FILE_SLOTS.map(({ key, labelKey }) => (
          <FileSlotRow
            key={key}
            slotKey={key}
            labelKey={labelKey}
            fileData={materials[key]}
            inputId={`lm-file-${key}-${selectedLessonId}`}
            t={t}
            onFileChange={(e) => handleFileChange(key, e)}
            onDelete={() => handleDelete(key)}
          />
        ))}
      </ul>

      {/* Rubric + Topics — shown once at least one file has been uploaded */}
      {Object.keys(materials).length > 0 && (
        <div className="mt-5 space-y-3">
          {/* Grading rubric */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
              {t.gradingRubricLabel}
            </label>
            <textarea
              rows={2}
              value={rubric}
              onChange={(e) => setRubric(e.target.value)}
              placeholder={t.gradingRubricPlaceholder}
              className="resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500"
            />
          </div>

          {/* Allowed topics */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
              {t.allowedTopicsLabel}
            </label>
            <input
              type="text"
              value={topics}
              onChange={(e) => setTopics(e.target.value)}
              placeholder={t.allowedTopicsPlaceholder}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500"
            />
          </div>
        </div>
      )}

      {/* Sync-to-backend section */}
      <div className="mt-5">
        {/* Inline warning when not all 3 files are ready */}
        {!allFilesPresent && (
          <p className="mb-2 flex items-start gap-1.5 text-xs text-amber-600 dark:text-amber-400">
            <AlertCircle size={13} className="mt-0.5 shrink-0" />
            {t.saveLessonContextMissingFiles}
          </p>
        )}

        {/* Primary sync button */}
        <button
          type="button"
          onClick={handleSync}
          disabled={!allFilesPresent || syncStatus === "syncing"}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-900 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {syncStatus === "syncing" ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <CloudUpload size={16} />
          )}
          {syncStatus === "syncing" ? t.saveLessonContextSaving : t.saveLessonContext}
        </button>

        {/* Success feedback */}
        {syncStatus === "success" && (
          <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <CheckCircle size={13} className="shrink-0" />
            {t.saveLessonContextSuccess}
          </p>
        )}

        {/* Error feedback */}
        {syncStatus === "error" && (
          <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-red-600 dark:text-red-400">
            <AlertCircle size={13} className="shrink-0" />
            {syncError ?? "Sync failed. Check that the backend is running."}
          </p>
        )}
      </div>
    </section>
  );
}

export default LessonManager;
