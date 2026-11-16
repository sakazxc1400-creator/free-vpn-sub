import React, { useLayoutEffect, useRef, useState } from "react";
import { MIRRORS, PLANS, PROTOCOLS, importUrl } from "../config.js";
import { CopyButton, Icon, SectionHeading } from "./Primitives.jsx";
import useGlassPointer from "../hooks/useEffects.js";

function number(value) { return typeof value === "number" ? value.toLocaleString("en-US") : "—"; }

export default function Subscription({ network }) {
  const [selected, setSelected] = useState(0);
  const [mirror, setMirror] = useState(0);
  const tablist = useRef(null);
  useGlassPointer(tablist);
  const plan = PLANS[selected];
  const url = MIRRORS[mirror][1] + plan.file;
  const clash = selected === 3;
  const stats = network.stats.data;
  const stableEmpty = selected === 1 && network.stats.status === "ready" && stats?.stable === 0;

  useLayoutEffect(() => {
    const list = tablist.current;
    const active = list?.querySelector('[aria-selected="true"]');
    if (!list || !active) return;
    list.style.setProperty("--tab-x", `${active.offsetLeft}px`);
    list.style.setProperty("--tab-width", `${active.offsetWidth}px`);
  }, [selected]);

  return <section className="section connect-section" id="connect" aria-labelledby="connect-title" data-reveal>
    <SectionHeading index="01" eyebrow="GET CONNECTED" title="Your link. Your client.">Choose a subscription and a reachable mirror. Your VPN client handles the connection.</SectionHeading>
    <div className="subscription-shell">
      <div className="plan-tabs glass" role="tablist" aria-label="Subscription type" ref={tablist}><span className="tab-indicator" aria-hidden="true" />{PLANS.map((item, index) => <button key={item.file} id={`tab-${index}`} role="tab" aria-selected={index === selected} aria-controls="subscription-panel" tabIndex={index === selected ? 0 : -1} onClick={() => setSelected(index)} onKeyDown={(event) => {
        const next = event.key === "ArrowRight" ? (index + 1) % PLANS.length : event.key === "ArrowLeft" ? (index + PLANS.length - 1) % PLANS.length : event.key === "Home" ? 0 : event.key === "End" ? PLANS.length - 1 : null;
        if (next !== null) { event.preventDefault(); setSelected(next); document.getElementById(`tab-${next}`)?.focus(); }
      }}>{item.name}{index === 0 && <span className="recommended">Start here</span>}</button>)}</div>
      <div className="plan-panel" id="subscription-panel" role="tabpanel" aria-labelledby={`tab-${selected}`} tabIndex={0} key={plan.file}>
        <div className="plan-copy"><span className="eyebrow">{plan.eyebrow}</span><h3>{plan.title}</h3><p>{plan.description}</p><span className="plan-count"><span className="status-dot" />{clash ? "HTTPS-verified selection" : network.stats.status === "ready" ? `${number(stats?.[plan.key])} servers in this snapshot` : "Server count unavailable"}</span></div>
        <div className="link-panel"><div className="link-label"><label htmlFor="subscription-link">Subscription URL</label><span>{clash ? "YAML" : "BASE64"}</span></div><textarea id="subscription-link" aria-label="Subscription URL" value={url} readOnly rows={3} onFocus={(event) => event.target.select()} spellCheck={false} />
          {stableEmpty && <p className="inline-notice" role="status">The stable list is empty in this snapshot. It will fill after six consecutive successful checks.</p>}
          <div className="link-actions"><CopyButton value={url} className="primary glass">Copy subscription</CopyButton><a className="button secondary glass" href={importUrl(plan, url)} title="Attempts to open your installed VPN client">Open in {clash ? "Clash" : "Hiddify"}<Icon name="external" size={18} /></a></div>
          <p className="launch-note">Opening the app link asks your browser to launch the client; a successful import cannot be confirmed here.</p>
          <div className="mirror-select"><label htmlFor="mirror">Can't reach GitHub? Try a mirror</label><select id="mirror" value={mirror} onChange={(event) => setMirror(Number(event.target.value))}>{MIRRORS.map(([name], index) => <option key={name} value={index}>{name}</option>)}</select></div>
          <p className="link-note">{plan.foot}{mirror === 1 && " jsDelivr may serve an older cached version."}</p>
        </div>
      </div>
    </div>
    <div className="protocol-strip"><span>WORKS ACROSS YOUR STACK</span><div>{PROTOCOLS.map((protocol) => <span key={protocol}>{protocol}</span>)}</div></div>
  </section>;
}
