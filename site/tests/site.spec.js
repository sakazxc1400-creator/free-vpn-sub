import { test, expect } from "@playwright/test";

const UUID = "11111111-2222-3333-4444-555555555555";
const stats = {
  updated: new Date().toISOString(), published: 128, published_full: 1842,
  verified: 1842, countries: 34, best_latency_ms: 28, stable: 64, stable_runs: 6,
};
const nodes = Array.from({ length: 18 }, (_, index) => ({
  i: index + 1, cc: ["NL", "DE", "US", "GB", "JP", "SG"][index % 6],
  proto: index % 2 ? "trojan" : "vless", addr: `1.2.3.${index + 1}:443`,
  ms: 28 + index * 22, tls: true, up: index, url: `${index % 2 ? "trojan" : "vless"}://${UUID}@1.2.3.${index + 1}:443`,
}));

async function mockNetwork(page) {
  await page.route(/\/output\/(stats|nodes)\.json/, (route) => route.fulfill({ json: route.request().url().includes("stats.json") ? stats : nodes }));
}

test("subscription tabs, mirror selection and copy stay in sync", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await mockNetwork(page);
  await page.goto("/");
  await page.getByRole("tab", { name: "Stable", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Subscription URL" })).toHaveValue(/sub-stable\.txt$/);
  await page.getByLabel("Can't reach GitHub? Try a mirror").selectOption("1");
  await expect(page.getByRole("textbox", { name: "Subscription URL" })).toHaveValue(/^https:\/\/cdn.jsdelivr.net\/.*sub-stable\.txt$/);
  await page.getByRole("button", { name: "Copy subscription", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copied", exact: true })).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toContain("@data/output/sub-stable.txt");
  await expect(page.getByRole("link", { name: "Open in Hiddify" })).toHaveAttribute("href", /hiddify:\/\/import\/https:\/\/cdn.jsdelivr.net/);
  await page.getByRole("tab", { name: "Clash / Mihomo" }).click();
  await expect(page.getByRole("textbox", { name: "Subscription URL" })).toHaveValue(/clash\.yaml$/);
  await expect(page.getByRole("link", { name: "Open in Clash" })).toHaveAttribute("href", /^clash:\/\/install-config\?/);
});

test("keyboard tab navigation and server filters work", async ({ page }) => {
  await mockNetwork(page);
  await page.goto("/");
  await page.getByRole("tab", { name: /Everyday/ }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Stable", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("tbody tr")).toHaveCount(6);
  await page.getByRole("button", { name: "Show more servers" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(18);
  await page.getByRole("searchbox", { name: "Search servers" }).fill("Netherlands");
  await expect(page.locator("tbody tr")).toHaveCount(3);
  await page.getByLabel("Filter by protocol").selectOption("trojan");
  await expect(page.getByRole("heading", { name: "No servers found" })).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(6);
});

test("all sources failing leaves usable subscription links", async ({ page }) => {
  await page.route(/\/output\/(stats|nodes)\.json/, (route) => route.fulfill({ status: 503, body: "Unavailable" }));
  await page.goto("/");
  await expect(page.getByText("Live data is taking a break.")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Subscription URL" })).toHaveValue(/data\/output\/sub\.txt$/);
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeEnabled();
  await expect(page.locator(".stat-value").first()).toHaveText("—");
});

test("invalid mirror payloads cannot crash the page or mark nodes as verified", async ({ page }) => {
  await page.route(/\/output\/(stats|nodes)\.json/, (route) => {
    const primary = route.request().url().includes("raw.githubusercontent.com");
    const payload = route.request().url().includes("stats.json")
      ? (primary ? { ...stats, stable_runs: { bad: true } } : stats)
      : (primary ? [{ ...nodes[0], cc: {}, tls: "false" }] : nodes);
    return route.fulfill({ json: payload });
  });
  await page.goto("/");
  await expect(page.getByText("Data from jsDelivr")).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(6);
});

test("blocked primary source times out and switches to a mirror", async ({ page }) => {
  await page.route(/\/output\/(stats|nodes)\.json/, async (route) => {
    if (route.request().url().includes("raw.githubusercontent.com")) {
      await new Promise((resolve) => setTimeout(resolve, 6500));
      await route.abort().catch(() => {});
      return;
    }
    await route.fulfill({ json: route.request().url().includes("stats.json") ? stats : nodes });
  });
  await page.goto("/");
  await expect(page.getByText("Data from jsDelivr")).toBeVisible({ timeout: 10000 });
  await expect(page.locator("tbody tr")).toHaveCount(6);
});

for (const [name, width, height] of [["mobile", 375, 812], ["tablet", 768, 1024], ["desktop", 1440, 1000], ["landscape", 812, 375]]) {
  test(`${name} layout has no overflow or runtime errors`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await mockNetwork(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.locator("tbody tr")).toHaveCount(6);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: true });
    expect(errors).toEqual([]);
  });
}
