import React from "react";
import { CopyButton, Icon, SectionHeading } from "./Primitives.jsx";
import { DONATION_URL, GITHUB, TON } from "../config.js";

export function Guide() {
  return <section className="section guide-section" id="how-it-works" aria-labelledby="guide-title" data-reveal><SectionHeading index="03" eyebrow="FROM LINK TO CONNECTION" title="Three steps. No account.">The subscription is a list of configurations. You still need a compatible VPN client installed.</SectionHeading><div className="steps-grid">{[
    ["01", "Install your client.", "Choose Hiddify on desktop or mobile, v2rayNG on Android, or a Mihomo-based client for the YAML subscription.", "Get Hiddify", "https://github.com/hiddify/hiddify-app/releases", "globe"],
    ["02", "Add the subscription.", "Copy one link above. In your client, choose the option to add a subscription from a URL.", "Choose a link", "#connect", "link"],
    ["03", "Choose and connect.", "Refresh the profile, select a server, and connect. Switch nodes if one stops responding between checks.", "Inspect the nodes", "#network", "arrow"],
  ].map(([n, title, text, cta, href, icon]) => <article className="step-card" key={n}><div className="step-top"><span>{n}</span><Icon name={icon} size={23} /></div><h3>{title}</h3><p>{text}</p><a className="text-link" href={href}>{cta}<Icon name="external" size={16} /></a></article>)}</div></section>;
}

export function Principles() {
  return <section className="principles-grid section" aria-label="Project principles" data-reveal><article className="transparency-card"><span className="eyebrow">BUILT IN THE OPEN</span><h2>Every line.<br />Open to inspect.</h2><p>Sources, conversion, verification, and exports are public. Found a broken source or a useful improvement? Bring it to the project.</p><a className="button dark-button" href={GITHUB} target="_blank" rel="noreferrer">Explore on GitHub <Icon name="external" size={18} /></a><div className="license-label"><Icon name="code" size={16} /> MIT licensed · Community maintained</div></article><article className="honesty-card"><Icon name="shield" size={26} /><h3>Access is not anonymity.</h3><p>Third parties operate these servers. An HTTPS connectivity check is not proof that an operator is trustworthy, and it does not guarantee privacy.</p><p>Avoid sensitive accounts on public proxies. For a connection you control, run your own server.</p><a className="text-link" href={`${GITHUB}#readme`} target="_blank" rel="noreferrer">Read the security notes <Icon name="external" size={16} /></a></article></section>;
}

export function Support() {
  return <section className="support-section section" data-reveal><div><span className="eyebrow">KEEP THE PROJECT OPEN</span><h2>Useful today.<br />Here tomorrow.</h2><p>A star, a reliable public source, or a contribution helps maintain it.</p><details className="ton-support"><summary className="glass">Support with TON <Icon name="plus" size={16} /></summary><div className="ton-panel"><img src="./assets/ton-qr.png" alt="TON donation wallet QR code" width="128" height="128" loading="lazy" /><div><code>{TON}</code><CopyButton value={TON} className="secondary">Copy TON address</CopyButton></div></div></details></div><div className="support-actions"><a className="button secondary glass" href={`${GITHUB}/issues`} target="_blank" rel="noreferrer">Share an improvement <Icon name="external" /></a><a className="text-link" href={DONATION_URL} target="_blank" rel="noreferrer">Support the project <Icon name="external" size={16} /></a></div></section>;
}

export function Footer() {
  return <footer className="footer"><span>Free VPN Sub · Public configurations, independently checked.</span><div><a href={`${GITHUB}/blob/main/LICENSE`}>MIT License</a><a href={GITHUB}>GitHub</a><a href={DONATION_URL} target="_blank" rel="noreferrer">Support <Icon name="external" size={14} /></a></div></footer>;
}
