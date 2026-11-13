import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";

const REPO = "sakazxc1400-creator/free-vpn-sub";
const GITHUB = `https://github.com/${REPO}`;
const RAW = `https://raw.githubusercontent.com/${REPO}/data/output/`;
const MIRRORS = [
  ["GitHub", RAW],
  ["jsDelivr", `https://cdn.jsdelivr.net/gh/${REPO}@data/output/`],
  ["gh-proxy", `https://gh-proxy.com/${RAW}`],
  ["ghproxy.net", `https://ghproxy.net/${RAW}`],
  ["githack", `https://raw.githack.com/${REPO}/data/output/`],
];
const PLANS = [
  { name: "Everyday", file: "sub.txt", key: "published", tag: "THE ESSENTIALS", title: "Your everyday connection.", description: "A curated selection of up to 200 traffic-tested servers. Balanced across countries, with HTTPS verification for every node.", foot: "For Hiddify, v2rayNG, and other subscription clients." },
  { name: "Stable", file: "sub-stable.txt", key: "stable", tag: "BUILT FOR CONSISTENCY", title: "A little more tried. And tested.", description: "Servers that passed at least six consecutive checks, with verified HTTPS. A smaller selection that has earned its place.", foot: "This list can be empty until enough checks have completed." },
  { name: "Full network", file: "sub-full.txt", key: "published_full", tag: "MORE PLACES TO CONNECT", title: "The whole working network.", description: "Every server that passed the traffic check, including nodes that failed HTTPS verification. Those nodes carry a warning in their name.", foot: "Use the everyday subscription for HTTPS-verified nodes only." },
  { name: "Clash / Mihomo", file: "clash.yaml", key: "published", tag: "READY FOR YOUR CLIENT", title: "Your network. In YAML.", description: "An auto-selection group, country groups, and HTTPS-verified nodes. A ready-to-import configuration for Mihomo-based clients.", foot: "Compatible with Clash Verge Rev, FlClash, and Mihomo." },
];
const PROTOCOLS = ["VLESS", "VMess", "Trojan", "Shadowsocks", "Hysteria2", "TUIC"];
const TON = "UQDj7y9AG8P_4oZ4KAnpRDfCulC-FsgnqSI_8xABobHvc1F3";
const COUNTRY_NAMES = new Intl.DisplayNames(["en"], { type: "region" });

function Icon({ name = "arrow", size = 20, ...props }) {
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
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.arrow}</svg>;
}

function Brand() {
  return <a className="brand" href="#" aria-label="Free VPN Sub home"><span className="brand-mark" aria-hidden="true"><i /><i /><i /><i /></span><span>freevpn<span className="brand-sub"> / sub</span></span></a>;
}

function number(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-US") : "—";
}

function timestamp(value) {
  return typeof value === "string" ? Date.parse(value.replace(" UTC", "Z").replace(" ", "T")) : NaN;
}

function age(value, now) {
  const time = timestamp(value);
  if (!Number.isFinite(time)) return "Update time unavailable";
  const minutes = Math.max(0, Math.floor((now - time) / 60000));
  if (!minutes) return "Updated just now";
  if (minutes < 60) return `Updated ${minutes}m ago`;
  if (minutes < 1440) return `Updated ${Math.floor(minutes / 60)}h ago`;
  return `Updated ${Math.floor(minutes / 1440)}d ago`;
}

function countryName(code) {
  return /^[A-Z]{2}$/.test(code || "") && code !== "XX" ? COUNTRY_NAMES.of(code) : "Unknown location";
}

function validStats(data) {
  return data && typeof data === "object" && !Array.isArray(data) && Number.isInteger(data.published)
    && data.published >= 0 && Number.isFinite(timestamp(data.updated))
    && ["published_full", "verified", "countries", "stable", "stable_runs", "best_latency_ms"]
      .every((key) => data[key] == null || (typeof data[key] === "number" && Number.isFinite(data[key]) && data[key] >= 0));
}

function validNode(node) {
  return node && typeof node.addr === "string" && typeof node.proto === "string"
    && typeof node.cc === "string" && (node.cc === "" || /^[A-Z]{2}$/.test(node.cc))
    && typeof node.tls === "boolean"
    && typeof node.url === "string" && /^(vless|vmess|trojan|ss|hysteria2|hy2|tuic):\/\//i.test(node.url)
    && (node.ms === null || (typeof node.ms === "number" && Number.isFinite(node.ms) && node.ms >= 0));
}

async function fetchData(file, validate, signal) {
  for (const [source, base] of MIRRORS) {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal.addEventListener("abort", abort, { once: true });
    const timer = setTimeout(abort, 5000);
    try {
      const response = await fetch(base + file, { signal: controller.signal, cache: "no-store" });
      if (!response.ok) continue;
      const data = await response.json();
      if (validate(data)) return { data, source };
    } catch (error) {
      if (signal.aborted) throw error;
    } finally {
      clearTimeout(timer);
      signal.removeEventListener("abort", abort);
    }
  }
  throw new Error("All data sources are unavailable");
}

function useNetwork() {
  const [stats, setStats] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [status, setStatus] = useState("loading");
  const [nodesStatus, setNodesStatus] = useState("loading");
  const [source, setSource] = useState("");
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setStatus("loading");
    setNodesStatus("loading");
    fetchData("stats.json", validStats, controller.signal).then(({ data, source }) => {
      if (controller.signal.aborted) return;
      setStats(data); setSource(source); setStatus("ready");
    }).catch(() => { if (!controller.signal.aborted) setStatus("error"); });
    fetchData("nodes.json", (data) => Array.isArray(data) && data.every(validNode), controller.signal)
      .then(({ data }) => {
        if (controller.signal.aborted) return;
        setNodes(data); setNodesStatus("ready");
      }).catch(() => { if (!controller.signal.aborted) setNodesStatus("error"); });
    return () => controller.abort();
  }, [revision]);
  return { stats, nodes, status, nodesStatus, source, now, retry: () => setRevision((value) => value + 1) };
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch { /* Use the legacy path when clipboard access is unavailable. */ }
  const area = document.createElement("textarea");
  area.value = text; area.style.cssText = "position:fixed;opacity:0;inset:0;pointer-events:none";
  document.body.append(area);
  const focused = document.activeElement;
  try { area.select(); return document.execCommand("copy"); } catch { return false; }
  finally { area.remove(); focused?.focus(); }
}

function CopyButton({ value, children = "Copy link", className = "", iconOnly = false, label = "Copy server link" }) {
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

function NetworkGlobe() {
  return <svg className="network-globe" viewBox="0 0 360 300" aria-hidden="true" fill="none">
    <g stroke="currentColor" strokeWidth=".8"><circle cx="190" cy="150" r="126" /><ellipse cx="190" cy="150" rx="86" ry="126" /><ellipse cx="190" cy="150" rx="37" ry="126" /><ellipse cx="190" cy="150" rx="126" ry="45" /><ellipse cx="190" cy="150" rx="126" ry="90" /><path d="M64 150h252M190 24v252" /></g>
    <g stroke="var(--accent)" strokeWidth="1.2" opacity=".8"><path d="M104 106Q175 44 254 106M104 106Q136 158 168 216M168 216Q188 132 254 106M254 106Q283 147 289 185" /></g>
    <g fill="var(--accent)">{[[104,106],[168,216],[254,106],[289,185]].map(([x,y]) => <React.Fragment key={x}><circle cx={x} cy={y} r="10" opacity=".12" /><circle cx={x} cy={y} r="3.5" /></React.Fragment>)}</g>
  </svg>;
}

function Hero({ network }) {
  const { stats, status, now } = network;
  const stale = stats && now - timestamp(stats.updated) > 8 * 3600000;
  const state = status === "loading" ? "Fetching network data" : status === "error" ? "Live data unavailable" : stale ? "Last snapshot is older than 8h" : "Latest network snapshot";
  return <section className="hero" aria-labelledby="hero-title">
    <div className="hero-copy">
      <div className="eyebrow"><span className="tiny-cross">+</span> OPEN INTERNET. SHARED BY EVERYONE.</div>
      <h1 id="hero-title">A freer internet.<br /><span>One simple link.</span></h1>
      <p className="hero-description">Free VPN servers, brought together.<br className="desktop-break" /> Checked for real traffic. Ready for your client.</p>
      <div className="hero-actions"><a className="button primary" href="#connect">Get connected <Icon /></a><a className="text-link" href="#network">Explore the network <Icon name="external" size={18} /></a></div>
      <div className="hero-proof"><span><Icon name="check" size={15} /> No account</span><span><Icon name="check" size={15} /> No paywall</span><span><Icon name="check" size={15} /> Open source</span></div>
    </div>
    <div className="hero-bento">
      <div className="network-card">
        <div className="card-top"><span className="eyebrow">THE COMMUNITY NETWORK</span><span className={`live-pill ${status !== "ready" || stale ? "muted" : ""}`}><i />{status === "ready" ? "SNAPSHOT" : status === "loading" ? "LOADING" : "OFFLINE"}</span></div>
        <NetworkGlobe />
        <div className="network-card-copy"><span className="mega-number">{number(stats?.countries)}<span> /</span></span><p>countries.<br />One open network.</p></div>
        <div className="card-bottom"><span>{state}</span><Icon name="globe" size={17} /></div>
      </div>
      <div className="mini-card"><Icon name="shield" /><div><strong className="mini-title">Checked, not guessed.</strong><p>Real traffic. Verified HTTPS.</p></div></div>
      <div className="mini-card accent-card"><span className="zero">0<span> / cost</span></span><div><strong className="mini-title">Free means free.</strong><p>From the community, for you.</p></div></div>
    </div>
  </section>;
}

function Subscription({ stats }) {
  const [selected, setSelected] = useState(0);
  const [mirror, setMirror] = useState(0);
  const plan = PLANS[selected];
  const url = MIRRORS[mirror][1] + plan.file;
  const clash = selected === 3;
  const importUrl = clash ? `clash://install-config?url=${encodeURIComponent(url)}&name=FreeVPNSub` : `hiddify://import/${url}#FreeVPNSub`;
  return <section className="section connect-section" id="connect" aria-labelledby="connect-title">
    <div className="section-heading"><div><div className="eyebrow section-index">01 / GET CONNECTED</div><h2 id="connect-title">Your next connection<br />starts here.</h2></div><p>Choose a subscription. Copy the link.<br />Let your VPN client do the rest.</p></div>
    <div className="subscription-card">
      <div className="plan-tabs" role="tablist" aria-label="Subscription type">{PLANS.map((item, index) => <button key={item.file} id={`tab-${index}`} role="tab" aria-selected={index === selected} aria-controls="subscription-panel" tabIndex={index === selected ? 0 : -1} onClick={() => setSelected(index)} onKeyDown={(event) => {
        const next = event.key === "ArrowRight" ? (index + 1) % PLANS.length : event.key === "ArrowLeft" ? (index + PLANS.length - 1) % PLANS.length : event.key === "Home" ? 0 : event.key === "End" ? PLANS.length - 1 : null;
        if (next !== null) { event.preventDefault(); setSelected(next); document.getElementById(`tab-${next}`)?.focus(); }
      }}>{item.name}{index === 0 && <span className="recommended">Recommended</span>}</button>)}</div>
      <div className="plan-panel" id="subscription-panel" role="tabpanel" aria-labelledby={`tab-${selected}`} tabIndex={0}>
        <div className="plan-copy"><span className="eyebrow">{plan.tag}</span><h3>{plan.title}</h3><p>{plan.description}</p><span className="plan-count"><span className="status-dot" />{clash ? "HTTPS-verified selection" : `${number(stats?.[plan.key])} servers in the latest snapshot`}</span></div>
        <div className="link-panel"><div className="link-label"><label htmlFor="subscription-link">SUBSCRIPTION URL</label><span>{clash ? "YAML" : "BASE64"}</span></div><textarea id="subscription-link" aria-label="Subscription URL" value={url} readOnly rows={3} onFocus={(event) => event.target.select()} spellCheck={false} />
          <div className="link-actions"><CopyButton value={url} className="primary">Copy subscription</CopyButton><a className="button secondary" href={importUrl}>Open in {clash ? "Clash" : "Hiddify"}<Icon name="external" size={18} /></a></div>
          <div className="mirror-select"><label htmlFor="mirror">Can't reach GitHub? Try a mirror</label><select id="mirror" value={mirror} onChange={(event) => setMirror(Number(event.target.value))}>{MIRRORS.map(([name], index) => <option key={name} value={index}>{name}</option>)}</select></div>
          <p className="link-note">{plan.foot}{mirror === 1 && " jsDelivr may serve an older cached version."}</p>
        </div>
      </div>
    </div>
    <div className="protocol-strip"><span>ONE LINK. YOUR PROTOCOL.</span><div>{PROTOCOLS.map((protocol) => <span key={protocol}>{protocol}</span>)}</div></div>
  </section>;
}

function Network({ network }) {
  const { stats, nodes, status, nodesStatus, source, now, retry } = network;
  const [search, setSearch] = useState("");
  const [protocol, setProtocol] = useState("");
  const [limit, setLimit] = useState(6);
  const protocols = useMemo(() => [...new Set(nodes.map((node) => node.proto))].sort(), [nodes]);
  const filtered = useMemo(() => nodes.filter((node) => (!protocol || node.proto === protocol) && `${node.cc} ${countryName(node.cc)} ${node.proto} ${node.addr}`.toLowerCase().includes(search.toLowerCase())).sort((a, b) => (a.ms ?? Infinity) - (b.ms ?? Infinity)), [nodes, protocol, search]);
  const reset = () => { setSearch(""); setProtocol(""); setLimit(6); };
  return <section className="section" id="network" aria-labelledby="network-title">
    <div className="section-heading"><div><div className="eyebrow section-index">02 / NOTHING TO HIDE</div><h2 id="network-title">A network you can see.</h2></div><div className="snapshot-status" role="status"><span className={`status-dot ${status !== "ready" ? "neutral-dot" : ""}`} />{status === "loading" ? "Loading live data…" : status === "error" ? "Snapshot unavailable" : age(stats?.updated, now)}</div></div>
    <div className="stats-grid">{[
      ["Traffic-tested servers", stats?.published_full, "Passing real internet traffic", "globe"],
      ["Countries", stats?.countries, "Across the published network", "external"],
      ["Best latency", stats?.best_latency_ms, "Measured from the test runner", "refresh"],
      ["Consistent performers", stats?.stable, `${stats?.stable_runs || 6} successful checks in a row`, "shield"],
    ].map(([label, value, note, icon], index) => <div className="stat-card" key={label}><div className="stat-title"><span>{label}</span><Icon name={icon} size={18} /></div><div className="stat-value">{number(value)}{index === 2 && value != null && <span>ms</span>}</div><p>{note}</p></div>)}</div>
    {(status === "error" || nodesStatus === "error") && <div className="error-banner" role="status"><div><strong>Live data is taking a break.</strong><span>Subscription links are still available above. Try a mirror if GitHub is blocked.</span></div><button className="button secondary" onClick={retry}><Icon name="refresh" size={17} /> Retry</button></div>}
    <div className="server-table"><div className="table-toolbar"><div><h3>Inside the everyday selection</h3><p>{nodesStatus === "loading" ? "Fetching the latest server list…" : `${filtered.length} matching servers · sorted by latency`}</p></div><div className="table-filters"><label className="search-field"><Icon name="search" size={18} /><span className="sr-only">Search servers</span><input type="search" value={search} onChange={(event) => { setSearch(event.target.value); setLimit(6); }} placeholder="Country, protocol, or IP" /></label><label className="sr-only" htmlFor="protocol-filter">Filter by protocol</label><select id="protocol-filter" value={protocol} onChange={(event) => { setProtocol(event.target.value); setLimit(6); }}><option value="">All protocols</option>{protocols.map((value) => <option key={value}>{value}</option>)}</select></div></div>
      <div className="table-wrap"><table><caption className="sr-only">Current subscription servers ordered by latency</caption><thead><tr><th scope="col">Location</th><th scope="col">Protocol</th><th scope="col">Latency</th><th scope="col" className="hide-small">HTTPS check</th><th scope="col"><span className="sr-only">Copy server link</span></th></tr></thead><tbody>
        {nodesStatus === "loading" && !nodes.length ? Array.from({ length: 4 }, (_, i) => <tr key={i} className="skeleton-row" aria-hidden="true"><td colSpan={5}><span /></td></tr>) : filtered.slice(0, limit).map((node) => <tr key={node.url}><td><div className="location-cell"><span className="country-code">{/^[A-Z]{2}$/.test(node.cc) ? node.cc : "—"}</span><div><strong>{countryName(node.cc)}</strong><span className="server-address">{node.addr}</span></div></div></td><td><span className="protocol-tag">{node.proto}</span></td><td><span className="latency"><i className={node.ms !== null && node.ms < 300 ? "fast" : ""} />{number(node.ms)}<small> ms</small></span></td><td className="hide-small"><span className={node.tls ? "verified-label" : "unverified-label"}><Icon name={node.tls ? "check" : "plus"} size={15} />{node.tls ? "Passed" : "Not verified"}</span></td><td><CopyButton value={node.url} className="icon-button" iconOnly label={`Copy ${countryName(node.cc)} ${node.proto} server`} /></td></tr>)}
      </tbody></table></div>
      {nodesStatus !== "loading" && !filtered.length && <div className="empty-state"><Icon name="search" size={28} /><h4>{nodesStatus === "error" ? "Server list unavailable" : "No servers found"}</h4><p>{nodesStatus === "error" ? "Try loading the network again." : "Try another country, protocol, or a shorter search."}</p><button className="button secondary" onClick={nodesStatus === "error" ? retry : reset}>{nodesStatus === "error" ? "Retry loading" : "Reset filters"}</button></div>}
      <div className="table-footer"><span>{source ? `Data from ${source}` : "Public data, independently inspectable."}</span>{filtered.length > limit ? <button className="text-link" onClick={() => setLimit((value) => value + 12)}>Show more servers <Icon name="plus" size={16} /></button> : <a className="text-link" href={RAW + "all-full.txt"} target="_blank" rel="noreferrer">View full list <Icon name="external" size={16} /></a>}</div>
    </div>
    <p className="data-note">Latency and availability reflect the last automated check, not your local connection. Public servers can change between updates.</p>
  </section>;
}

function Guide() {
  return <section className="section guide-section" id="how-it-works" aria-labelledby="guide-title"><div className="section-heading"><div><div className="eyebrow section-index">03 / LESS SETUP. MORE INTERNET.</div><h2 id="guide-title">Three steps. You're in.</h2></div><p>No registration form.<br />No complicated configuration.</p></div><div className="steps-grid">{[
    ["01", "Bring your favorite client.", "Install Hiddify on desktop or mobile, or v2rayNG on Android.", "Choose Hiddify", "https://github.com/hiddify/hiddify-app/releases", "globe"],
    ["02", "Add one simple link.", "Copy a subscription above. In your client, choose add subscription from URL.", "Get the subscription", "#connect", "link"],
    ["03", "Find your connection.", "Refresh your subscription, pick a server, and connect. Switch nodes if one stops responding.", "Browse the network", "#network", "arrow"],
  ].map(([n, title, text, cta, href, icon]) => <article className="step-card" key={n}><div className="step-top"><span>{n}</span><Icon name={icon} size={23} /></div><h3>{title}</h3><p>{text}</p><a className="text-link" href={href}>{cta}<Icon name="external" size={16} /></a></article>)}</div></section>;
}

function App() {
  const network = useNetwork();
  useEffect(() => {
    if ("serviceWorker" in navigator) navigator.serviceWorker.getRegistrations().then((list) => list.filter((r) => r.scope === new URL("./", location.href).href).forEach((r) => r.update().catch(() => {}))).catch(() => {});
  }, []);
  return <><style>{styles}</style><a className="skip-link" href="#main-content">Skip to content</a><div className="page-shell"><header className="header"><Brand /><nav aria-label="Main navigation"><a href="#network">Network</a><a href="#how-it-works">How it works</a><a className="github-link" href={GITHUB} target="_blank" rel="noreferrer"><Icon name="code" size={17} /> GitHub <Icon name="external" size={15} /></a></nav><a className="button nav-cta" href="#connect">Get connected <Icon name="external" size={16} /></a></header>
    <main id="main-content"><Hero network={network} /><div className="intro-line"><span>LESS FRICTION. MORE FREEDOM.</span><span>A small open-source project for a more open internet.<Icon name="external" size={18} /></span></div><Subscription stats={network.stats} /><Network network={network} /><Guide />
      <section className="principles-grid" aria-label="Project principles"><article className="transparency-card"><span className="eyebrow">OPEN CODE. OPEN CONVERSATION.</span><h2>Built in public.<br />Better together.</h2><p>Every source, every check, every line of code is there to inspect. Found a broken source or have an improvement? Make it part of the project.</p><a className="button dark-button" href={GITHUB} target="_blank" rel="noreferrer">Explore on GitHub <Icon name="external" size={18} /></a><div className="license-label"><Icon name="code" size={16} /> MIT licensed · Community maintained</div></article><article className="honesty-card"><Icon name="shield" size={26} /><h3>Open access.<br />Honest expectations.</h3><p>These servers are operated by third parties. HTTPS checks are a useful signal, not a guarantee of privacy or anonymity.</p><p>Avoid using public proxies for sensitive accounts. For a connection you control, use your own server.</p><a className="text-link" href={`${GITHUB}#readme`} target="_blank" rel="noreferrer">Read the project notes <Icon name="external" size={16} /></a></article></section>
      <section className="support-section"><div><span className="eyebrow">KEEP GOOD THINGS OPEN.</span><h2>Free to use.<br />Worth keeping around.</h2><p>A star, a better source, or a contribution goes a long way.</p><details className="ton-support"><summary>Support with TON <Icon name="plus" size={16} /></summary><div className="ton-panel"><img src="./assets/ton-qr.png" alt="TON donation wallet QR code" width="112" height="112" loading="lazy" /><div><code>{TON}</code><CopyButton value={TON} className="secondary">Copy TON address</CopyButton></div></div></details></div><a className="button secondary" href={`${GITHUB}/issues`} target="_blank" rel="noreferrer">Share an improvement <Icon name="external" /></a></section>
    </main><footer className="footer"><Brand /><span>An open network. A shared effort.</span><div><a href={`${GITHUB}/blob/main/LICENSE`}>MIT License</a><a href="https://www.donationalerts.com/r/saka12312312" target="_blank" rel="noreferrer">Support the project <Icon name="external" size={14} /></a></div></footer></div></>;
}

const styles = `
.mini-title{font-size:13px;font-weight:600;letter-spacing:-.2px;line-height:1.4}
.ton-support{margin-top:15px;max-width:470px}.ton-support summary{display:flex;align-items:center;gap:12px;cursor:pointer;font-size:11px;min-height:44px;list-style:none;width:fit-content}.ton-support summary::-webkit-details-marker{display:none}.ton-support summary:focus-visible{outline:3px solid #63842f;outline-offset:4px}.ton-panel{display:flex;align-items:center;gap:18px;margin-top:10px;padding:16px;border:1px solid var(--line);border-radius:12px;background:var(--surface)}.ton-panel img{border-radius:6px;flex-shrink:0}.ton-panel>div{min-width:0}.ton-panel code{font-size:10px;overflow-wrap:anywhere;line-height:1.8;display:block}.ton-panel .button{font-size:10px;margin-top:10px;padding:10px;white-space:normal}
:root{--bg:#f7f8f5;--surface:#fff;--text:#191d19;--muted:#626960;--line:#e0e4da;--accent:#d3f88d;--accent-strong:#4b6a24;--dark:#20261f;--radius:20px;--font:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;font-family:var(--font);font-synthesis:none;color:var(--text);background:var(--bg);font-weight:400}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:32px}body{margin:0}button,input,select,textarea{font:inherit}button,a,select{touch-action:manipulation}button,a{ -webkit-tap-highlight-color:transparent}button,select{cursor:pointer}button{color:inherit}a{color:inherit;text-decoration:none}button:disabled{cursor:wait}a,button{transition:background .18s,color .18s,border-color .18s}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,[tabindex="0"]:focus-visible{outline:3px solid #63842f;outline-offset:4px}::selection{background:var(--accent);color:var(--text)}h1,h2,h3,h4,p{margin:0}h1,h2,h3{text-wrap:balance}p{text-wrap:pretty}svg{flex-shrink:0}.page-shell{max-width:1280px;margin:0 auto;padding:0 48px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}.skip-link{position:fixed;top:12px;left:12px;z-index:30;background:var(--dark);color:white;padding:14px;transform:translateY(-150%)}.skip-link:focus{transform:translateY(0)}
.header{height:100px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);gap:24px}.brand{display:inline-flex;align-items:center;gap:11px;font-size:22px;letter-spacing:-1px;font-weight:700;min-height:44px;white-space:nowrap}.brand-sub{font-weight:400;color:var(--muted)}.brand-mark{width:28px;height:28px;display:grid;grid-template-columns:1fr 1fr;gap:3px}.brand-mark i{background:var(--text);border-radius:1px}.brand-mark i:last-child{background:#9dc958;border-radius:1px 1px 9px 1px}.header nav{display:flex;align-items:center;gap:30px;font-size:13px;font-weight:500}.header nav a{display:flex;align-items:center;gap:8px;min-height:44px}.header nav a:hover,.text-link:hover{color:var(--accent-strong)}.button{display:inline-flex;justify-content:center;align-items:center;gap:10px;border:1px solid transparent;border-radius:8px;padding:14px 20px;min-height:48px;font-size:13px;font-weight:600;line-height:1.3;white-space:nowrap}.primary{background:var(--accent);color:#213111}.primary:hover{background:#c2ec75}.secondary{border-color:var(--line);background:var(--surface)}.secondary:hover{background:#f0f3ea;border-color:#b9c2ae}.nav-cta{border-color:#cfd5c8;background:transparent;min-height:42px;padding:11px 15px;font-size:12px}.nav-cta:hover{background:var(--accent);border-color:var(--accent)}.dark-button{background:var(--text);color:white}.dark-button:hover{background:#3e4937}.text-link{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:550;min-height:44px;background:none;border:0;padding:0}.eyebrow{font-family:var(--font);font-size:10px;line-height:1.5;font-weight:600;letter-spacing:1.5px}.tiny-cross{font-size:19px;font-weight:400;vertical-align:-1px;margin-right:8px}.hero{display:grid;grid-template-columns:1.2fr 1fr;gap:54px;align-items:center;padding:80px 0 64px}.hero-copy>.eyebrow{margin-bottom:25px;color:var(--muted)}h1{font-size:clamp(46px,5.3vw,72px);font-weight:550;line-height:1.055;letter-spacing:-4px;margin:0 -20px 25px 0}h1>span{color:#777e71}.hero-description{font-size:16px;line-height:1.7;color:var(--muted);max-width:410px}.hero-actions{display:flex;align-items:center;gap:24px;margin-top:30px}.hero-actions .primary{padding:16px 22px}.hero-proof{display:flex;gap:19px;margin-top:29px;flex-wrap:wrap}.hero-proof>span{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted)}.hero-proof svg{color:var(--accent-strong)}.hero-bento{display:grid;grid-template-columns:1fr 1fr;gap:14px}.network-card{grid-column:1/-1;background:var(--dark);color:#f6f8f0;min-height:288px;border-radius:var(--radius);padding:24px;position:relative;overflow:hidden;display:flex;flex-direction:column}.card-top{display:flex;align-items:center;justify-content:space-between;gap:8px;z-index:1}.card-top .eyebrow{color:#c4cabe;font-size:9px;letter-spacing:1.1px}.live-pill{display:inline-flex;align-items:center;gap:5px;background:#35432c;color:#d3f88d;border:1px solid #4a5e38;border-radius:30px;padding:5px 7px;font-size:8px;letter-spacing:.7px}.live-pill i,.status-dot{width:6px;height:6px;border-radius:50%;background:#80ab47;display:inline-block;flex-shrink:0}.live-pill.muted{color:#d4d9ce;background:#333c30;border-color:#515c4a}.live-pill.muted i,.neutral-dot{background:#8a9282}.network-globe{position:absolute;width:288px;height:248px;right:-30px;top:42px;color:#78856d;opacity:.6}.network-card-copy{position:relative;z-index:1;margin:27px 0 25px}.mega-number{font-size:64px;line-height:1;letter-spacing:-4px}.mega-number>span{font-size:32px;font-weight:300;color:#7e8a72}.network-card-copy p{font-size:18px;line-height:1.3;letter-spacing:-.4px;margin-top:10px}.card-bottom{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid #424b3b;padding-top:15px;margin-top:auto;font-size:10px;color:#c3cbbb;z-index:1}.mini-card{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);padding:23px 20px;min-height:146px;display:flex;flex-direction:column;justify-content:space-between;gap:23px}.mini-card>svg{color:#56664a}.mini-card h3{font-size:13px;font-weight:600;letter-spacing:-.2px}.mini-card p{font-size:10px;color:var(--muted);margin-top:6px;line-height:1.5}.accent-card{background:#eaf1df;border-color:#e1e8d6}.zero{font-size:29px;line-height:1;letter-spacing:-1px}.zero>span{font-size:11px;letter-spacing:0;color:#5d6953;margin-left:4px}.intro-line{display:flex;justify-content:space-between;gap:24px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:22px 0;color:var(--muted);font-size:11px}.intro-line>span:first-child{font-size:9px;letter-spacing:1.5px;font-weight:600}.intro-line>span:last-child{display:flex;align-items:center;gap:26px}
.section{padding-top:92px;scroll-margin-top:32px}.section-heading{display:flex;justify-content:space-between;align-items:flex-end;gap:30px;margin-bottom:30px}.section-index{color:var(--muted);margin-bottom:13px}.section-heading h2{font-size:36px;line-height:1.14;font-weight:500;letter-spacing:-1.6px}.section-heading>p{color:var(--muted);font-size:13px;line-height:1.7;padding-bottom:3px}.subscription-card{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);overflow:hidden}.plan-tabs{display:flex;gap:5px;padding:9px;border-bottom:1px solid var(--line);background:#f0f2ed}.plan-tabs button{flex:1;min-height:48px;padding:12px;border:0;border-radius:9px;background:transparent;color:var(--muted);font-size:12px;font-weight:500;display:flex;align-items:center;justify-content:center;gap:10px}.plan-tabs button[aria-selected="true"]{background:var(--surface);color:var(--text);box-shadow:0 1px 4px #1720190a}.plan-tabs button:hover{color:var(--text);background:#fafbf8}.recommended{font-size:8px;font-weight:600;padding:4px 6px;border-radius:4px;background:#e9f3dc;color:#3d591d}.plan-panel{display:grid;grid-template-columns:1fr 1.15fr;gap:62px;padding:40px}.plan-copy>.eyebrow{color:var(--accent-strong);font-size:9px}.plan-copy h3{font-size:26px;font-weight:500;letter-spacing:-.9px;line-height:1.2;margin-top:17px;max-width:310px;min-height:63px}.plan-copy>p{font-size:13px;line-height:1.85;color:var(--muted);margin-top:16px;max-width:350px;min-height:73px}.plan-count{display:flex;align-items:center;gap:7px;font-size:10px;margin-top:24px;color:#4e5d42}.link-label{display:flex;justify-content:space-between;align-items:center;font-size:9px;letter-spacing:1px;color:var(--muted);margin-bottom:12px}.link-label span{font-size:8px;border:1px solid var(--line);border-radius:4px;padding:4px 6px}.link-panel textarea{width:100%;resize:none;border:1px solid #d8ddd1;border-radius:8px;background:#f6f7f3;padding:16px;color:#45523b;line-height:1.8;font-size:11px;font-family:"SFMono-Regular",Consolas,monospace;overflow-wrap:anywhere;height:91px}.link-actions{display:flex;gap:9px;margin-top:12px}.link-actions .button{flex:1;padding:13px 10px;font-size:11px}.mirror-select{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:16px;font-size:10px;color:var(--muted)}select{min-height:40px;border:1px solid var(--line);border-radius:6px;padding:8px 29px 8px 11px;background-color:var(--surface);color:var(--text);font-size:11px;max-width:100%}.mirror-select select{min-height:34px;font-size:10px;border-color:transparent;padding-right:20px}.link-note{font-size:9px;line-height:1.7;color:var(--muted);margin-top:9px;min-height:30px}.protocol-strip{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:24px 6px 0}.protocol-strip>span{font-size:8px;letter-spacing:1.3px;color:var(--muted);font-weight:600}.protocol-strip>div{display:flex;gap:30px;flex-wrap:wrap}.protocol-strip>div span{font-size:12px;font-weight:550;color:#626c58;letter-spacing:-.3px}
.snapshot-status{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted);padding-bottom:4px}.stats-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:22px}.stat-card{border:1px solid var(--line);border-radius:15px;background:var(--surface);padding:22px}.stat-title{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:10px;color:var(--muted)}.stat-title svg{color:#748365}.stat-value{font-size:39px;line-height:1.1;letter-spacing:-1.8px;margin-top:24px;font-weight:500;font-variant-numeric:tabular-nums}.stat-value>span{font-size:17px;color:var(--muted);margin-left:4px;letter-spacing:-.3px;font-weight:400}.stat-card>p{font-size:9px;color:var(--muted);margin-top:10px;line-height:1.5}.server-table{background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:hidden}.table-toolbar{padding:25px 26px;display:flex;align-items:center;justify-content:space-between;gap:20px}.table-toolbar h3{font-size:14px;letter-spacing:-.3px;font-weight:550}.table-toolbar p{font-size:10px;color:var(--muted);margin-top:7px}.table-filters{display:flex;gap:10px}.search-field{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:7px;padding:0 10px;color:var(--muted);max-width:240px}.search-field input{width:100%;min-width:0;border:none;background:transparent;height:40px;font-size:11px;color:var(--text)}.search-field input::placeholder{color:var(--muted)}.search-field:focus-within{outline:2px solid #63842f;outline-offset:2px}.search-field input:focus-visible{outline:none}table{width:100%;border-collapse:collapse;text-align:left;table-layout:fixed}th{font-size:9px;text-transform:uppercase;font-weight:500;letter-spacing:.7px;background:#f7f8f5;color:var(--muted);padding:13px 25px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}th:first-child{width:37%}th:nth-child(2){width:20%}th:nth-child(3){width:17%}th:nth-child(4){width:18%}th:last-child{width:8%;padding:13px 0}td{border-bottom:1px solid #edf0e8;padding:15px 25px;font-size:11px;height:73px}td:last-child{padding:0 10px}tr:last-child td{border-bottom:none}.location-cell{display:flex;align-items:center;gap:12px}.country-code{display:flex;align-items:center;justify-content:center;background:#f0f3eb;border:1px solid #e1e7d9;flex-shrink:0;width:33px;height:29px;border-radius:5px;font-size:9px;font-weight:600;color:#556847}.location-cell strong{font-size:11px;font-weight:500}.server-address{display:block;color:var(--muted);font-family:Consolas,monospace;font-size:9px;margin-top:5px;overflow-wrap:anywhere}.protocol-tag{display:inline-block;padding:5px 7px;border-radius:4px;background:#f3f4f0;color:#58624e;font-size:9px;max-width:100%;overflow-wrap:anywhere}.latency{font-variant-numeric:tabular-nums;white-space:nowrap}.latency>i{display:inline-block;width:5px;height:5px;border-radius:50%;background:#949b8b;margin-right:7px}.latency>i.fast{background:#6d942f}.latency small{color:var(--muted);font-size:9px}.verified-label,.unverified-label{display:flex;align-items:center;gap:5px;font-size:10px;white-space:nowrap;color:#517328}.unverified-label{color:#86552f}.icon-button{background:transparent;min-height:44px;width:44px;padding:10px;border-radius:6px;color:#606d53}.icon-button:hover{background:#eff5e7}.copied{background:#e7f3d7!important;color:#34521a}.table-footer{border-top:1px solid var(--line);padding:12px 26px;display:flex;align-items:center;justify-content:space-between;gap:14px;color:var(--muted);font-size:9px}.table-footer .text-link{font-size:10px}.data-note{font-size:10px;line-height:1.7;color:var(--muted);margin-top:14px}.skeleton-row td{height:73px}.skeleton-row span{display:block;width:70%;height:14px;border-radius:4px;background:#eef1e8}.empty-state{padding:40px 20px;text-align:center;color:var(--muted)}.empty-state h4{color:var(--text);font-size:16px;margin-top:15px}.empty-state p{font-size:12px;margin:10px 0 18px}.error-banner{display:flex;align-items:center;justify-content:space-between;gap:20px;background:#f4eddb;border:1px solid #dcd0b1;border-radius:12px;padding:20px;margin-bottom:22px}.error-banner strong{display:block;font-size:13px;margin-bottom:7px}.error-banner span{font-size:11px;line-height:1.5;color:#6d5b32}
.steps-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:30px}.step-card{padding:24px 0 0;border-top:1px solid #bfc9b4;display:flex;flex-direction:column}.step-top{display:flex;align-items:center;justify-content:space-between;color:var(--muted);font-size:11px}.step-top>svg{color:#6f805f}.step-card h3{font-size:19px;line-height:1.35;font-weight:500;letter-spacing:-.6px;margin-top:29px}.step-card>p{font-size:12px;line-height:1.85;color:var(--muted);margin-top:11px;margin-bottom:22px;max-width:280px}.step-card .text-link{font-size:11px;margin-top:auto}.principles-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:18px;margin-top:90px}.transparency-card{border-radius:var(--radius);background:#e9efdf;padding:40px;position:relative}.transparency-card>.eyebrow{color:#556443;font-size:9px}.transparency-card h2{font-size:36px;font-weight:500;line-height:1.1;letter-spacing:-1.5px;margin-top:19px}.transparency-card p{font-size:12px;line-height:1.9;max-width:360px;color:#56614c;margin-top:20px}.transparency-card .button{margin-top:24px;font-size:11px}.license-label{display:flex;align-items:center;gap:7px;margin-top:25px;font-size:9px;color:#5e6a52}.honesty-card{border-radius:var(--radius);background:var(--surface);border:1px solid var(--line);padding:36px;display:flex;flex-direction:column;align-items:flex-start}.honesty-card>svg{color:#596b48}.honesty-card h3{font-size:23px;font-weight:500;line-height:1.25;letter-spacing:-.6px;margin-top:21px}.honesty-card p{font-size:11px;line-height:1.95;color:var(--muted);margin-top:18px}.honesty-card .text-link{margin-top:24px;font-size:11px}.support-section{display:flex;align-items:center;justify-content:space-between;gap:30px;padding:85px 0 75px}.support-section .eyebrow{color:var(--muted);font-size:9px}.support-section h2{font-size:39px;font-weight:500;line-height:1.1;letter-spacing:-1.6px;margin-top:17px}.support-section p{font-size:12px;color:var(--muted);margin-top:18px}.support-section .button{font-size:11px}.footer{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:24px 0 33px;border-top:1px solid var(--line)}.footer .brand{font-size:17px;gap:8px}.footer .brand-mark{width:23px;height:23px}.footer>span{font-size:10px;color:var(--muted)}.footer>div{display:flex;align-items:center;gap:24px}.footer>div a{display:flex;align-items:center;gap:5px;font-size:10px;min-height:44px;color:var(--muted)}
@media(min-width:1440px){.hero{gap:64px}h1{font-size:76px}.hero-bento{gap:16px}.network-card{min-height:308px}.network-globe{width:310px;height:265px}.mini-card{min-height:150px}}
@media(max-width:1100px){.page-shell{padding:0 32px}.hero{gap:30px;padding-top:62px}h1{font-size:57px;letter-spacing:-3px}.hero-actions{gap:16px}.hero-actions .text-link{font-size:11px}.hero-proof{gap:12px}.hero-proof>span{font-size:10px}.mini-card{padding:20px 16px}.mini-card h3{font-size:12px}.plan-panel{gap:32px;padding:32px}.link-actions{flex-direction:column}.link-actions .button{min-height:43px}.plan-copy h3{min-height:0}.plan-tabs button{gap:5px}.recommended{font-size:7px}.table-toolbar{align-items:flex-start}.table-filters{flex-direction:column}.table-filters select{min-height:34px}.table-toolbar{padding:20px}.stat-card{padding:18px}.stat-title{font-size:9px}.stat-title svg{width:15px}.protocol-strip>div{gap:18px}th,td{padding-left:20px;padding-right:16px}.network-globe{right:-60px}.card-top .eyebrow{font-size:8px}.card-top{gap:4px}.live-pill{font-size:7px}}
@media(max-width:800px){.page-shell{padding:0 24px}.header{height:80px}.header nav{gap:20px}.header .nav-cta{display:none}.hero{grid-template-columns:1fr;gap:38px;padding:56px 0 40px}.hero-copy{max-width:600px}h1{font-size:68px;letter-spacing:-3.5px;margin-right:0}.hero-description{font-size:16px}.hero-actions .text-link{font-size:13px}.hero-bento{grid-template-columns:1.4fr 1fr;grid-template-rows:1fr 1fr}.network-card{grid-column:auto;grid-row:1/3;min-height:300px}.mini-card{min-height:0;gap:16px}.network-globe{right:-55px}.section{padding-top:66px}.section-heading h2{font-size:32px}.section-heading>p{font-size:12px}.plan-panel{grid-template-columns:1fr;gap:30px}.plan-copy h3{max-width:none;margin-top:12px}.plan-copy>p{max-width:520px;min-height:0}.plan-count{margin-top:16px}.link-actions{flex-direction:row}.link-panel textarea{height:83px}.plan-tabs{gap:2px}.plan-tabs button{font-size:11px;flex-wrap:wrap;gap:4px}.recommended{font-size:7px}.protocol-strip{align-items:flex-start;gap:22px}.protocol-strip>div{gap:12px 20px;justify-content:flex-end}.protocol-strip>span{min-width:100px;max-width:120px;line-height:1.8}.stats-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.stat-card{padding:22px}.stat-title{font-size:11px}.stat-card>p{font-size:10px}.stat-value{margin-top:18px}.table-toolbar{flex-direction:column;gap:18px}.table-filters{flex-direction:row;width:100%}.search-field{max-width:none;flex:1}.steps-grid{gap:22px}.step-card h3{font-size:17px}.step-card>p{font-size:11px}.principles-grid{grid-template-columns:1fr 1fr;margin-top:62px;gap:14px}.transparency-card{padding:28px}.transparency-card h2{font-size:32px}.honesty-card{padding:28px}.honesty-card h3{font-size:21px}.intro-line>span:last-child{font-size:10px;gap:12px}.intro-line>span:first-child{font-size:8px}.support-section{padding:66px 0}.support-section h2{font-size:34px}.footer{flex-wrap:wrap;gap:15px}.footer>span{margin-left:auto}.footer>div{width:100%;justify-content:space-between;gap:12px}}
@media(max-width:520px){.page-shell{padding:0 20px}.header{height:73px;gap:12px}.brand{font-size:20px}.brand-mark{width:25px;height:25px}.header nav>a:not(.github-link){display:none}.header nav{gap:0}.github-link{font-size:11px}.hero{padding-top:44px;gap:32px}.hero-copy>.eyebrow{font-size:8px;letter-spacing:1.2px;margin-bottom:22px}h1{font-size:clamp(42px,11.8vw,60px);letter-spacing:-2.6px;line-height:1.08;margin-bottom:22px}.hero-description{font-size:14px;line-height:1.8}.hero-actions{gap:16px;flex-wrap:wrap;margin-top:24px}.hero-actions .primary{font-size:12px;padding:15px 16px}.hero-actions .text-link{font-size:11px;gap:7px}.hero-proof{margin-top:22px;gap:14px}.hero-proof>span{font-size:9px;gap:4px}.hero-bento{grid-template-columns:1fr 1fr;grid-template-rows:auto auto;gap:10px}.network-card{grid-column:1/-1;grid-row:auto;min-height:280px;padding:23px}.network-globe{right:-5px;top:40px;width:260px;height:230px}.network-card-copy{margin-top:25px}.card-top .eyebrow{font-size:8px}.live-pill{font-size:7px}.mini-card{min-height:141px;border-radius:16px;padding:20px 16px;gap:20px}.mini-card h3{font-size:11px}.mini-card p{font-size:9px}.intro-line{padding:18px 0}.intro-line>span:first-child{display:none}.intro-line>span:last-child{justify-content:space-between;width:100%;font-size:10px;line-height:1.6}.section{padding-top:56px}.section-heading{flex-direction:column;align-items:flex-start;gap:16px;margin-bottom:24px}.section-index{font-size:8px;letter-spacing:1.3px;margin-bottom:12px}.section-heading h2{font-size:30px;letter-spacing:-1.2px}.section-heading>p{font-size:12px}.plan-tabs{display:grid;grid-template-columns:1fr 1fr;padding:7px;gap:5px}.plan-tabs button{font-size:11px;min-height:42px}.recommended{font-size:7px}.plan-panel{padding:25px 20px;gap:25px}.plan-copy h3{font-size:24px}.plan-copy>p{font-size:12px;line-height:1.85}.plan-copy>.eyebrow{font-size:8px}.link-label{font-size:8px}.link-panel textarea{font-size:10px;height:102px}.link-actions{flex-direction:column}.link-actions .button{font-size:12px;min-height:46px}.mirror-select{font-size:9px;gap:5px;flex-wrap:wrap}.mirror-select select{font-size:10px}.link-note{font-size:9px}.protocol-strip{padding:20px 0 0;flex-direction:column;gap:12px}.protocol-strip>span{max-width:none;font-size:8px}.protocol-strip>div{justify-content:flex-start;gap:14px 21px}.protocol-strip>div span{font-size:11px}.stats-grid{gap:10px}.stat-card{padding:17px 15px}.stat-title{font-size:9px;align-items:flex-start;gap:8px;line-height:1.5}.stat-title svg{width:14px}.stat-value{font-size:33px;margin-top:20px}.stat-card>p{font-size:9px}.stat-value>span{font-size:14px}.snapshot-status{font-size:10px}.table-toolbar{padding:20px 16px}.table-toolbar h3{font-size:13px}.table-toolbar p{font-size:9px}.table-filters{gap:7px;flex-wrap:wrap}.search-field{flex-basis:100%;height:43px}.table-filters select{flex:1;height:40px}.hide-small{display:none}th{font-size:8px;padding:12px 10px}th:first-child{width:44%;padding-left:16px}th:nth-child(2){width:23%}th:nth-child(3){width:20%}th:last-child{width:13%}td{padding:14px 8px;font-size:10px}td:first-child{padding-left:16px}td:last-child{padding:0}.location-cell{gap:8px}.country-code{width:25px;height:25px;font-size:8px}.location-cell strong{font-size:10px}.server-address{font-size:8px;max-width:110px;line-height:1.5}.protocol-tag{font-size:8px;padding:5px}.latency{font-size:10px}.latency>i{display:none}.latency small{font-size:8px}.icon-button{width:40px;min-width:0;padding:9px}.icon-button svg{width:16px}.table-footer{padding:12px 16px;font-size:8px;gap:8px}.table-footer .text-link{font-size:9px;gap:4px}.data-note{font-size:9px;line-height:1.8}.error-banner{padding:17px;flex-direction:column;align-items:flex-start;gap:14px}.error-banner span{font-size:10px}.error-banner .button{font-size:11px}.steps-grid{grid-template-columns:1fr;gap:24px}.step-card{padding-top:22px}.step-top{font-size:11px}.step-card h3{margin-top:22px;font-size:21px}.step-card>p{font-size:12px;max-width:none;margin-bottom:12px}.step-card .text-link{font-size:11px}.principles-grid{grid-template-columns:1fr;gap:15px;margin-top:52px}.transparency-card{padding:30px 26px}.transparency-card h2{font-size:35px}.transparency-card p{font-size:12px}.honesty-card{padding:30px 26px}.honesty-card h3{font-size:26px}.honesty-card p{font-size:12px}.support-section{align-items:flex-start;flex-direction:column;padding:58px 0 44px;gap:24px}.support-section h2{font-size:34px}.support-section p{font-size:12px;line-height:1.8}.support-section .button{font-size:12px}.footer{padding:22px 0;gap:12px}.footer .brand{font-size:17px}.footer>span{font-size:8px;max-width:115px;text-align:right;line-height:1.8}.footer>div a{font-size:9px}.footer>div{gap:12px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*::before,*::after{animation:none!important;transition:none!important}}
`;

createRoot(document.getElementById("root")).render(<App />);
