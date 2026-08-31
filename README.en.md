# Free VPN Subscription

[![Update subscription](https://github.com/sakazxc1400-creator/free-vpn-sub/actions/workflows/update.yml/badge.svg)](https://github.com/sakazxc1400-creator/free-vpn-sub/actions/workflows/update.yml)
[![Servers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.published&label=servers&color=brightgreen)](output/all.txt)
[![Total](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.published_full&label=total&color=green)](output/all-full.txt)
[![Countries](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.countries&label=countries&color=blue)](output/by-country)
[![Updated](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.updated&label=updated&color=informational)](output/stats.json)
[![License MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

**[Русская версия](README.md)**

A free VPN server list that updates itself every hour.

Configs are pulled from public GitHub sources, merged into a single link, and
verified: a real request goes out through every server, and only the ones that
actually pass traffic make it to the list. Each server shows its country,
protocol, and latency right in the name.

Two subscription sizes: the main one holds around two hundred hand-picked
servers, the full one holds everything that passed verification — usually over
a thousand. The main list pings in seconds; the full one is there when you want
to dig through every option.

Protocols: VLESS (including Reality), VMess, Trojan, Shadowsocks, Hysteria2, TUIC.

## Subscription link

Main — short list, for everyday use:

```
https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub.txt
```

Full — everything that passed verification:

```
https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub-full.txt
```

If `raw.githubusercontent.com` is blocked in your network, use a mirror. The
content is identical:

```
https://cdn.jsdelivr.net/gh/sakazxc1400-creator/free-vpn-sub@main/output/sub.txt
```

```
https://gh-proxy.com/https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub.txt
```

For the full subscription, swap the filename to `sub-full.txt` in either mirror.

Both mirrors are tested. jsdelivr caches for a few hours, gh-proxy serves the
latest version immediately.

## What the list looks like

Servers are sorted by latency, fastest first:

```
01. 🇨🇦 Canada · vless · 25ms
02. 🇺🇸 USA · vless · 123ms
03. 🇬🇧 UK · ss · 398ms
04. 🇫🇷 France · ss · 405ms
05. 🇳🇱 Netherlands · ss · 408ms
```

In the main subscription no single country takes more than 12 slots — otherwise
half the list would be one datacenter in Hong Kong. The full one has no such cap.

## Setup

### Windows

Easiest with [Nekoray](https://github.com/MatsuriDayo/nekoray/releases):
download `nekoray-*-windows64.zip`, unpack, run `nekoray.exe`.

1. Program → Preferences → Core → `sing-box`
2. Server → Add profile from subscription, paste the link, OK
3. Server → Update all subscriptions
4. Pick a server from the top, press `Enter`
5. `Ctrl+Alt+S` enables the system proxy

[v2rayN](https://github.com/2dust/v2rayN/releases) works too — subscriptions go
under "Subscription → Subscription settings".

### Android

[v2rayNG](https://github.com/2dust/v2rayNG/releases) or Google Play.

1. `≡` top left → Subscription group setting → `+`
2. Paste the link into the URL field, save
3. `⋮` top right → Update subscriptions
4. Pick a server, tap connect

[Hiddify](https://github.com/hiddify/hiddify-next/releases) is also good,
especially for Hysteria2 and TUIC. Add via `+` → "Add from link".

### iPhone / iPad

From the App Store: Streisand (free), v2Box (free), or Shadowrocket (paid).
Same everywhere: subscription section → `+` → paste link → update → pick a server.

### macOS

[Hiddify](https://github.com/hiddify/hiddify-next/releases) or V2RayXS.
Add the subscription by link, update, connect.

### Linux

[Nekoray](https://github.com/MatsuriDayo/nekoray/releases) or
[Hiddify](https://github.com/hiddify/hiddify-next/releases) as an AppImage.

## Troubleshooting

**Server connects but there is no internet.** It happens: between the check and
your connection the server may have gone down or hit its limit. Take the next
one on the list.

**Nothing works at all.** Refresh the subscription in your client — the list
changes every hour.

**Subscription won't load.** Use a mirror from the section above. If that is
blocked too, download `output/all.txt` manually and paste its contents into the
client via "Import from clipboard".

**Slow.** Free servers are overloaded, that is normal. Take the ones near the
top. Hysteria2 usually holds up best on bad connections.

## Files

| File | Contents |
|------|----------|
| `output/sub.txt` | Main subscription, base64 |
| `output/all.txt` | Same as plain text |
| `output/sub-full.txt` | Full subscription, base64 |
| `output/all-full.txt` | Same as plain text |
| `output/vless.txt` and others by protocol | Single protocol, from the full list |
| `output/by-country/us.txt` etc. | Single country, from the full list |
| `output/stats.json` | Stats from the last update |

## How it works

```
sources.txt     list of sources
collect.py      main script: download, parse, verify, write
outbound.py     converts vless:// and friends into sing-box config
probe.py        verification via sing-box: does traffic actually flow
geo.py          country lookup by IP
output/         results
```

Every hour GitHub Actions does the following.

Downloads all sources in parallel, three attempts each. Handles both plain text
and base64. Extracts links, drops junk: broken addresses, localhost, private
subnets, out-of-range ports.

Then deduplication by server address, not by link text. The same server often
sits in five sources under different names, and without this step the list
would be half duplicates. Out of 40,000 links about 11,000 distinct servers
remain.

Then two verification stages. First a fast TCP connect, which weeds out dead
addresses in a minute. Survivors go to the second stage: sing-box starts up, a
local proxy is bound per server, and a request to `generate_204` goes through
it. A 204 with an empty body means traffic really reached the internet and came
back. Verification runs in batches of 150 until candidates or the time budget
run out.

QUIC protocols (Hysteria2, TUIC) skip the TCP filter: on a working server the
TCP port is closed, so knocking there is pointless. They go straight to the
second stage.

Finally the country is resolved by IP and servers are sorted by latency.
Everything verified goes into the full subscription; the main one takes the top
slice with a per-country quota.

If the sources are unreachable or no server passes verification, the script
exits with an error and leaves the old files alone. A slightly stale working
subscription beats an empty one.

### Running locally

```bash
python selftest.py     # parsers
python testconv.py     # link converter and geo
python testsingbox.py  # config validity (needs sing-box)
python e2etest.py      # full pipeline against a local server
python collect.py      # build the subscription
```

Python 3.9+, no dependencies. For full node verification put the
[sing-box](https://github.com/SagerNet/sing-box/releases) binary next to the
scripts; without it the script falls back to TCP checks and says so in the log.

### Adding sources

Append links to `sources.txt`, one per line. `#` starts a comment. The content
format is detected automatically.

## Security notice

This matters — read it before you start.

The server owner sees your traffic. These servers were set up by unknown people
for unknown reasons. The operator can see which sites you visit, and with a
substituted certificate, the contents of your connections too.

Hence the simple rules. Do not log into banking, government services, or work
email through such a VPN. Do not send passwords, documents, or payment details.
This is a tool for bypassing blocks, not a privacy tool.

If you need actual privacy there are two options: a paid service with a
reputation, or your own server. VLESS+Reality on a cheap VPS takes an evening to
set up and runs noticeably faster than any free node.

There is no way to verify these servers are run in good faith. Use at your own
risk.

## Support

The project is free and will stay that way. If you found it useful:
[donate](https://www.donationalerts.com/r/saka1232131).

Also accepted in TON:

```
UQDj7y9AG8P_4oZ4KAnpRDfCulC-FsgnqSI_8xABobHvc1F3
```

You can help without money too: star the repo so people who need it can find it.
Found a dead source or know a good one? Open an
[issue](../../issues) or edit `sources.txt` and send a pull request.

## License

MIT. This project only collects publicly available configs into one list. The
servers belong to third parties; this repository provides no VPN service.
