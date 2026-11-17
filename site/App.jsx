import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import useNetwork from "./hooks/useNetwork.js";
import useTheme from "./hooks/useTheme.js";
import { useReveal } from "./hooks/useEffects.js";
import { Brand, ThemeControl } from "./components/Primitives.jsx";
import Hero from "./components/Hero.jsx";
import Subscription from "./components/Subscription.jsx";
import Network from "./components/Network.jsx";
import { Footer, Guide, Principles, Support } from "./components/Sections.jsx";
import { GITHUB } from "./config.js";
import { Icon } from "./components/Primitives.jsx";
import "./styles.css";

function App() {
  const network = useNetwork();
  const theme = useTheme();
  const page = useRef(null);
  const [scrolled, setScrolled] = useState(false);
  useReveal(page);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    if ("serviceWorker" in navigator) navigator.serviceWorker.getRegistrations().then((list) => list.filter((r) => r.scope === new URL("./", location.href).href).forEach((r) => r.update().catch(() => {}))).catch(() => {});
  }, []);

  return <div ref={page}><a className="skip-link" href="#main-content">Skip to content</a><div className="ambient" aria-hidden="true"><i /><i /></div><div className="page-shell">
    <header className={`header${scrolled ? " scrolled" : ""}`}><Brand /><nav className="main-nav glass" aria-label="Main navigation"><a href="#connect">Connect</a><a href="#network">Network</a><a href="#how-it-works">How it works</a></nav><div className="header-actions"><ThemeControl theme={theme} /><a className="github-link glass" href={GITHUB} target="_blank" rel="noreferrer" aria-label="GitHub repository"><Icon name="code" size={18} /><span>GitHub</span><Icon name="external" size={14} /></a></div></header>
    <main id="main-content"><Hero network={network} /><div className="trust-line" data-reveal><span><Icon name="check" size={16} /> No registration</span><span><Icon name="check" size={16} /> Real-traffic verification</span><span><Icon name="check" size={16} /> Open source, end to end</span></div><Subscription network={network} /><Network network={network} /><Guide /><Principles /><Support /></main><Footer />
  </div></div>;
}

createRoot(document.getElementById("root")).render(<App />);
