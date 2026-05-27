import { useMemo, useState } from 'react'
import CourseNavigator from './components/CourseNavigator'
import Dashboard from './components/Dashboard'
import DarkModeToggle from './components/DarkModeToggle'
import LessonView from './components/LessonView'
import ReviewModal from './components/ReviewModal'
import { courses, getMockAiReview, groups, students } from './data/mockData'

const defaultLesson = courses[0].semesters[0].lessons[0]

function App() {
  const [selectedGroupId, setSelectedGroupId] = useState(null)
  const [selectedLessonId, setSelectedLessonId] = useState(defaultLesson.id)
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [activeReview, setActiveReview] = useState(null)
  const [approvedReviews, setApprovedReviews] = useState({})

  const selectedGroup = groups.find((group) => group.id === selectedGroupId)

  const selectedLessonLabel = useMemo(() => {
    for (const course of courses) {
      for (const semester of course.semesters) {
        const lesson = semester.lessons.find((item) => item.id === selectedLessonId)
        if (lesson) {
          return `${course.name} · ${semester.name} · ${lesson.title}`
        }
      }
    }
    return 'No lesson selected'
  }, [selectedLessonId])

  const reviewStorageKey = (lessonId, studentId) => `${lessonId}-${studentId}`

  const reviewsByStudent = useMemo(
    () =>
      students.reduce((accumulator, student) => {
        const savedReview = approvedReviews[reviewStorageKey(selectedLessonId, student.id)]
        if (savedReview) {
          accumulator[student.id] = savedReview
        }
        return accumulator
      }, {}),
    [approvedReviews, selectedLessonId],
  )

  const handleUpload = (student, file) => {
    const aiReview = getMockAiReview(student.id, selectedLessonId, file.name)
    setActiveReview({
      ...aiReview,
      lessonId: selectedLessonId,
      studentId: student.id,
      studentName: student.name,
    })
  }

  const handleApproveFeedback = (feedback) => {
    if (!activeReview) {
      return
    }

    const key = reviewStorageKey(activeReview.lessonId, activeReview.studentId)
    setApprovedReviews((current) => ({
      ...current,
      [key]: {
        fileName: activeReview.fileName,
        score: activeReview.score,
        cheatingRisk: activeReview.cheatingRisk,
        feedback,
      },
    }))
    setActiveReview(null)
  }

  return (
    <div className={isDarkMode ? 'dark' : ''}>
      <main className="min-h-screen bg-blue-50 text-slate-900 transition dark:bg-slate-900 dark:text-slate-100">
        <header className="flex items-center justify-between border-b border-blue-200 bg-blue-900 px-6 py-4 text-white dark:border-slate-700 dark:bg-slate-950">
          <div>
            <p className="text-lg font-semibold">Instructor Console</p>
            <p className="text-xs text-blue-100">Pedagogical Assistant MVP</p>
          </div>
          <DarkModeToggle enabled={isDarkMode} onToggle={() => setIsDarkMode((value) => !value)} />
        </header>

        {!selectedGroup ? (
          <Dashboard groups={groups} onSelectGroup={setSelectedGroupId} />
        ) : (
          <div className="mx-auto flex max-w-7xl flex-col gap-4 p-4 lg:flex-row">
            <CourseNavigator
              courses={courses}
              selectedLessonId={selectedLessonId}
              onSelectLesson={(_, __, lessonId) => setSelectedLessonId(lessonId)}
            />
            <LessonView
              groupName={selectedGroup.name}
              selectedLesson={selectedLessonLabel}
              students={students}
              onUpload={handleUpload}
              reviewsByStudent={reviewsByStudent}
            />
          </div>
        )}

        <ReviewModal
          key={activeReview ? activeReview.lessonId + '-' + activeReview.studentId + '-' + activeReview.fileName : 'review-modal'}
          reviewData={activeReview}
          onClose={() => setActiveReview(null)}
          onApprove={handleApproveFeedback}
        />
      </main>
    </div>
  )
}

export default App
