import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";
import worker from "./mirror/worker.js";

function setup(fetcher, cached = null) {
  const saved = [];
  globalThis.caches = { default: { match: async () => cached?.clone(), put: async (key, response) => { saved.push(await response.text()); } } };
  globalThis.fetch = fetcher;
  const pending = [];
  return { saved, ctx: { waitUntil: (task) => pending.push(task) }, done: () => Promise.all(pending) };
}

test("HEAD has no body and caches the complete GET response", async () => {
  const mock = setup(async () => new Response("subscription payload"));
  const response = await worker.fetch(new Request("https://mirror.example/sub.txt", { method: "HEAD" }), {}, mock.ctx);
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "");
  await mock.done();
  assert.deepEqual(mock.saved, ["subscription payload"]);
});

test("cached HEAD is bodyless and includes CORS", async () => {
  const mock = setup(() => { throw new Error("Cache should be used"); }, new Response("cached"));
  const response = await worker.fetch(new Request("https://mirror.example/sub.txt", { method: "HEAD" }), {}, mock.ctx);
  assert.equal(await response.text(), "");
  assert.equal(response.headers.get("access-control-allow-origin"), "*");
});

test("worker falls back on upstream or body failures", async () => {
  let calls = 0;
  const mock = setup(async (url, options) => {
    assert.ok(options.signal instanceof AbortSignal);
    if (++calls === 1) return { ok: true, text: async () => { throw new Error("Interrupted body"); } };
    return new Response("fallback");
  });
  const response = await worker.fetch(new Request("https://mirror.example/sub.txt"), {}, mock.ctx);
  assert.equal(await response.text(), "fallback");
  assert.equal(response.headers.get("x-mirror"), "jsdelivr");
  await mock.done();
});

test("worker enforces file allowlist and request methods", async () => {
  const mock = setup(() => { throw new Error("Must not fetch"); });
  const head = await worker.fetch(new Request("https://mirror.example/secrets.txt", { method: "HEAD" }), {}, mock.ctx);
  assert.equal(head.status, 404);
  assert.equal(await head.text(), "");
  const post = await worker.fetch(new Request("https://mirror.example/sub.txt", { method: "POST" }), {}, mock.ctx);
  assert.equal(post.status, 405);
  assert.equal(post.headers.get("allow"), "GET, HEAD, OPTIONS");
});

test("retired service worker only clears this project's caches", async () => {
  const events = {};
  const removed = [];
  let unregistered = false;
  vm.runInNewContext(await readFile("site/public/sw.js", "utf8"), {
    self: { addEventListener: (event, handler) => { events[event] = handler; },
      registration: { unregister: async () => { unregistered = true; } } },
    caches: { keys: async () => ["fvps-shell-v7", "another-project-v2"], delete: async (key) => removed.push(key) },
  });
  let task;
  events.activate({ waitUntil: (promise) => { task = promise; } });
  await task;
  assert.deepEqual(removed, ["fvps-shell-v7"]);
  assert.equal(unregistered, true);
});
