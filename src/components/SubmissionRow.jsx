function SubmissionRow({ student, onUpload, existingReview }) {
  const inputId = `upload-${student.id}`

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-blue-100 bg-blue-50/70 p-3 dark:border-slate-700 dark:bg-slate-900/60">
      <div>
        <p className="font-medium text-blue-950 dark:text-blue-100">{student.name}</p>
        {existingReview && (
          <p className="text-xs text-emerald-700 dark:text-emerald-400">
            Approved review saved ({existingReview.fileName})
          </p>
        )}
      </div>
      <div>
        <label
          htmlFor={inputId}
          className="cursor-pointer rounded-lg bg-blue-900 px-3 py-2 text-xs font-semibold text-white transition hover:bg-blue-800"
        >
          Upload Assignment
        </label>
        <input
          id={inputId}
          type="file"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) {
              onUpload(student, file)
            }
            event.target.value = ''
          }}
        />
      </div>
    </li>
  )
}

export default SubmissionRow
