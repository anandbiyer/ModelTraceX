/**
 * App-shell placeholder (SDD §13.4.0 — persistent header + five-tab bar).
 * Scaffold only: the Upload/Review/Lineage/Data Quality/Chat tabs and their
 * shared primitives (inspector, filter chips, diff block) are built in Phase 2.
 */
const TABS = ["Upload", "Review", "Lineage", "Data Quality", "Chat"] as const;

export default function App() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="flex items-center gap-3 border-b border-border bg-sidebar px-4 py-3">
        <span className="font-extrabold tracking-tight">Modelis</span>
        <span className="rounded bg-accent-soft px-1.5 py-0.5 text-xs text-accent">ModelTraceX</span>
        <span className="rounded border border-border px-1.5 py-0.5 text-xs text-dim">v2</span>
      </header>

      <nav className="flex gap-4 border-b border-border-soft px-4">
        {TABS.map((tab, i) => (
          <button
            key={tab}
            className={
              "border-b-2 py-2 text-sm " +
              (i === 0 ? "border-accent text-text" : "border-transparent text-dim hover:text-text")
            }
          >
            {tab}
          </button>
        ))}
      </nav>

      <main className="p-6 text-dim">
        <p>
          ModelTraceX v2 frontend scaffold. Tabs and components are implemented in{" "}
          <span className="mono text-text">Phase 2</span>.
        </p>
      </main>
    </div>
  );
}
