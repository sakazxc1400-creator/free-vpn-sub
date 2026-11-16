import { useEffect, useState } from "react";

export function readTheme() {
  try {
    const saved = localStorage.getItem("fvps-theme");
    if (["light", "dark", "system"].includes(saved)) return saved;
  } catch { /* Storage is optional. */ }
  return "system";
}

export function resolvedTheme(preference) {
  return preference === "system"
    ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : preference;
}

export default function useTheme() {
  const [preference, setPreference] = useState(readTheme);
  const [system, setSystem] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);

  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const change = (event) => setSystem(event.matches);
    setSystem(query.matches);
    query.addEventListener("change", change);
    return () => query.removeEventListener("change", change);
  }, []);

  useEffect(() => {
    const resolved = preference === "system" ? (system ? "dark" : "light") : preference;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.themePreference = preference;
    document.documentElement.style.colorScheme = resolved;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", resolved === "dark" ? "#11161b" : "#eef2f4");
    try { localStorage.setItem("fvps-theme", preference); } catch { /* Storage is optional. */ }
  }, [preference, system]);

  return { preference, setPreference, resolved: preference === "system" ? (system ? "dark" : "light") : preference };
}
