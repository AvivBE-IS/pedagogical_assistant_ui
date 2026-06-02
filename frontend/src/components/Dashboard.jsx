import { useLang } from "../contexts/LanguageContext";

function Dashboard({ groups, onSelectGroup }) {
  const { t } = useLang();

  return (
    <section className="mx-auto mt-16 max-w-3xl rounded-2xl border border-blue-200/60 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <h1 className="text-3xl font-bold text-blue-950 dark:text-blue-100">
        {t.dashboardTitle}
      </h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
        {t.dashboardSubtitle}
      </p>
      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {groups.map((group) => {
          const label = t.groups[group.id] || group;
          return (
            <button
              key={group.id}
              type="button"
              onClick={() => onSelectGroup(group.id)}
              className="rounded-xl border border-blue-300/70 bg-blue-50 p-4 text-left transition hover:bg-blue-100 dark:border-slate-600 dark:bg-slate-900 dark:hover:bg-slate-700"
            >
              <p className="font-semibold text-blue-950 dark:text-blue-100">
                {label.name}
              </p>
              <p className="text-xs text-slate-600 dark:text-slate-300">
                {label.track}
              </p>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export default Dashboard;
