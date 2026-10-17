# Free VPN Subscription

[![Website](https://img.shields.io/badge/website-live%20list-blueviolet)](https://sakazxc1400-creator.github.io/free-vpn-sub/)
[![Update subscription](https://github.com/sakazxc1400-creator/free-vpn-sub/actions/workflows/update.yml/badge.svg)](https://github.com/sakazxc1400-creator/free-vpn-sub/actions/workflows/update.yml)
[![Servers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.published&label=servers&color=brightgreen)](output/all.txt)
[![Total](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.published_full&label=total&color=green)](output/all-full.txt)
[![Countries](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.countries&label=countries&color=blue)](output/by-country)
[![Updated](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fsakazxc1400-creator%2Ffree-vpn-sub%2Fmain%2Foutput%2Fstats.json&query=%24.updated&label=updated&color=informational)](output/stats.json)
[![License MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

**[Русская версия](README.md)**

Website with the live server list, statistics, and guides: **https://sakazxc1400-creator.github.io/free-vpn-sub/**

A free VPN subscription with servers that are checked and refreshed every hour.

The script collects configs from public GitHub sources, tests them, and keeps only the servers that actually work. Each server name includes its country, protocol, and latency.

There are three subscription sizes:

* the main list, with around 200 of the fastest servers;
* the stable list, only servers that answered several runs in a row, usually 30 to 100;
* the full list, with every server that passed verification, usually more than 1,000.

The main list is quicker to load and is best for everyday use. The stable list updates more slowly but its servers do not vanish after an hour. The full list is useful when nothing in the main list connects or when you want to pick a server yourself.

Supported protocols include VLESS, including Reality, VMess, Trojan, Shadowsocks, Hysteria2, and TUIC. A ready-made Clash and Mihomo config is available too.

## Subscription link

Main subscription:

```
https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub.txt
```

Stable subscription:

```
https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub-stable.txt
```

Full subscription:

```
https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub-full.txt
```

Clash or Mihomo config:

```
https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/clash.yaml
```

If `raw.githubusercontent.com` is blocked on your network, try one of the mirrors below. The content is the same.

```
https://cdn.jsdelivr.net/gh/sakazxc1400-creator/free-vpn-sub@main/output/sub.txt
```

```
https://gh-proxy.com/https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/main/output/sub.txt
```

For the full subscription, replace `sub.txt` with `sub-full.txt` in the link. For the stable one, use `sub-stable.txt`.

jsdelivr may cache a version for a few hours. gh-proxy usually shows updates faster.

## What is in the list

Servers are sorted from fastest to slowest. For example:

```
01. 🇨🇦 Canada · vless · 25ms · 12h
02. 🇺🇸 USA · vless · 123ms
03. 🇬🇧 UK · ss · 398ms · 8h
04. 🇫🇷 France · ss · 405ms
05. 🇳🇱 Netherlands · ss · 408ms · 26h
```

A number like `12h` at the end shows how many hours in a row the server has been answering in our runs. New nodes do not have this mark yet.

The `⚠` sign means the node passes traffic but failed the HTTPS certificate check: it may intercept certificates and read connection contents. Such nodes only appear in the full subscription.

The main subscription includes no more than 12 servers from one country. This keeps the list from being filled almost entirely by a single datacenter. The full subscription has no country limit.

Inside the main list servers are ranked by quality: certificate-checked nodes with a measured speed first, then by latency. Speed is measured for the best 150 nodes and stored in `output/nodes.json`.

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
| `output/sub-stable.txt` | Stable subscription in base64 |
| `output/all-stable.txt` | Stable subscription as plain text |
| `output/sub-full.txt` | Full subscription in base64 |
| `output/all-full.txt` | Full subscription as plain text |
| `output/clash.yaml` | Clash and Mihomo config with “Auto”, “Manual” and per-country groups |
| `output/nodes.json` | Website data: country, protocol, latency, speed, uptime |
| `output/history.json` | Node history: how many runs in a row each server answers |
| `output/vless.txt` and others | Servers using one protocol |
| `output/by-country/us.txt` and others | Servers from one country |
| `output/stats.json` | Statistics from the latest update |

The website can build a personal subscription: tick the nodes you want and download the file. Your selection is processed in the browser and never sent anywhere.

## How it works

```
sources.txt     list of sources
collect.py      download, parse, check, and save configs
outbound.py     convert links into a sing-box config
probe.py        check traffic, the certificate, and the speed
clashout.py     build a Clash or Mihomo config from checked nodes
notify.py       send run summaries to Telegram
geo.py          look up the country by IP
mirror/         subscription mirror on Cloudflare Workers
output/         generated lists
docs/           website for GitHub Pages
```

GitHub Actions runs the collection every hour.

First, the script downloads the sources in parallel, retrying each request up to three times. It handles plain text and base64, extracts the links, and removes junk such as broken addresses, localhost, private subnets, and invalid ports.

Next, duplicate servers are merged. The same address often appears in several sources under different names. This leaves more than 20,000 unique candidates.

Verification has two stages. The first is a quick TCP check that removes clearly unreachable addresses. Then sing-box starts a local proxy for each candidate and sends a request to `generate_204` through it. An empty response with status 204 means the server really passed traffic to the internet and returned the response.

Servers are checked by several sing-box processes at once, so more candidates get verified within the same time budget.

Hysteria2 and TUIC use QUIC, so they skip the TCP check and go straight to the second stage.

Before verification, the script drops configs that make sing-box fail to start and take the whole batch down with them: an unknown uTLS fingerprint (such as `unsafe`), a broken Reality key, a TUIC node without a valid UUID, shadowsocks-2022 with a key of the wrong length, and an invented VMess cipher. Such a node would not work anyway, but without this filter it would stop its neighbours from being checked.

After verification, the script looks up each server's country, measures latency, and sorts the results. The full list gets every working server. The main subscription takes the best ones while limiting the number from each country.

Next, every live node goes through an HTTPS check: the script connects through it to sites with known certificates and validates the certificate fully. If a node serves its own certificate, it reads the contents of your connections. Such a node stays only in the full subscription and is marked with `⚠`.

The best 150 nodes by latency get a speed measurement: a file is downloaded through the node and the result in megabits per second lands in `output/nodes.json`. The subscription itself does not carry the speed, so the list stays small.

Runs are linked to each other through `output/history.json`. The script counts how many runs in a row a node keeps answering and remembers that number. Nodes alive for many hours go into the separate stable subscription: usually these are the most reliable servers in the list.

If a build turns out noticeably worse than the previous one, under 60% of the previous server count, the script does not overwrite the subscriptions and exits with an error. That way a failure on the source side will not leave you with an empty list. Set `ALLOW_SHRINK=1` to bypass the guard when the drop is real.

Servers with the same address and port are merged into one, keeping the fastest. The same node often appears in the sources as a dozen copies with different UUIDs, and without this the subscription would fill up with duplicates.

If the sources are unavailable or no server passes verification, the old files are kept. A working subscription with old data is better than an empty list.

### Telegram notifications

A run can send a summary to Telegram: how many servers were found, which countries are in the list, what changed. The feature stays off until the secrets are set.

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Send your bot any message and get your id from [@userinfobot](https://t.me/userinfobot).
3. In the repository, open `Settings` → `Secrets and variables` → `Actions` and add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

You can test it by hand:

```bash
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python notify.py "test message"
```

### Subscription mirror

If GitHub is blocked on your network, run a mirror on Cloudflare Workers: the files are the same while the Cloudflare domain is usually reachable. The code and step-by-step instructions are in [`mirror/`](mirror/README.md). The free tier is more than enough, and everything is done in the browser.

### Running locally

```bash
python selftest.py     # check the parsers
python testconv.py     # check link conversion and country lookup
python testclash.py    # check Clash config generation
python testsingbox.py  # check configs, sing-box required
python e2etest.py      # run the full test scenario
python collect.py      # build the subscription
```

Python 3.9 or newer is required. No extra libraries are needed; `testclash.py` likes `pyyaml` but works without it. For full server verification, place the [sing-box](https://github.com/SagerNet/sing-box/releases) binary next to the scripts. Without it, the script only performs TCP checks and says so in the log.

### Adding a source

Add a link to `sources.txt`, one per line. Lines starting with `#` are comments. The source format is detected automatically.

## Important security note

Please read this before using the subscription.

The server owner may be able to see your traffic. These servers are run by unknown people, and we do not know how they handle the traffic that passes through them. The operator may see which sites you visit. If they replace a certificate, they may also intercept the contents of your connections.

That is why every node additionally passes an HTTPS request with full certificate validation. A node that intercepts certificates to read connection contents never gets into the main subscription: in the full list it is marked with `⚠`. This lowers the risk but does not remove it: the server owner still sees which sites you connect to.

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
