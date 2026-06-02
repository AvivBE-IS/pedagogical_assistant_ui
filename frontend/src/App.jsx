import { useEffect, useMemo, useState } from "react";
import CourseNavigator from "./components/CourseNavigator";
import CourseSetupPanel from "./components/CourseSetupPanel";
import DarkModeToggle from "./components/DarkModeToggle";
import LessonView from "./components/LessonView";
import LoginScreen from "./components/LoginScreen";
import ReviewModal from "./components/ReviewModal";
import StudentManager from "./components/StudentManager";
import { useAuth, ROLE_COURSE, ROLES } from "./contexts/AuthContext";
import { useLang } from "./contexts/LanguageContext";

/** Convert a base64 dataUrl back to a File object for multipart upload. */
function dataUrlToFile(dataUrl, fileName) {
  const [header, base64Data] = dataUrl.split(",");
  const mimeType = header.match(/:(.*?);/)[1];
  const bytes = atob(base64Data);
  const buffer = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) buffer[i] = bytes.charCodeAt(i);
  return new File([buffer], fileName, { type: mimeType });
}
import { courses, groups, students as initialStudents } from "./data/mockData";
import {
  dbSave,
  dbLoadAll,
  STORE_LESSON_MATERIALS,
  STORE_COURSE_MATERIALS,
} from "./db";
import {
  fetchReviewsForLesson,
  saveReview,
  submitStudentFile,
  syncLessonContext,
} from "./api";

function App() {
  const { t, toggleLang } = useLang();
  const { role, login, logout, canAccessCourse } = useAuth();
  const [students, setStudents] = useState(initialStudents);
  const [selectedLessonId, setSelectedLessonId] = useState(
    courses[0].semesters[0].lessons[0].id,
  );
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [activeReview, setActiveReview] = useState(null);
  const [approvedReviews, setApprovedReviews] = useState({});
  const [isStudentManagerOpen, setIsStudentManagerOpen] = useState(false);
  const [submissionsStatus, setSubmissionsStatus] = useState({
    loading: false,
    error: null,
  });
  const [gradingStudents, setGradingStudents] = useState({});
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [lessonMaterials, setLessonMaterials] = useState({});
  const [courseMaterials, setCourseMaterials] = useState({});

  // Load all persisted materials from IndexedDB on mount
  useEffect(() => {
    dbLoadAll(STORE_LESSON_MATERIALS)
      .then(setLessonMaterials)
      .catch(() => {});
    dbLoadAll(STORE_COURSE_MATERIALS)
      .then(setCourseMaterials)
      .catch(() => {});
  }, []);

  // Fetch approved submissions from backend whenever the selected lesson changes
  useEffect(() => {
    const controller = new AbortController();
    setSubmissionsStatus({ loading: true, error: null });

    fetchReviewsForLesson(selectedLessonId, controller.signal)
      .then((reviews) => {
        const mapped = {};
        for (const r of reviews) {
          const key = `${r.lesson_key}-${r.student_id}`;
          mapped[key] = {
            fileName: r.file_name,
            score: r.score,
            cheatingRisk: r.cheating_risk,
            feedback: r.feedback,
          };
        }
        setApprovedReviews((prev) => ({ ...prev, ...mapped }));
        setSubmissionsStatus({ loading: false, error: null });
      })
      .catch((err) => {
        if (err.name === "AbortError") return;
        setSubmissionsStatus({ loading: false, error: err.message });
      });

    return () => controller.abort();
  }, [selectedLessonId]);

  // Only show courses this role can access
  const visibleCourses = courses.filter((c) => canAccessCourse(c.id));

  const handleLogin = (selectedRole) => {
    login(selectedRole);
    // Auto-select first lesson of the role's course (or course-1 for manager)
    const firstCourseId =
      selectedRole === ROLES.MANAGER ? "course-1" : ROLE_COURSE[selectedRole];
    const firstCourse =
      courses.find((c) => c.id === firstCourseId) ?? courses[0];
    setSelectedLessonId(firstCourse.semesters[0].lessons[0].id);
  };

  const handleLogout = () => logout();

  // Use the first group as the fixed context (group selection removed)
  const activeGroup = { ...groups[0], ...t.groups[groups[0].id] };

  const selectedLessonLabel = useMemo(() => {
    for (const course of courses) {
      for (const semester of course.semesters) {
        const lesson = semester.lessons.find(
          (item) => item.id === selectedLessonId,
        );
        if (lesson) {
          const semNum = semester.name.split(" ")[1];
          const lessonNum = lesson.title.split(" ")[1];
          return `${t.courseLabels[course.id]} · ${t.semester} ${semNum} · ${t.lesson} ${lessonNum}`;
        }
      }
    }
    return t.noLessonSelected;
  }, [selectedLessonId, t]);

  const reviewStorageKey = (lessonId, studentId) => `${lessonId}-${studentId}`;

  const reviewsByStudent = useMemo(
    () =>
      students.reduce((accumulator, student) => {
        const savedReview =
          approvedReviews[reviewStorageKey(selectedLessonId, student.id)];
        if (savedReview) {
          accumulator[student.id] = savedReview;
        }
        return accumulator;
      }, {}),
    [approvedReviews, selectedLessonId, students],
  );

  const handleUpload = async (student, file) => {
    setGradingStudents((prev) => ({ ...prev, [student.id]: true }));
    try {
      const result = await submitStudentFile({
        lessonKey: selectedLessonId,
        studentId: student.id,
        studentName: student.name,
        file,
      });
      setActiveReview({
        lessonId: selectedLessonId,
        studentId: student.id,
        studentName: student.name,
        fileName: file.name,
        score: result.recommended_score,
        cheatingRisk: result.cheating_flag ? "high" : "low",
        feedback: result.ai_feedback_draft,
      });
    } catch (err) {
      setSubmissionsStatus((prev) => ({
        ...prev,
        error: `Grading failed for ${student.name}: ${err.message}`,
      }));
    } finally {
      setGradingStudents((prev) => ({ ...prev, [student.id]: false }));
    }
  };

  const handleUploadMaterial = (type, file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const key = `${selectedYear}-${selectedLessonId}`;
      const fileData = {
        name: file.name,
        size: file.size,
        mimeType: file.type,
        dataUrl: e.target.result,
      };
      setLessonMaterials((prev) => {
        const updated = {
          ...prev,
          [key]: { ...(prev[key] ?? {}), [type]: fileData },
        };
        dbSave(STORE_LESSON_MATERIALS, key, updated[key]).catch(() => {});

        // Auto-sync to MongoDB when all 3 required context files are present
        const slot = updated[key];
        if (slot?.lecture && slot?.exercise && slot?.solution) {
          const lessonNumber = parseInt(
            selectedLessonId.split("-l")[1] ?? "1",
            10,
          );
          const courseKey = `${selectedYear}-${selectedCourseId}`;
          const syllabusData = courseMaterials[courseKey]?.syllabus;
          syncLessonContext({
            lessonKey: selectedLessonId,
            courseId: selectedCourseId,
            lessonNumber,
            lectureFile: dataUrlToFile(slot.lecture.dataUrl, slot.lecture.name),
            assignmentFile: dataUrlToFile(
              slot.exercise.dataUrl,
              slot.exercise.name,
            ),
            solutionFile: dataUrlToFile(
              slot.solution.dataUrl,
              slot.solution.name,
            ),
            rubricFile: slot.rubric
              ? dataUrlToFile(slot.rubric.dataUrl, slot.rubric.name)
              : null,
            syllabusFile: syllabusData?.dataUrl
              ? dataUrlToFile(syllabusData.dataUrl, syllabusData.name)
              : null,
          }).catch((err) =>
            console.warn("Lesson sync to backend failed:", err),
          );
        }

        return updated;
      });
    };
    reader.readAsDataURL(file);
  };

  const handleUploadCourseMaterial = (type, file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const key = `${selectedYear}-${selectedCourseId}`;
      const fileData = {
        name: file.name,
        size: file.size,
        mimeType: file.type,
        dataUrl: e.target.result,
      };
      setCourseMaterials((prev) => {
        const updated = {
          ...prev,
          [key]: { ...(prev[key] ?? {}), [type]: fileData },
        };
        dbSave(STORE_COURSE_MATERIALS, key, updated[key]).catch(() => {});
        return updated;
      });
    };
    reader.readAsDataURL(file);
  };

  const selectedCourseId = useMemo(() => {
    for (const course of courses) {
      for (const semester of course.semesters) {
        if (semester.lessons.some((l) => l.id === selectedLessonId)) {
          return course.id;
        }
      }
    }
    return courses[0].id;
  }, [selectedLessonId]);

  const currentMaterials =
    lessonMaterials[`${selectedYear}-${selectedLessonId}`] ?? {};

  const currentCourseMaterials =
    courseMaterials[`${selectedYear}-${selectedCourseId}`] ?? {};

  const handleViewReview = (student) => {
    const key = reviewStorageKey(selectedLessonId, student.id);
    const review = approvedReviews[key];
    if (!review) return;
    setActiveReview({
      lessonId: selectedLessonId,
      studentId: student.id,
      studentName: student.name,
      fileName: review.fileName,
      score: review.score,
      cheatingRisk: review.cheatingRisk,
      feedback: review.feedback,
    });
  };

  const handleApproveFeedback = (feedback) => {
    if (!activeReview) return;

    const reviewData = {
      fileName: activeReview.fileName,
      score: activeReview.score,
      cheatingRisk: activeReview.cheatingRisk,
      feedback,
    };

    const key = reviewStorageKey(activeReview.lessonId, activeReview.studentId);
    setApprovedReviews((current) => ({ ...current, [key]: reviewData }));

    // Persist to MongoDB (fire-and-forget — UI already updated optimistically)
    saveReview({
      lessonKey: activeReview.lessonId,
      studentId: activeReview.studentId,
      studentName: activeReview.studentName,
      fileName: activeReview.fileName,
      score: activeReview.score,
      cheatingRisk: activeReview.cheatingRisk,
      feedback,
    }).catch((err) => console.warn("Failed to save review to backend:", err));

    setActiveReview(null);
  };

  return (
    <div className={isDarkMode ? "dark" : ""} dir={t.dir}>
      {!role ? (
        <LoginScreen
          isDarkMode={isDarkMode}
          onToggleDarkMode={() => setIsDarkMode((v) => !v)}
          onLogin={handleLogin}
        />
      ) : (
        <main className="min-h-screen bg-blue-50 text-slate-900 transition dark:bg-slate-900 dark:text-slate-100">
          <header className="flex items-center justify-between border-b border-blue-200 bg-blue-900 px-6 py-4 text-white dark:border-slate-700 dark:bg-slate-950">
            <div>
              <p className="text-lg font-semibold">{t.appTitle}</p>
              <p className="text-xs text-blue-200">{t.roles[role]?.label}</p>
            </div>
            <div className="flex items-center gap-3">
              {/* Logout */}
              <button
                type="button"
                onClick={handleLogout}
                title={t.logout}
                className="rounded-lg border border-blue-300/50 p-1.5 text-white transition hover:bg-blue-800"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="h-5 w-5"
                >
                  <path
                    fillRule="evenodd"
                    d="M3 4.25A2.25 2.25 0 0 1 5.25 2h5.5A2.25 2.25 0 0 1 13 4.25v2a.75.75 0 0 1-1.5 0v-2a.75.75 0 0 0-.75-.75h-5.5a.75.75 0 0 0-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 0 0 .75-.75v-2a.75.75 0 0 1 1.5 0v2A2.25 2.25 0 0 1 10.75 18h-5.5A2.25 2.25 0 0 1 3 15.75V4.25Z"
                    clipRule="evenodd"
                  />
                  <path
                    fillRule="evenodd"
                    d="M19 10a.75.75 0 0 0-.75-.75H8.704l1.048-1.068a.75.75 0 1 0-1.064-1.059l-2.25 2.3a.75.75 0 0 0 0 1.054l2.25 2.3a.75.75 0 1 0 1.064-1.058L8.704 10.75H18.25A.75.75 0 0 0 19 10Z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
              {/* Language toggle */}
              <button
                type="button"
                onClick={toggleLang}
                title={t.langToggle}
                className="rounded-lg border border-blue-300/50 p-1.5 text-lg leading-none text-white transition hover:bg-blue-800"
              >
                🌐
              </button>
              <DarkModeToggle
                enabled={isDarkMode}
                onToggle={() => setIsDarkMode((value) => !value)}
              />
            </div>
          </header>

          <div className="mx-auto flex max-w-7xl flex-col gap-4 p-4 lg:flex-row">
            <div className="flex w-full flex-col gap-4 lg:w-96">
              <CourseNavigator
                courses={visibleCourses}
                selectedLessonId={selectedLessonId}
                onSelectLesson={(_, __, lessonId) =>
                  setSelectedLessonId(lessonId)
                }
              />
              {role === ROLES.MANAGER && <CourseSetupPanel />}
            </div>
            <LessonView
              groupName={activeGroup.name}
              selectedLesson={selectedLessonLabel}
              selectedLessonId={selectedLessonId}
              selectedCourseId={selectedCourseId}
              students={students}
              onUpload={handleUpload}
              reviewsByStudent={reviewsByStudent}
              onManageStudents={() => setIsStudentManagerOpen(true)}
              isManager={role === ROLES.MANAGER}
              selectedYear={selectedYear}
              onYearChange={setSelectedYear}
              currentMaterials={currentMaterials}
              onUploadMaterial={handleUploadMaterial}
              currentCourseMaterials={currentCourseMaterials}
              onUploadCourseMaterial={handleUploadCourseMaterial}
              submissionsLoading={submissionsStatus.loading}
              submissionsError={submissionsStatus.error}
              gradingStudents={gradingStudents}
              onViewReview={handleViewReview}
            />
          </div>

          <ReviewModal
            key={
              activeReview
                ? activeReview.lessonId +
                  "-" +
                  activeReview.studentId +
                  "-" +
                  activeReview.fileName
                : "review-modal"
            }
            reviewData={activeReview}
            onClose={() => setActiveReview(null)}
            onApprove={handleApproveFeedback}
          />

          {isStudentManagerOpen && (
            <StudentManager
              students={students}
              onUpdate={setStudents}
              onClose={() => setIsStudentManagerOpen(false)}
            />
          )}
        </main>
      )}
    </div>
  );
}

export default App;
