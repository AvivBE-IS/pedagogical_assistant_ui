function DarkModeToggle({ enabled, onToggle }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-3 text-sm font-medium text-slate-100">
      <span>{enabled ? 'Dark mode' : 'Light mode'}</span>
      <button
        type="button"
        onClick={onToggle}
        className={`relative h-7 w-14 rounded-full transition ${
          enabled ? 'bg-blue-400' : 'bg-blue-900/60'
        }`}
        aria-pressed={enabled}
      >
        <span
          className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${
            enabled ? 'left-8' : 'left-1'
          }`}
        />
      </button>
    </label>
  )
}

export default DarkModeToggle
