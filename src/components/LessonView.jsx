import SubmissionRow from './SubmissionRow'

function LessonView({ groupName, selectedLesson, students, onUpload, reviewsByStudent }) {
  return (
    <section className="flex-1 rounded-2xl border border-blue-200/70 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <h2 className="text-xl font-bold text-blue-950 dark:text-blue-100">Lesson View</h2>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
        {groupName} · {selectedLesson}
      </p>
      <ul className="mt-4 space-y-3">
        {students.map((student) => (
          <SubmissionRow
            key={student.id}
            student={student}
            onUpload={onUpload}
            existingReview={reviewsByStudent[student.id]}
          />
        ))}
      </ul>
    </section>
  )
}

export default LessonView
