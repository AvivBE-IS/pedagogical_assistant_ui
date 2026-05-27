function CourseNavigator({ courses, selectedLessonId, onSelectLesson }) {
  return (
    <aside className="w-full rounded-2xl border border-blue-200/70 bg-white p-4 dark:border-slate-700 dark:bg-slate-800 lg:w-96">
      <h2 className="mb-4 text-lg font-semibold text-blue-950 dark:text-blue-100">Course Navigator</h2>
      <div className="space-y-4">
        {courses.map((course) => (
          <section key={course.id}>
            <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-200">{course.name}</h3>
            <div className="mt-2 space-y-2">
              {course.semesters.map((semester) => (
                <div key={semester.id} className="rounded-lg border border-blue-100 p-2 dark:border-slate-700">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-300">
                    {semester.name}
                  </p>
                  <div className="grid grid-cols-4 gap-1">
                    {semester.lessons.map((lesson) => (
                      <button
                        key={lesson.id}
                        type="button"
                        onClick={() => onSelectLesson(course.id, semester.id, lesson.id)}
                        className={`rounded px-1 py-1 text-xs transition ${
                          lesson.id === selectedLessonId
                            ? 'bg-blue-800 text-white'
                            : 'bg-blue-50 text-blue-900 hover:bg-blue-100 dark:bg-slate-900 dark:text-blue-100 dark:hover:bg-slate-700'
                        }`}
                      >
                        L{lesson.title.split(' ')[1]}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </aside>
  )
}

export default CourseNavigator
