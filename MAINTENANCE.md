# Development and maintenance

## Build and run

The collector uses Python 3.9+ and the standard library. Traffic verification is
required for publication. The tested engine is sing-box **1.14.4**.

```sh
python install_singbox.py
python runtests.py --require-singbox
python collect.py
```

The installer supports Windows and Linux x86-64, verifies a pinned SHA-256, and
replaces the binary only after validation. Other platforms can install sing-box
manually. PyYAML is optional locally and required by CI to validate YAML exports.

The Python 3.9 CI job is pinned to `ubuntu-24.04`: `ubuntu-latest` moved to
Ubuntu 26.04, for which `actions/setup-python` has no Python 3.9 builds. Keep
this job on a compatible runner while Python 3.9 remains the supported minimum.

The website uses React and Vite with Node.js 22.12+:

```sh
npm ci
npm run dev
```

```sh
npm run build
npm test
npx playwright install chromium
npm run test:ui
```

`site/App.jsx` composes the React application. Components live in
`site/components/`, network/theme/effect hooks in `site/hooks/`, request validation
in `site/data.js`, shared links and plans in `site/config.js`, and design tokens in
`site/styles.css`. `site/index.html` provides document metadata and the initial
theme before React starts. `site/public/` contains the favicon and retired
service worker. `npm run build` replaces `docs/` with the deployable static site;
do not hand-edit generated files. Relative asset URLs work with the repository's
GitHub Pages subpath. Commit the rebuilt `docs/` alongside source changes when
Pages is configured to publish `main /docs`.

`npm run preview:pages` serves `docs/` at both `/` and `/free-vpn-sub/` on port
4173. Playwright uses this production-file preview so asset paths are checked at
the published subpath rather than only on the Vite development server.

## Data flow

- `sources.txt` -> `collect.py`: source download, share-link parsing, deduplication,
  TCP/UDP prefiltering, history, selection, and output.
- `outbound.py` -> `probe.py`: protocol conversion and isolated sing-box batches.
- `geo.py`: geographic annotation and caching.
- `clashout.py`: Mihomo/Clash export.
- `notify.py`: optional Telegram reports.
- `mirror/worker.js`: allowlisted Cloudflare Worker mirror with bounded upstream
  requests and GET/HEAD/OPTIONS support.
- `site/App.jsx` plus `site/hooks/` and `site/data.js`: independent stats/node
  fetches with per-source timeouts, cancellation, validation, fallback mirrors,
  explicit stale/future timestamps, and mixed-mirror generation warnings. No
  fabricated production data.

## Publication invariants

1. TCP reachability and successful DNS resolution never count as traffic verification.
2. Zero traffic-verified nodes or zero HTTPS-verified nodes abort publication.
3. Everyday, stable, and Clash subscriptions exclude failed HTTPS probes.
4. The full subscription may contain traffic-working nodes that failed HTTPS.
5. Endpoint deduplication prefers verified HTTPS before latency.
6. The per-country cap is a hard cap: a subscription can contain fewer than 200 nodes.
7. `ALLOW_SHRINK=1` explicitly overrides the count guard; `0` does not.
8. All output files, history, and Clash conversion are staged before replacing the
   output directory. Generation failures preserve the previous snapshot. A failed
   replacement attempts to restore the previous directory; a failed restore keeps
   a recoverable `.subscription-*-previous` backup. An exclusive sibling lock
   serializes replacement across local collector processes. If a process is
   killed, its `.subscription-publish.lock` may require manual removal after the
   process has stopped; this is not a guarantee against a machine crash between
   filesystem renames.

## Regression fixes

- Preserve complete case-sensitive passwords, transport paths, and TLS parameters
  in configuration identities; equivalent Shadowsocks forms deduplicate.
- VMess labels are stored in `ps`, and existing fragments do not break parsing.
- URI transport paths are decoded once; plaintext Shadowsocks credentials parse.
- Missed runs reset uptime hours; malformed and future history cannot fabricate age.
- Connectivity checks require HTTP 204 instead of accepting captive-portal pages.
- Probe requests cannot bypass the selected proxy through `NO_PROXY`.
- One invalid outbound is isolated to one node rather than dropping its neighbors.
- Empty/unavailable port ranges cannot start an empty proxy process.
- Speed targets refer to the `data` branch.
- Clash name suffixes cannot collide; YAML serialization supports Python 3.9.
- End-to-end tests operate in a temporary directory and do not send Telegram reports.
- Fake sing-box tests launch through Python on Windows and propagate failures even
  when the real binary is absent. CI requires a real binary.
- Mirror HEAD responses are bodyless, failed reads fall back, encoded traversal
  segments are rejected before the allowlist, and abandoned service workers clean
  only the project's own cache prefix.
- Deduplication and history use the full configuration identity rather than only
  `host:port`; changing credentials resets the stability streak. Future history
  timestamps are discarded. History format version 3 starts a fresh sequence
  rather than transferring stability from address-keyed records.
- Source bodies are limited to 8 MiB, individual links to 16 KiB, Geo CSV input
  and decompressed output to 24 MiB, and Geo API responses to 1 MiB. HTML source
  responses are rejected. Geo cache entries expire independently after 30 days.

## Design direction

The interface uses a web interpretation of Apple's 2025 Liquid Glass design:
glass is limited to navigation and functional controls, while long-form content
and the server table use opaque surfaces. Tokens cover neutral light/dark colors,
system typography, spacing, radii, elevation, focus, and motion. The theme control
supports light, dark, and system preferences, persists when storage is available,
and follows system changes. Pointer highlights use refs and animation frames;
reduced-motion, reduced-transparency, increased-contrast, and no-backdrop-filter
fallbacks keep the content available.

Browser tests mock subscription data; screenshot counts are fixtures, not claims
about the live network. Real node availability still requires `python collect.py`
in the deployment environment. HTTPS checks are connectivity evidence, not proof
that a third-party operator is trustworthy.
