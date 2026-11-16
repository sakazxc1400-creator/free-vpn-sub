import React, { useEffect, useRef, useState } from "react";

const paths = {
  arrow: <><path d="M5 12h14M12 5l7 7-7 7" /></>,
  external: <><path d="M7 17 17 7M7 7h10v10" /></>,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V4H4v12h4" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  globe: <><circle cx="12" cy="12" r="9" /><ellipse cx="12" cy="12" rx="4" ry="9" /><path d="M3 12h18" /></>,
  shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>,
  link: <><path d="m10 14 4-4M8 16l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M16 8l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(1 0) scale(.92 1)" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
  code: <><path d="m7 6-6 6 6 6M17 6l6 6-6 6M14 3l-4 18" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.5 7a8 8 0 0 1 13-2L20 8M4 16l1.5 3a8 8 0 0 0 13-2" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41" /></>,
  moon: <path d="M20.7 13.1A8.5 8.5 0 0 1 10.9 3.3 8.5 8.5 0 1 0 20.7 13.1Z" />,
  system: <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></>,
  chevron: <path d="m8 10 4 4 4-4" />,
};

export function Icon({ name = "arrow", size = 20, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.arrow}</svg>;
}

export function Brand() {
  return <a className="brand" href="#" aria-label="Free VPN Sub home"><svg className="brand-symbol" viewBox="0 0 32 32" aria-hidden="true"><path d="M5 17c4-9 18-9 22 0M9 21c3-5 11-5 14 0" /><circle cx="16" cy="25" r="2" /></svg><span>freevpn<span className="brand-sub"> / sub</span></span></a>;
}

export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch { /* Fall back to a selection copy. */ }
  const area = document.createElement("textarea");
  area.value = text;
  area.style.cssText = "position:fixed;opacity:0;inset:0;pointer-events:none";
  document.body.append(area);
  const focused = document.activeElement;
  try { area.select(); return document.execCommand("copy"); } catch { return false; }
  finally { area.remove(); focused?.focus(); }
}

export function CopyButton({ value, children = "Copy link", className = "", iconOnly = false, label = "Copy server link" }) {
  const [result, setResult] = useState("");
  const timer = useRef(null);
  useEffect(() => { setResult(""); return () => clearTimeout(timer.current); }, [value]);
  const copy = async () => {
    const success = await copyText(value);
    setResult(success ? "Copied" : "Copy failed");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setResult(""), 2400);
  };
  return <button type="button" className={`button ${className} ${result === "Copied" ? "copied" : ""}`} onClick={copy} aria-label={iconOnly ? (result || label) : undefined}>
    <Icon name={result === "Copied" ? "check" : "copy"} size={18} />
    <span className={iconOnly ? "sr-only" : ""} aria-live="polite" aria-atomic="true">{result || children}</span>
  </button>;
}

export function ThemeControl({ theme }) {
  return <label className="theme-control glass" title="Color theme"><Icon name={theme.resolved === "dark" ? "moon" : "sun"} size={17} /><span className="sr-only">Theme</span><select aria-label="Theme" value={theme.preference} onChange={(event) => theme.setPreference(event.target.value)}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select><Icon name="chevron" size={14} /></label>;
}

export function SectionHeading({ index, eyebrow, title, children, id }) {
  return <div className="section-heading"><div><div className="eyebrow"><span>{index}</span>{eyebrow}</div><h2 id={id}>{title}</h2></div>{children && <p>{children}</p>}</div>;
}
