const groups = [
  { id: "grp-101", name: "קבוצת פרונטאנד א", track: "פיתוח ווב" },
  { id: "grp-102", name: "קבוצת בקאנד ב", track: "הנדסת API ב-Node.js" },
  { id: "grp-103", name: "קבוצת פולסטאק ג", track: "הנדסת מוצר" },
];

const courseNames = [
  "מבוא לתכנות",
  "רשתות תקשורת",
  "עקרונות מדעי המחשב",
  "ארכיטקטורת מחשבים",
];

const courses = courseNames.map((name, courseIndex) => ({
  id: `course-${courseIndex + 1}`,
  name,
  semesters: [1, 2].map((semesterNumber) => ({
    id: `course-${courseIndex + 1}-semester-${semesterNumber}`,
    name: `סמסטר ${semesterNumber}`,
    lessons: Array.from({ length: 13 }, (_, lessonIndex) => ({
      id: `c${courseIndex + 1}-s${semesterNumber}-l${lessonIndex + 1}`,
      title: `שיעור ${lessonIndex + 1}`,
    })),
  })),
}));

const studentNames = [
  "נועה לוי",
  "איתן כהן",
  "מאיה בן-עמי",
  "ליאור אזולאי",
  "דניאל מזרחי",
  "יעל שחר",
  "נדב בר-און",
  "שירה פז",
  "עומר הראל",
  "רוני דור",
  "יובל פרץ",
  "גלעד ארד",
  "טליה כץ",
  "עמית רומנו",
  "קרן גולן",
];

const students = studentNames.map((name, index) => ({
  id: `student-${index + 1}`,
  name,
}));

const feedbackStrengths = [
  "Great effort structuring your solution and keeping naming readable.",
  "Your code flow is clear and your decomposition into functions is strong.",
  "You demonstrated solid understanding of the lesson concepts and sequencing.",
];

const feedbackImprovements = [
  "Please extract repeated logic into a reusable helper and add edge-case checks.",
  "Consider adding clearer error handling for invalid input and empty data states.",
  "Next revision should tighten validation and remove duplicated conditional blocks.",
];

const feedbackEncouragement = [
  "Keep this momentum—one more focused iteration will make this submission excellent.",
  "You are very close to production-ready quality, so continue refining with confidence.",
  "Strong progress overall. With these adjustments, your next submission should be top-tier.",
];

const getMockAiReview = (studentId, lessonId, fileName) => {
  const indexSeed = Number(studentId.split("-")[1]) + lessonId.length;
  const strength = feedbackStrengths[indexSeed % feedbackStrengths.length];
  const improvement =
    feedbackImprovements[indexSeed % feedbackImprovements.length];
  const encouragement =
    feedbackEncouragement[indexSeed % feedbackEncouragement.length];
  const score = 72 + (indexSeed % 24);
  const cheatingRisk =
    indexSeed % 5 === 0 ? "high" : indexSeed % 2 === 0 ? "medium" : "low";

  return {
    fileName,
    score,
    cheatingRisk,
    feedback: `${strength}\n\n${improvement}\n\n${encouragement}`,
  };
};

export { groups, courses, students, getMockAiReview };
