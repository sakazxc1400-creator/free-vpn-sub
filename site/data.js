import { MIRRORS } from "./config.js";

export function timestamp(value) {
  return typeof value === "string" ? Date.parse(value.replace(" UTC", "Z").replace(" ", "T")) : NaN;
}

export function snapshotState(value, now) {
  const time = timestamp(value);
  if (!Number.isFinite(time)) return "unknown";
  if (time > now + 5 * 60000) return "future";
  if (now - time > 8 * 3600000) return "stale";
  return "fresh";
}

export function age(value, now) {
  const state = snapshotState(value, now);
  if (state === "unknown") return "Update time unavailable";
  if (state === "future") return "Snapshot time is in the future";
  const time = timestamp(value);
  const minutes = Math.floor((now - time) / 60000);
  if (minutes < 1) return "Updated just now";
  if (minutes < 60) return `Updated ${minutes}m ago`;
  if (minutes < 1440) return `Updated ${Math.floor(minutes / 60)}h ago`;
  return `Updated ${Math.floor(minutes / 1440)}d ago`;
}

export function validStats(data) {
  return data && typeof data === "object" && !Array.isArray(data)
    && Number.isInteger(data.published) && data.published >= 0
    && Number.isFinite(timestamp(data.updated))
    && ["published_full", "verified", "countries", "stable", "stable_runs", "best_latency_ms"]
      .every((key) => data[key] == null || (typeof data[key] === "number" && Number.isFinite(data[key]) && data[key] >= 0))
    && (data.published_full == null || data.published <= data.published_full)
    && (data.stable == null || data.stable <= data.published)
    && (data.countries == null || data.published_full == null || data.countries <= data.published_full);
}

export function validNode(node) {
  return node && typeof node.addr === "string" && node.addr.length <= 2048
    && typeof node.proto === "string" && ["vless", "vmess", "trojan", "ss", "hysteria2", "tuic"].includes(node.proto)
    && typeof node.cc === "string" && (node.cc === "" || /^[A-Z]{2}$/.test(node.cc))
    && typeof node.tls === "boolean" && typeof node.url === "string" && node.url.length <= 32768
    && /^(vless|vmess|trojan|ss|hysteria2|hy2|tuic):\/\//i.test(node.url)
    && (node.ms === null || (typeof node.ms === "number" && Number.isFinite(node.ms) && node.ms >= 0))
    && (node.mbps == null || (typeof node.mbps === "number" && Number.isFinite(node.mbps) && node.mbps >= 0));
}

export function validNodes(data) {
  return Array.isArray(data) && data.length <= 200 && data.every(validNode)
    && new Set(data.map((node) => node.url)).size === data.length;
}

async function fetchOne(base, file, validate, signal, timeout) {
  const controller = new AbortController();
  const abort = () => controller.abort(signal.reason);
  signal.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(abort, timeout);
  try {
    const response = await fetch(base + file, { signal: controller.signal, cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!validate(data)) throw new Error("Invalid snapshot payload");
    return data;
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", abort);
  }
}

export async function fetchData(file, validate, signal, timeout = 5000) {
  let lastError;
  for (const [source, base] of MIRRORS) {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    try {
      const data = await fetchOne(base, file, validate, signal, timeout);
      return { data, source };
    } catch (error) {
      if (signal.aborted) throw error;
      lastError = error;
    }
  }
  throw lastError || new Error("All data sources are unavailable");
}
