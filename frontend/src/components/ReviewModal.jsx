import { useState } from "react";
import { useLang } from "../contexts/LanguageContext";

function ReviewModal({ reviewData, onClose, onApprove }) {
  const { t } = useLang();
  const [editedFeedback, setEditedFeedback] = useState(
    reviewData?.feedback || "",
  );

  if (!reviewData) {
    return null;
  }

  const cheatingClasses = {
    high: "bg-red-100 text-red-800 border-red-300",
    medium: "bg-amber-100 text-amber-800 border-amber-300",
    low: "bg-emerald-100 text-emerald-800 border-emerald-300",
  };

  const cheatingLabels = {
    high: t.cheatingHigh,
    medium: t.cheatingMedium,
    low: t.cheatingLow,
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-blue-950/70 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-5 shadow-xl dark:bg-slate-800">
        <h3 className="text-lg font-semibold text-blue-950 dark:text-blue-100">
          {t.mockAiReviewTitle}
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-300">
          {reviewData.studentName} · {reviewData.fileName}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-900">
            {t.recommendedScore}: {reviewData.score}/100
          </span>
          <span
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${
              cheatingClasses[reviewData.cheatingRisk]
            }`}
          >
            {t.cheatingRisk}: {cheatingLabels[reviewData.cheatingRisk]}
          </span>
        </div>

        <textarea
          className="mt-4 h-48 w-full rounded-lg border border-blue-200 p-3 text-sm text-slate-700 focus:border-blue-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          value={editedFeedback}
          onChange={(event) => setEditedFeedback(event.target.value)}
        />

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 dark:border-slate-500 dark:text-slate-200"
            onClick={onClose}
          >
            {t.cancel}
          </button>
          <button
            type="button"
            className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800"
            onClick={() => onApprove(editedFeedback)}
          >
            {t.approveFeedback}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ReviewModal;
