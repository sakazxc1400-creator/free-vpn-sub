import React, { useRef } from "react";
import { Icon } from "./Primitives.jsx";
import { age, snapshotState } from "../data.js";
import { useParallax } from "../hooks/useEffects.js";

function NetworkArtwork() {
  return <svg className="network-art" viewBox="0 0 600 480" fill="none" aria-hidden="true">
    <defs><linearGradient id="route" x1="120" y1="120" x2="470" y2="360" gradientUnits="userSpaceOnUse"><stop stopColor="#54a5ff" /><stop offset="1" stopColor="#64c9bb" /></linearGradient></defs>
    <g className="art-grid" stroke="currentColor"><ellipse cx="300" cy="239" rx="205" ry="202" /><ellipse cx="300" cy="239" rx="120" ry="202" /><ellipse cx="300" cy="239" rx="43" ry="202" /><ellipse cx="300" cy="239" rx="205" ry="74" /><ellipse cx="300" cy="239" rx="205" ry="143" /><path d="M95 239h410M300 37v404" /></g>
    <g className="art-route" stroke="url(#route)" strokeWidth="2"><path pathLength="1" d="M165 157Q298 77 433 158" /><path pathLength="1" d="M165 157Q181 275 247 362" /><path pathLength="1" d="M247 362Q339 267 433 158" /><path pathLength="1" d="M433 158Q478 220 467 294" /></g>
    <g className="art-nodes">{[[165,157],[247,362],[433,158],[467,294]].map(([x,y]) => <g key={x}><circle cx={x} cy={y} r="15" className="node-halo" /><circle cx={x} cy={y} r="5" className="node-point" /></g>)}</g>
  </svg>;
}

export default function Hero({ network }) {
  const hero = useRef(null);
  useParallax(hero);
  const { stats, now } = network;
  const data = stats.data;
  const state = stats.status === "loading" && !data ? "Checking public data" : stats.status === "error" && !data ? "Public data unavailable" : snapshotState(data?.updated, now) === "fresh" ? age(data?.updated, now) : snapshotState(data?.updated, now) === "unknown" ? "Update time unavailable" : "Older snapshot — not a live check";
  return <section className="hero" aria-labelledby="hero-title" ref={hero}>
    <div className="hero-copy">
      <div className="eyebrow hero-eyebrow"><span className="pulse-dot" />OPEN SOURCE · COMMUNITY SERVERS</div>
      <h1 id="hero-title">The open internet.<br /><span>Within reach.</span></h1>
      <p className="hero-description">Free VPN configurations, collected from public sources and checked with real traffic. Copy a subscription into your own VPN client — no account, no paywall.</p>
      <div className="hero-actions"><a className="button primary glass" href="#connect">Get a subscription <Icon /></a><a className="button quiet" href="#network">See the real data <Icon name="arrow" size={18} /></a></div>
      <p className="hero-requirement"><Icon name="plus" size={15} /> A VPN client such as Hiddify is required. This website does not connect you by itself.</p>
    </div>
    <div className="hero-visual" aria-label="Illustration of a distributed network, not live telemetry">
      <div className="visual-halo" /><NetworkArtwork />
      <div className="glass-orbit glass"><Icon name="globe" size={20} /><div><strong>One subscription</strong><span>Six supported protocols</span></div></div>
      <div className="glass-snapshot glass"><span className={`status-dot ${stats.status === "ready" ? "" : "neutral"}`} /><div><strong>{data ? `${data.published} selected servers` : "Public network snapshot"}</strong><span>{state}</span></div></div>
      <div className="verification-note"><Icon name="shield" size={18} /><span>Real traffic, not just open ports.</span></div>
    </div>
  </section>;
}
