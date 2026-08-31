# Free VPN Subscription

[![Update subscription](https://github.com/sakazxc1400-creator/free-vpn-sub/actions/workflows/update.yml/badge.svg)](https://github.com/sakazxc1400-creator/free-vpn-sub/actions/workflows/update.yml)
[![Servers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.published&label=servers&color=brightgreen)](output/all.txt)
[![Total](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.published_full&label=total&color=green)](output/all-full.txt)
[![Countries](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.countries&label=countries&color=blue)](output/by-country)
[![Updated](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.updated&label=updated&color=informational)](output/stats.json)
[![License MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

**[Русская версия](README.md)**

A free VPN subscription with servers that are checked and refreshed every hour.

The script collects configs from public GitHub sources, tests them, and keeps only the servers that actually work. Each server name includes its country, protocol, and latency.

There are two subscription sizes:

* the main list, with around 200 of the fastest servers;
* the full list, with every server that passed verification, usually more than 1,000.

The main list is quicker to load and is best for everyday use. The full list is useful when nothing in the main list connects or when you want to pick a server yourself.

Supported protocols include VLESS, including Reality, VMess, Trojan, Shadowsocks, Hysteria2, and TUIC.

## Subscription link

Main subscription:

```
https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub.txt
```

Full subscription:

```
https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub-full.txt
```

If `raw.githubusercontent.com` is blocked on your network, try one of the mirrors below. The content is the same.

```
https://cdn.jsdelivr.net/gh/sakazxc1400-creator/free-vpn-sub@main/output/sub.txt
```

```
https://gh-proxy.com/https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub.txt
```

For the full subscription, replace `sub.txt` with `sub-full.txt` in the link.

jsdelivr may cache a version for a few hours. gh-proxy usually shows updates faster.

## What is in the list

Servers are sorted from fastest to slowest. For example:

```
01. 🇨🇦 Canada · vless · 25ms
02. 🇺🇸 USA · vless · 123ms
03. 🇬🇧 UK · ss · 398ms
04. 🇫🇷 France · ss · 405ms
05. 🇳🇱 Netherlands · ss · 408ms
```

The main subscription includes no more than 12 servers from one country. This keeps the list from being filled almost entirely by a single datacenter. The full subscription has no country limit.

## How to connect

### Windows

The easiest option is [Nekoray](https://github.com/MatsuriDayo/nekoray/releases). Download `nekoray-*-windows64.zip`, unpack it, and run `nekoray.exe`.

1. Open the settings and choose the `sing-box` core.
2. Go to the option for adding a profile from a subscription and paste the link.
3. Update the subscriptions.
4. Pick a server near the top of the list and press `Enter`.
5. Press `Ctrl+Alt+S` to enable the system proxy.

You can also use [v2rayN](https://github.com/2dust/v2rayN/releases). Add the link in the Subscriptions section.

### Android

Use [v2rayNG](https://github.com/2dust/v2rayNG/releases) or Hiddify.

1. Open the menu on the left and go to the subscription group settings.
2. Tap `+`, paste the link, and save it.
3. Open the menu on the right and update the subscriptions.
4. Pick a server and tap the connect button.

[Hiddify](https://github.com/hiddify/hiddify-next/releases) is especially convenient for Hysteria2 and TUIC. Add the subscription through `+` and "Add from link".

### iPhone and iPad

You can use Streisand, v2Box, or Shadowrocket. The first two are free, while Shadowrocket is paid.

Open the subscription section, tap `+`, paste the link, update the list, and choose a server.

### macOS

Try [Hiddify](https://github.com/hiddify/hiddify-next/releases) or V2RayXS. Add the subscription by link, update the list, and connect to a server.

### Linux

Use [Nekoray](https://github.com/MatsuriDayo/nekoray/releases) or [Hiddify](https://github.com/hiddify/hiddify-next/releases) in AppImage format.

## Troubleshooting

**The server connects, but there is no internet.** It may have stopped working or reached its limit after the last check. Try the next server in the list.

**None of the servers work.** Refresh the subscription in your app. The list changes every hour.

**The subscription will not load.** Use one of the mirrors above. If that is blocked too, download `output/all.txt` and import its contents from the clipboard.

**The connection is slow.** Free servers can get overloaded. Start with the first few entries. Hysteria2 often performs better than other protocols on unstable connections.

## Files

| File | Contents |
|------|----------|
| `output/sub.txt` | Main subscription in base64 |
| `output/all.txt` | Main subscription as plain text |
| `output/sub-full.txt` | Full subscription in base64 |
| `output/all-full.txt` | Full subscription as plain text |
| `output/vless.txt` and others | Servers using one protocol |
| `output/by-country/us.txt` and others | Servers from one country |
| `output/stats.json` | Statistics from the latest update |

## How it works

```
sources.txt     list of sources
collect.py      download, parse, check, and save configs
outbound.py     convert links into a sing-box config
probe.py        check whether traffic passes through a server
geo.py          look up the country by IP
output/         generated lists
```

GitHub Actions runs the collection every hour.

First, the script downloads the sources in parallel, retrying each request up to three times. It handles plain text and base64, extracts the links, and removes junk such as broken addresses, localhost, private subnets, and invalid ports.

Next, duplicate servers are merged. The same address often appears in several sources under different names. This leaves around 10,000 unique candidates.

Verification has two stages. The first is a quick TCP check that removes clearly unreachable addresses. Then sing-box starts a local proxy for each candidate and sends a request to `generate_204` through it. An empty response with status 204 means the server really passed traffic to the internet and returned the response.

Hysteria2 and TUIC use QUIC, so they skip the TCP check and go straight to the second stage.

After verification, the script looks up each server's country, measures latency, and sorts the results. The full list gets every working server. The main subscription takes the best ones while limiting the number from each country.

If the sources are unavailable or no server passes verification, the old files are kept. A working subscription with old data is better than an empty list.

### Running locally

```bash
python selftest.py     # check the parsers
python testconv.py     # check link conversion and country lookup
python testsingbox.py  # check configs, sing-box required
python e2etest.py      # run the full test scenario
python collect.py      # build the subscription
```

Python 3.9 or newer is required. No extra libraries are needed. For full server verification, place the [sing-box](https://github.com/SagerNet/sing-box/releases) binary next to the scripts. Without it, the script only performs TCP checks and says so in the log.

### Adding a source

Add a link to `sources.txt`, one per line. Lines starting with `#` are comments. The source format is detected automatically.

## Important security note

Please read this before using the subscription.

The server owner may be able to see your traffic. These servers are run by unknown people, and we do not know how they handle the traffic that passes through them. The operator may see which sites you visit. If they replace a certificate, they may also intercept the contents of your connections.

Do not use these servers for banking, government services, work email, or other important accounts. Do not send passwords, documents, or payment details through them. This subscription is for bypassing blocks, not for complete privacy or anonymity.

If you need privacy, choose a trusted paid service or set up your own server. VLESS+Reality on an inexpensive VPS is usually faster than free nodes.

There is no practical way to verify every server. Use the subscription at your own risk.

## Support the project

The subscription is free and will stay free. If it has been useful, you can [support the project with a donation](https://www.donationalerts.com/r/saka1232131).

TON transfers are also welcome:

![TON donation QR code](assets/ton-qr.png)

```
UQDj7y9AG8P_4oZ4KAnpRDfCulC-FsgnqSI_8xABobHvc1F3
```

The easiest way to help without spending money is to star the repository. If you find a broken source or know a good one, open an [issue](../../issues) or send a pull request with a change to `sources.txt`.

## License

MIT. This repository collects public configs into one list and does not provide a VPN service. The servers belong to third parties.
