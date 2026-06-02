import { useLang } from "../contexts/LanguageContext";
import { ROLES } from "../contexts/AuthContext";
import DarkModeToggle from "./DarkModeToggle";

const ROLE_ORDER = [
  ROLES.MANAGER,
  ROLES.INSTRUCTOR_INTRO,
  ROLES.INSTRUCTOR_NETWORKS,
  ROLES.INSTRUCTOR_PRINCIPLES,
  ROLES.INSTRUCTOR_ARCH,
];

function LoginScreen({ isDarkMode, onToggleDarkMode, onLogin }) {
  const { t, toggleLang } = useLang();

  return (
    <main className="flex min-h-screen flex-col bg-blue-50 text-slate-900 dark:bg-slate-900 dark:text-slate-100">
      {/* Top bar */}
      <header className="flex items-center justify-between border-b border-blue-200 bg-blue-900 px-6 py-4 text-white dark:border-slate-700 dark:bg-slate-950">
        <div>
          <p className="text-lg font-semibold">{t.appTitle}</p>
          <p className="text-xs text-blue-100">{t.appSubtitle}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggleLang}
            title={t.langToggle}
            className="rounded-lg border border-blue-300/50 p-1.5 text-lg leading-none text-white transition hover:bg-blue-800"
          >
            🌐
          </button>
          <DarkModeToggle enabled={isDarkMode} onToggle={onToggleDarkMode} />
        </div>
      </header>

      {/* Role selection */}
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-lg">
          <h1 className="text-2xl font-bold text-blue-950 dark:text-blue-100">
            {t.loginTitle}
          </h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            {t.loginSubtitle}
          </p>

          {/* Mock auth notice */}
          <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
            {t.loginMockNotice}
          </p>

          <div className="mt-6 grid gap-3">
            {ROLE_ORDER.map((roleKey) => {
              const roleInfo = t.roles[roleKey];
              const isManager = roleKey === ROLES.MANAGER;
              return (
                <button
                  key={roleKey}
                  type="button"
                  onClick={() => onLogin(roleKey)}
                  className={`rounded-xl border p-4 text-start transition ${
                    isManager
                      ? "border-blue-400/70 bg-blue-900 text-white hover:bg-blue-800 dark:border-blue-500 dark:bg-blue-950 dark:hover:bg-blue-900"
                      : "border-blue-200/80 bg-white hover:bg-blue-50 dark:border-slate-600 dark:bg-slate-800 dark:hover:bg-slate-700"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-base">{isManager ? "👑" : "👤"}</span>
                    <p
                      className={`font-semibold ${isManager ? "text-white" : "text-blue-950 dark:text-blue-100"}`}
                    >
                      {roleInfo.label}
                    </p>
                  </div>
                  <p
                    className={`mt-0.5 text-xs ${isManager ? "text-blue-200" : "text-slate-500 dark:text-slate-400"}`}
                  >
                    {roleInfo.desc}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </main>
  );
}

export default LoginScreen;
