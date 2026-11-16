export const REPO = "sakazxc1400-creator/free-vpn-sub";
export const GITHUB = `https://github.com/${REPO}`;
export const RAW = `https://raw.githubusercontent.com/${REPO}/data/output/`;

export const MIRRORS = [
  ["GitHub", RAW],
  ["jsDelivr", `https://cdn.jsdelivr.net/gh/${REPO}@data/output/`],
  ["gh-proxy", `https://gh-proxy.com/${RAW}`],
  ["ghproxy.net", `https://ghproxy.net/${RAW}`],
  ["githack", `https://raw.githack.com/${REPO}/data/output/`],
];

export const PLANS = [
  { name: "Everyday", file: "sub.txt", key: "published", eyebrow: "The essential list", title: "A balanced place to start.", description: "Up to 200 traffic-tested servers, balanced across countries. Every node passed the automated HTTPS check.", foot: "For Hiddify, v2rayNG, and other subscription clients." },
  { name: "Stable", file: "sub-stable.txt", key: "stable", eyebrow: "Proven over time", title: "Consistency, earned.", description: "Servers that passed at least six consecutive checks and the automated HTTPS check. A smaller list with a track record.", foot: "This list can be empty until enough checks have completed." },
  { name: "Full network", file: "sub-full.txt", key: "published_full", eyebrow: "The wider network", title: "More routes, clearly marked.", description: "Every server that passed the traffic check, including nodes that failed HTTPS verification. Those nodes carry a warning.", foot: "Use Everyday when you want HTTPS-verified nodes only." },
  { name: "Clash / Mihomo", file: "clash.yaml", key: "published", eyebrow: "Ready for your client", title: "One YAML. Your client.", description: "Automatic and manual selection groups, country groups, and HTTPS-verified nodes for Mihomo-based clients.", foot: "Compatible with Clash Verge Rev, FlClash, and Mihomo." },
];

export const PROTOCOLS = ["VLESS", "VMess", "Trojan", "Shadowsocks", "Hysteria2", "TUIC"];
export const TON = "UQDj7y9AG8P_4oZ4KAnpRDfCulC-FsgnqSI_8xABobHvc1F3";
export const DONATION_URL = "https://www.donationalerts.com/r/saka12312312";

export function importUrl(plan, url) {
  return plan.file === "clash.yaml"
    ? `clash://install-config?url=${encodeURIComponent(url)}&name=FreeVPNSub`
    : `hiddify://import/${url}#FreeVPNSub`;
}
