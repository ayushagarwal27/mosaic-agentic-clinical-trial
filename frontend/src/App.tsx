import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Health } from "./types";
import {
  applyTheme,
  initialTheme,
  readStoredTheme,
  storeTheme,
  systemTheme,
  type Theme,
} from "./theme";
import { AnalyzeView } from "./components/AnalyzeView";
import { MemoryView } from "./components/MemoryView";
import { ReviewView } from "./components/ReviewView";
import { SignalsView } from "./components/SignalsView";
import { SponsorsView } from "./components/SponsorsView";

const TABS = [
  { id: "analyze", label: "Analyze" },
  { id: "signals", label: "Signals" },
  { id: "review", label: "Review" },
  { id: "memory", label: "Memory" },
  { id: "sponsors", label: "Sponsors" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function App() {
  // The hash keeps the current tab in the URL so a reload or a shared
  // link lands in the right place, without pulling in a router.
  const [tab, setTab] = useState<TabId>(() => tabFromHash(location.hash));
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Follow the OS while the user has not made an explicit choice, so
  // switching macOS to light mode at dusk switches the console too.
  // Once they have picked a side, their choice wins and this stops.
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => {
      if (!readStoredTheme()) setTheme(systemTheme());
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const toggleTheme = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    storeTheme(next);
    setTheme(next);
  };

  useEffect(() => {
    const onHashChange = () => setTab(tabFromHash(location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
      setHealthError(false);
    } catch {
      setHealthError(true);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
    // The health check opens its own database pool on every call, so poll
    // slowly — this is a status light, not a metrics feed.
    const id = window.setInterval(() => void refreshHealth(), 60_000);
    return () => window.clearInterval(id);
  }, [refreshHealth]);

  const select = (id: TabId) => {
    location.hash = id;
    setTab(id);
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">
            ◈
          </span>
          <div>
            <h1>MOSAIC</h1>
            <span className="tagline">Clinical Trial Intelligence</span>
          </div>
        </div>

        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? "on" : ""}`}
              onClick={() => select(t.id)}
            >
              {t.label}
              {t.id === "review" && !!health?.details.pending_reviews && (
                <span className="badge">{health.details.pending_reviews}</span>
              )}
            </button>
          ))}
        </nav>

        <button
          className="theme-toggle"
          onClick={toggleTheme}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>

        <div className="health" title={health?.database ?? "unknown"}>
          <span
            className={`health-dot ${
              healthError ? "down" : health?.status === "healthy" ? "up" : "warn"
            }`}
          />
          <span className="health-text">
            {healthError
              ? "API unreachable"
              : health
                ? `${health.details.signals_in_db} signals · ${health.details.episodes_count} episodes`
                : "checking…"}
          </span>
        </div>
      </header>

      <main>
        {tab === "analyze" && <AnalyzeView onRunComplete={refreshHealth} />}
        {tab === "signals" && <SignalsView />}
        {tab === "review" && <ReviewView onDecision={refreshHealth} />}
        {tab === "memory" && <MemoryView />}
        {tab === "sponsors" && <SponsorsView />}
      </main>
    </div>
  );
}

function tabFromHash(hash: string): TabId {
  const id = hash.replace(/^#/, "") as TabId;
  return TABS.some((t) => t.id === id) ? id : "analyze";
}
