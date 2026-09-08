export type Theme = "dark" | "light";

const STORAGE_KEY = "mosaic.theme";

// localStorage throws outright in some privacy modes rather than just
// returning null, so every access here is guarded and falls back to a
// working default instead of taking the app down with it.
export function readStoredTheme(): Theme | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "light" || saved === "dark" ? saved : null;
  } catch {
    return null;
  }
}

export function storeTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Preference simply will not persist — not worth surfacing.
  }
}

export function systemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

// The inline script in index.html has already stamped <html> by the time
// React runs, so read that back rather than recomputing and risking a
// mismatch between what is painted and what the app thinks is active.
export function initialTheme(): Theme {
  const stamped = document.documentElement.getAttribute("data-theme");
  if (stamped === "light" || stamped === "dark") return stamped;
  return readStoredTheme() ?? systemTheme();
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
}
