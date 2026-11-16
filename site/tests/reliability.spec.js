import { test, expect } from "@playwright/test";

const UUID = "11111111-2222-3333-4444-555555555555";
const freshStats = () => ({ updated: new Date().toISOString(), published: 2, published_full: 3, verified: 3, countries: 2, best_latency_ms: 20, stable: 0, stable_runs: 6 });
const nodes = [
  { cc: "NL", proto: "vless", addr: "a-very-long-public-hostname-for-layout-check.example.com:443", ms: null, mbps: null, tls: true, url: `vless://${UUID}@1.2.3.4:443` },
  { cc: "", proto: "trojan", addr: "5.6.7.8:443", ms: 90, mbps: null, tls: false, url: "trojan://password@5.6.7.8:443" },
];

async function routeData(page, { stats = freshStats(), nodeData = nodes, statsStatus = 200, nodesStatus = 200, statsByHost = null } = {}) {
  await page.route(/\/output\/(stats|nodes)\.json/, (route) => {
    const isStats = route.request().url().includes("stats.json");
    const status = isStats ? statsStatus : nodesStatus;
    if (status !== 200) return route.fulfill({ status, body: "Unavailable" });
    const host = new URL(route.request().url()).hostname;
    const payload = isStats ? (statsByHost?.[host] ?? stats) : nodeData;
    return route.fulfill({ json: payload });
  });
}

test("theme preference persists and system changes apply", async ({ page }) => {
  await routeData(page);
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByLabel("Theme", { exact: true }).selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(await page.evaluate(() => localStorage.getItem("fvps-theme"))).toBe("dark");
  await page.reload();
  await expect(page.getByLabel("Theme", { exact: true })).toHaveValue("dark");
  await page.getByLabel("Theme", { exact: true }).selectOption("system");
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("storage failure does not block theme controls or content", async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => { throw new Error("Storage denied"); };
    Storage.prototype.setItem = () => { throw new Error("Storage denied"); };
  });
  await routeData(page);
  await page.goto("/");
  await page.getByLabel("Theme", { exact: true }).selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("nodes-only failure keeps real stats visible and marks the partial failure", async ({ page }) => {
  await routeData(page, { nodesStatus: 503 });
  await page.goto("/");
  await expect(page.getByText("Some network data is unavailable.")).toBeVisible();
  await expect(page.locator(".stat-value").first()).toHaveText("3");
  await expect(page.getByRole("heading", { name: "Server list unavailable" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Subscription URL" })).toHaveValue(/sub\.txt$/);
});

test("stats-only failure keeps real nodes and unavailable counts", async ({ page }) => {
  await routeData(page, { statsStatus: 503 });
  await page.goto("/");
  await expect(page.getByText("Some network data is unavailable.")).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await expect(page.locator(".stat-value").first()).toHaveText("—");
  await expect(page.getByText("Server count unavailable")).toBeVisible();
});

test("different mirror generations are not presented as consistent", async ({ page }) => {
  await page.route(/\/output\/stats\.json/, (route) => route.request().url().includes("raw.githubusercontent.com")
    ? route.fulfill({ status: 503 }) : route.fulfill({ json: freshStats() }));
  await page.route(/\/output\/nodes\.json/, (route) => route.request().url().includes("raw.githubusercontent.com")
    ? route.fulfill({ json: nodes }) : route.fulfill({ status: 503 }));
  await page.goto("/");
  await expect(page.getByText(/Stats and nodes came from different mirrors/)).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(2);
});

test("future and stale timestamps are explicit, not fresh", async ({ page }) => {
  const future = { ...freshStats(), updated: new Date(Date.now() + 3600000).toISOString() };
  await routeData(page, { stats: future });
  await page.goto("/");
  await expect(page.getByText("This snapshot has a future timestamp. Its freshness cannot be verified.")).toBeVisible();
  await expect(page.getByText("Snapshot time is in the future").first()).toBeVisible();
  await routeData(page, { stats: { ...freshStats(), updated: new Date(Date.now() - 86400000).toISOString() } });
  await page.reload();
  await expect(page.getByText(/This snapshot is older than 8 hours/)).toBeVisible();
});

test("empty stable subscription has an honest state", async ({ page }) => {
  await routeData(page);
  await page.goto("/");
  await page.getByRole("tab", { name: "Stable", exact: true }).click();
  await expect(page.getByText(/The stable list is empty in this snapshot/)).toBeVisible();
  await expect(page.getByText("0 servers in this snapshot")).toBeVisible();
});

test("null metrics and long addresses do not overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await routeData(page, { stats: { ...freshStats(), best_latency_ms: null } });
  await page.goto("/");
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await expect(page.locator(".latency").last()).toHaveText("—");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("clipboard failure is reported and legacy fallback can succeed", async ({ page }) => {
  await routeData(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: () => Promise.reject(new Error("Denied")) } });
    document.execCommand = () => false;
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Copy subscription", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy failed", exact: true })).toBeVisible();
  await page.evaluate(() => { document.execCommand = () => true; });
  await page.getByRole("button", { name: "Copy failed", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copied", exact: true })).toBeVisible();
});

test("retry ignores a late response from the cancelled request", async ({ page }) => {
  let first = true;
  await page.route(/\/output\/stats\.json/, async (route) => {
    if (!route.request().url().includes("raw.githubusercontent.com")) return route.fulfill({ status: 503 });
    const initial = first;
    first = false;
    await new Promise((resolve) => setTimeout(resolve, initial ? 1400 : 100));
    return route.fulfill({ json: { ...freshStats(), published: initial ? 11 : 77, published_full: 100 } }).catch(() => {});
  });
  await page.route(/\/output\/nodes\.json/, (route) => route.fulfill({ status: 503 }));
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByText("77 servers in this snapshot")).toBeVisible();
  await page.waitForTimeout(1600);
  await expect(page.getByText("77 servers in this snapshot")).toBeVisible();
  await expect(page.getByText("11 servers in this snapshot")).toHaveCount(0);
});

test("missing IntersectionObserver does not hide content", async ({ page }) => {
  await page.addInitScript(() => { delete window.IntersectionObserver; });
  await routeData(page);
  await page.goto("/");
  await expect(page.locator(".hero-copy")).toHaveCSS("opacity", "1");
  await expect(page.locator(".principles-grid")).toHaveCSS("opacity", "1");
  await expect(page.locator("tbody tr")).toHaveCount(2);
});

test("reduced motion leaves all content available and focus visible", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await routeData(page);
  await page.goto("/");
  await expect(page.locator(".principles-grid")).toBeVisible();
  await page.getByRole("tab", { name: /Everyday/ }).focus();
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Clash / Mihomo" })).toBeFocused();
  await expect(page.locator("html")).toHaveCSS("scroll-behavior", "auto");
});
