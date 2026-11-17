import React, { useMemo, useState } from "react";
import { RAW } from "../config.js";
import { age, snapshotState } from "../data.js";
import { CopyButton, Icon, SectionHeading } from "./Primitives.jsx";
import { useCountUp } from "../hooks/useEffects.js";

const regions = new Intl.DisplayNames(["en"], { type: "region" });
const number = (value) => typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-US") : "—";
export const countryName = (code) => /^[A-Z]{2}$/.test(code || "") && code !== "XX" ? regions.of(code) : "Unknown location";

function StatCard({ label, value, note, icon, unit }) {
  const animated = useCountUp(value);
  return <div className="stat-card"><div className="stat-title"><span>{label}</span><Icon name={icon} size={18} /></div><div className="stat-value">{number(animated)}{unit && animated != null && <span>{unit}</span>}</div><p>{note}</p></div>;
}

function Stats({ network }) {
  const { stats } = network;
  const data = stats.data;
  const items = [
    ["Traffic-tested servers", data?.published_full, "In the full working network", "globe"],
    ["Countries", data?.countries, "Across the published network", "external"],
    ["Best latency", data?.best_latency_ms, "Measured from the test runner", "refresh"],
    ["Consistent performers", data?.stable, `${data?.stable_runs ?? 6} successful checks in a row`, "shield"],
  ];
  return <div className="stats-grid">{items.map(([label, value, note, icon], index) => <StatCard key={label} label={label} value={value} note={note} icon={icon} unit={index === 2 ? "ms" : null} />)}</div>;
}

export default function Network({ network }) {
  const { stats: statsState, nodes: nodesState, now, retry, consistent } = network;
  const stats = statsState.data;
  const nodes = nodesState.data;
  const [search, setSearch] = useState("");
  const [protocol, setProtocol] = useState("");
  const [limit, setLimit] = useState(6);
  const protocols = useMemo(() => [...new Set(nodes.map((node) => node.proto))].sort(), [nodes]);
  const filtered = useMemo(() => nodes.filter((node) => (!protocol || node.proto === protocol) && `${node.cc} ${countryName(node.cc)} ${node.proto} ${node.addr}`.toLowerCase().includes(search.trim().toLowerCase())).sort((a, b) => (a.ms ?? Infinity) - (b.ms ?? Infinity)), [nodes, protocol, search]);
  const reset = () => { setSearch(""); setProtocol(""); setLimit(6); };
  const failed = statsState.status === "error" || nodesState.status === "error";
  const partial = statsState.status !== nodesState.status && (statsState.status === "error" || nodesState.status === "error");
  const state = snapshotState(stats?.updated, now);

  return <section className="section" id="network" aria-labelledby="network-title" data-reveal>
    <SectionHeading index="02" eyebrow="THE PUBLIC SNAPSHOT" title="Evidence, not promises.">Latency and availability come from the last automated check. They are not a prediction of your connection.</SectionHeading>
    <div className="snapshot-line" role="status"><span><i className={`status-dot ${state === "fresh" ? "" : "neutral"}`} />{statsState.status === "error" ? "Snapshot unavailable" : age(stats?.updated, now)}</span><span>{statsState.source && statsState.source === nodesState.source ? `Data from ${statsState.source}` : `${statsState.source ? `Stats: ${statsState.source}` : "Stats source unavailable"}${nodesState.source ? ` · Nodes: ${nodesState.source}` : ""}`}</span></div>
    <p className="data-note">Stats and nodes are independent responses; matching mirror names do not prove a shared snapshot generation.</p>
    {failed && <div className="error-banner" role="status"><Icon name="refresh" size={22} /><div><strong>{partial ? "Some network data is unavailable." : "Live data is taking a break."}</strong><span>{partial ? "Available data stays visible. The unavailable source is marked above." : "Subscription links still work. No demo data is substituted."}</span></div><button className="button secondary glass" onClick={retry}><Icon name="refresh" size={17} /> Retry</button></div>}
    {statsState.status === "ready" && nodesState.status === "ready" && !consistent && <div className="inline-notice" role="status">Stats and nodes came from different mirrors. They are shown independently and may represent different snapshot generations.</div>}
    {state === "stale" && <div className="inline-notice" role="status">This snapshot is older than 8 hours. Treat it as historical data, not a current availability check.</div>}
    {state === "future" && <div className="inline-notice" role="status">This snapshot has a future timestamp. Its freshness cannot be verified.</div>}
    <Stats network={network} />
    <div className="server-table"><div className="table-toolbar"><div><span className="eyebrow">THE EVERYDAY SELECTION</span><h3>Servers you can inspect</h3><p>{nodesState.status === "loading" && !nodes.length ? "Fetching the server list…" : nodesState.status === "error" && !nodes.length ? "Server list unavailable" : `${filtered.length} matching servers · sorted by latency`}</p></div><div className="table-filters"><label className="search-field"><Icon name="search" size={18} /><span className="sr-only">Search servers</span><input type="search" value={search} onChange={(event) => { setSearch(event.target.value); setLimit(6); }} placeholder="Country, protocol, or IP" /></label><label className="sr-only" htmlFor="protocol-filter">Filter by protocol</label><select id="protocol-filter" value={protocol} onChange={(event) => { setProtocol(event.target.value); setLimit(6); }}><option value="">All protocols</option>{protocols.map((value) => <option key={value}>{value}</option>)}</select></div></div>
      <div className="table-wrap"><table><caption className="sr-only">Everyday subscription servers ordered by latency</caption><thead><tr><th scope="col">Location</th><th scope="col">Protocol</th><th scope="col">Latency</th><th scope="col" className="hide-small">HTTPS check</th><th scope="col"><span className="sr-only">Copy server link</span></th></tr></thead><tbody>
        {nodesState.status === "loading" && !nodes.length ? Array.from({ length: 4 }, (_, i) => <tr key={i} className="skeleton-row" aria-hidden="true"><td colSpan={5}><span /></td></tr>) : filtered.slice(0, limit).map((node) => <tr key={node.url} className="server-row"><td><div className="location-cell"><span className="country-code">{/^[A-Z]{2}$/.test(node.cc) ? node.cc : "—"}</span><div><strong>{countryName(node.cc)}</strong><span className="server-address" title={node.addr}>{node.addr}</span></div></div></td><td><span className="protocol-tag">{node.proto}</span></td><td><span className="latency"><i className={node.ms !== null && node.ms < 300 ? "fast" : ""} />{number(node.ms)}{node.ms !== null && <small> ms</small>}</span></td><td className="hide-small"><span className={node.tls ? "verified-label" : "unverified-label"}><Icon name={node.tls ? "check" : "plus"} size={15} />{node.tls ? "Passed" : "Not verified"}</span></td><td><CopyButton value={node.url} className="icon-button glass" iconOnly label={`Copy ${countryName(node.cc)} ${node.proto} server`} /></td></tr>)}
      </tbody></table></div>
      {nodesState.status !== "loading" && !filtered.length && <div className="empty-state"><Icon name="search" size={28} /><h4>{nodesState.status === "error" ? "Server list unavailable" : "No servers found"}</h4><p>{nodesState.status === "error" ? "The list could not be loaded. Subscription links remain available." : nodes.length ? "Try another country, protocol, or a shorter search." : "The everyday selection is empty in this snapshot."}</p><button className="button secondary" onClick={nodesState.status === "error" ? retry : reset}>{nodesState.status === "error" ? "Retry loading" : "Reset filters"}</button></div>}
      <div className="table-footer"><span>{nodesState.source ? `Server list from ${nodesState.source}` : "Public data, independently inspectable."}</span>{filtered.length > limit ? <button className="text-link" onClick={() => setLimit((value) => value + 12)}>Show more servers <Icon name="plus" size={16} /></button> : <a className="text-link" href={RAW + "all-full.txt"} target="_blank" rel="noreferrer">View full list <Icon name="external" size={16} /></a>}</div>
    </div>
  </section>;
}
