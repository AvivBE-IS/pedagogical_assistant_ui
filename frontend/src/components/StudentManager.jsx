import { useState } from "react";
import { useLang } from "../contexts/LanguageContext";

function StudentManager({ students, onUpdate, onClose }) {
  const { t } = useLang();
  const [newName, setNewName] = useState("");
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState("");

  const handleAdd = () => {
    const trimmed = newName.trim();
    if (!trimmed) return;
    onUpdate([...students, { id: `student-${Date.now()}`, name: trimmed }]);
    setNewName("");
  };

  const handleDelete = (id) => {
    onUpdate(students.filter((s) => s.id !== id));
  };

  const startRename = (student) => {
    setRenamingId(student.id);
    setRenameValue(student.name);
  };

  const handleSaveRename = () => {
    const trimmed = renameValue.trim();
    if (!trimmed) return;
    onUpdate(
      students.map((s) => (s.id === renamingId ? { ...s, name: trimmed } : s)),
    );
    setRenamingId(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-blue-950/70 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl dark:bg-slate-800">
        <h3 className="text-lg font-semibold text-blue-950 dark:text-blue-100">
          {t.studentsManagerTitle}
        </h3>

        <div className="mt-4 flex gap-2">
          <input
            className="flex-1 rounded-lg border border-blue-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            placeholder={t.addStudentPlaceholder}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          />
          <button
            type="button"
            className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800"
            onClick={handleAdd}
          >
            {t.addStudentBtn}
          </button>
        </div>

        <ul className="mt-4 max-h-80 space-y-2 overflow-y-auto">
          {students.length === 0 && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t.noStudents}
            </p>
          )}
          {students.map((student) => (
            <li
              key={student.id}
              className="flex items-center gap-2 rounded-lg border border-blue-100 bg-blue-50/70 p-2 dark:border-slate-700 dark:bg-slate-900/60"
            >
              {renamingId === student.id ? (
                <>
                  <input
                    className="flex-1 rounded border border-blue-200 px-2 py-1 text-sm focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSaveRename()}
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={handleSaveRename}
                    className="text-xs font-semibold text-blue-700 dark:text-blue-300"
                  >
                    {t.saveRename}
                  </button>
                  <button
                    type="button"
                    onClick={() => setRenamingId(null)}
                    className="text-xs text-slate-500"
                  >
                    {t.cancel}
                  </button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm font-medium text-blue-950 dark:text-blue-100">
                    {student.name}
                  </span>
                  <button
                    type="button"
                    onClick={() => startRename(student)}
                    className="text-xs text-blue-600 hover:underline dark:text-blue-300"
                  >
                    {t.renameStudent}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(student.id)}
                    className="text-xs text-red-500 hover:underline"
                  >
                    {t.deleteStudent}
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-500 dark:text-slate-200 dark:hover:bg-slate-700"
            onClick={onClose}
          >
            {t.close}
          </button>
        </div>
      </div>
    </div>
  );
}

export default StudentManager;
