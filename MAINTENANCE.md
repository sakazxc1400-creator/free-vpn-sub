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

`site/App.jsx` is the single-file React implementation: components, styles,
network requests, filters, clipboard behavior, and import links. `site/index.html`
provides the document metadata. `site/public/` contains the favicon and retired
service worker. `npm run build` replaces `docs/` with the deployable static site;
do not hand-edit generated files. Relative asset URLs work with the repository's
GitHub Pages subpath. Commit the rebuilt `docs/` alongside source changes when
Pages is configured to publish `main /docs`.

## Data flow

- `sources.txt` -> `collect.py`: source download, share-link parsing, deduplication,
  TCP/UDP prefiltering, history, selection, and output.
- `outbound.py` -> `probe.py`: protocol conversion and isolated sing-box batches.
- `geo.py`: geographic annotation and caching.
- `clashout.py`: Mihomo/Clash export.
- `notify.py`: optional Telegram reports.
- `mirror/worker.js`: allowlisted Cloudflare Worker mirror with bounded upstream
  requests and GET/HEAD/OPTIONS support.
- `site/App.jsx`: independent stats/node fetches with per-source timeouts,
  cancellation, validation, and fallback mirrors. No fabricated production data.

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
   a recoverable `.subscription-*-previous` backup. This is not a
   cross-process lock or a guarantee against a machine crash between renames.

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
- Mirror HEAD responses are bodyless, failed reads fall back, and abandoned service
  workers clean only the project's own cache prefix.

## Design direction

The requested UI/UX Pro Max skill was installed from
`nextlevelbuilder/ui-ux-pro-max-skill` and queried for Swiss typography, bento grids,
and React async UI. The implemented direction uses a light neutral canvas, graphite
type, one lime accent, asymmetric modular cards, and restrained motion. It includes
keyboard-accessible tabs, visible focus, reduced-motion support, mobile layouts,
and explicit loading/empty/error states.

Browser tests mock subscription data; screenshot counts are fixtures, not claims
about the live network. Real node availability still requires `python collect.py`
in the deployment environment. HTTPS checks are connectivity evidence, not proof
that a third-party operator is trustworthy.
