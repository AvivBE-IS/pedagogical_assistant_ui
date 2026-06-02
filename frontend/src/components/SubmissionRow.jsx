import { useLang } from "../contexts/LanguageContext";

function SubmissionRow({
  student,
  onUpload,
  existingReview,
  isGrading,
  onViewReview,
}) {
  const { t } = useLang();
  const inputId = `upload-${student.id}`;
  const isHighRisk = existingReview?.cheatingRisk === "high";

  return (
    <li
      className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 ${
        isHighRisk
          ? "border-red-300 bg-red-100/70 dark:border-red-700/60 dark:bg-red-900/20"
          : "border-blue-100 bg-blue-50/70 dark:border-slate-700 dark:bg-slate-900/60"
      }`}
    >
      <div>
        <p className="font-medium text-blue-950 dark:text-blue-100">
          {student.name}
        </p>
        {existingReview && (
          <div className="flex items-center gap-2">
            <p
              className={`text-xs ${
                isHighRisk
                  ? "text-red-700 dark:text-red-400"
                  : "text-emerald-700 dark:text-emerald-400"
              }`}
            >
              {isHighRisk ? "⚠ " : ""}
              {t.approvedReviewSaved} ({existingReview.fileName})
            </p>
            {onViewReview && (
              <button
                type="button"
                onClick={() => onViewReview(student)}
                className="text-xs font-semibold text-blue-700 underline hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-200"
              >
                {t.viewReview}
              </button>
            )}
          </div>
        )}
      </div>
      <div>
        {isGrading ? (
          <div className="flex items-center gap-2 rounded-lg bg-blue-900 px-3 py-2 text-xs font-semibold text-white opacity-80">
            <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
            {t.grading}
          </div>
        ) : (
          <>
            <label
              htmlFor={inputId}
              className="cursor-pointer rounded-lg bg-blue-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-blue-800"
            >
              {t.uploadAssignment}
            </label>
            <input
              id={inputId}
              type="file"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  onUpload(student, file);
                }
                event.target.value = "";
              }}
            />
          </>
        )}
      </div>
    </li>
  );
}

export default SubmissionRow;
