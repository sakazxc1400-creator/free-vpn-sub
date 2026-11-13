#!/usr/bin/env python3
"""Offline regression tests for publication, parsing and probe boundaries."""

import base64
import json
import os
import tempfile
import unittest
import urllib.parse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import clashout
import collect
import outbound
import probe

UUID = "11111111-2222-3333-4444-555555555555"


def b64(text):
    return base64.b64encode(text.encode()).decode()


def node(link=None, **values):
    item = collect.parse_link(link or f"vless://{UUID}@1.2.3.4:443")
    assert item is not None
    for key, value in values.items():
        setattr(item, key, value)
    return item


class ParsingTests(unittest.TestCase):
    def test_credentials_are_not_truncated_or_case_folded(self):
        pairs = [
            ("trojan://Secret@1.2.3.4:443", "trojan://secret@1.2.3.4:443"),
            (f"tuic://{UUID}:one@1.2.3.4:443", f"tuic://{UUID}:two@1.2.3.4:443"),
            ("hy2://user:one@1.2.3.4:443", "hy2://user:two@1.2.3.4:443"),
            ("trojan://" + "x" * 36 + "A@1.2.3.4:443",
             "trojan://" + "x" * 36 + "B@1.2.3.4:443"),
            ("ss://" + b64("aes-256-gcm:" + "x" * 40 + "A") + "@1.2.3.4:443",
             "ss://" + b64("aes-256-gcm:" + "x" * 40 + "B") + "@1.2.3.4:443"),
        ]
        for a, b in pairs:
            with self.subTest(a=a):
                self.assertNotEqual(node(a).key, node(b).key)

    def test_transport_parameters_participate_in_identity(self):
        prefix = f"vless://{UUID}@1.2.3.4:443?type=ws&path="
        self.assertNotEqual(node(prefix + "%2Fa").key, node(prefix + "%2Fb").key)
        cfg = {"add": "1.2.3.4", "port": 443, "id": UUID, "net": "ws"}
        a = "vmess://" + b64(json.dumps(dict(cfg, path="/a")))
        b = "vmess://" + b64(json.dumps(dict(cfg, path="/b")))
        self.assertNotEqual(node(a).key, node(b).key)

    def test_equivalent_links_deduplicate(self):
        a = f"vless://{UUID}@1.2.3.4:443?type=ws&path=%2Fa#one"
        b = f"vless://{UUID}@1.2.3.4:443?path=%2Fa&type=ws#two"
        self.assertEqual(node(a).key, node(b).key)
        a = "ss://" + b64("aes-256-gcm:password") + "@1.2.3.4:443"
        b = "ss://" + b64("aes-256-gcm:password@1.2.3.4:443")
        self.assertEqual(node(a).key, node(b).key)

    def test_vmess_retag_roundtrip(self):
        cfg = {"add": "1.2.3.4", "port": 443, "id": UUID, "ps": "Old"}
        original = node("vmess://" + b64(json.dumps(cfg)), latency_ms=42)
        tagged = collect.retag(original, 1)
        payload = tagged.split("://", 1)[1].split("#", 1)[0]
        renamed = json.loads(base64.b64decode(payload))
        self.assertNotEqual(renamed["ps"], "Old")
        self.assertIn("42ms", renamed["ps"])
        self.assertEqual(node(tagged).key, original.key)
        self.assertEqual(outbound.build(tagged), outbound.build(original.raw))

    def test_vmess_accepts_existing_fragment(self):
        link = "vmess://" + b64(json.dumps({"add": "1.2.3.4", "port": 443, "id": UUID}))
        self.assertIsNotNone(collect.parse_link(link + "#old-label"))
        self.assertEqual(outbound.build(link + "#old-label"), outbound.build(link))

    def test_websocket_path_is_decoded_once(self):
        for proto in ("vless", "trojan"):
            link = f"{proto}://{UUID}@1.2.3.4:443?type=ws&path=%2Fa%252Fb"
            self.assertEqual(outbound.build(link)["transport"]["path"], "/a%2Fb")

    def test_plain_shadowsocks_credentials(self):
        link = "ss://aes-256-gcm:p%40ss%3Aword@1.2.3.4:8388"
        self.assertEqual(outbound.build(link)["password"], "p@ss:word")

    def test_encoded_shadowsocks_password_keeps_literal_percent(self):
        a = "ss://" + b64("aes-256-gcm:pass%41") + "@1.2.3.4:443"
        b = "ss://" + b64("aes-256-gcm:pass%41@1.2.3.4:443")
        self.assertEqual(node(a).key, node(b).key)
        self.assertEqual(outbound.build(a), outbound.build(b))


class SelectionTests(unittest.TestCase):
    def test_country_limit_is_a_hard_cap(self):
        nodes = [node(country="NL", ident=str(i)) for i in range(30)]
        self.assertEqual(len(collect.pick_diverse(nodes, 200, 12)), 12)

    def test_server_dedupe_prefers_verified_tls(self):
        insecure = node(tls_ok=False, verified=True, latency_ms=1)
        secure = node(tls_ok=True, verified=True, latency_ms=200)
        self.assertIs(collect.dedupe_servers([insecure, secure])[0], secure)

    def test_history_resets_hours_after_a_missed_run(self):
        now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
        history = {"nodes": {}}
        collect.apply_history(history, [node()], now - timedelta(hours=6))
        collect.apply_history(history, [], now - timedelta(hours=1))
        current = node()
        collect.apply_history(history, [current], now)
        self.assertEqual(current.streak, 1)
        self.assertEqual(current.uptime_hours, 0)

    def test_future_or_malformed_history_does_not_crash(self):
        now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
        bad_entries = [[], {"streak": "oops", "runs": None},
                       {"streak": 5, "last": "2026-11-14T12:00:00Z",
                        "first": "2026-11-14T12:00:00Z"}]
        for entry in bad_entries:
            with self.subTest(entry=entry):
                current = node()
                history = {"nodes": {current.addr: entry}}
                collect.apply_history(history, [current], now)
                self.assertEqual(current.streak, 1)
                self.assertEqual(current.uptime_hours, 0)


class PublicationTests(unittest.TestCase):
    def run_collection(self, tmp, verified):
        output = Path(tmp)
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"ALLOW_SHRINK": "0"}))
            replacements = {
                "OUTPUT_DIR": output, "HISTORY_FILE": output / "history.json",
                "read_sources": lambda: ["https://source.invalid/sub"],
                "fetch": lambda url: f"vless://{UUID}@1.2.3.4:443",
                "check_alive": lambda nodes: nodes,
                "log": lambda message: None,
            }
            for key, value in replacements.items():
                stack.enter_context(patch.object(collect, key, value))
            stack.enter_context(patch.object(probe, "verify", return_value=verified))
            stack.enter_context(patch.object(probe, "measure_speed", return_value=0))
            stack.enter_context(patch.object(collect.geo, "annotate", return_value={"1.2.3.4": "NL"}))
            stack.enter_context(patch("notify.send_report", return_value=False))
            return collect.main()

    def test_zero_verified_preserves_every_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub.txt"
            path.write_text("previous subscription", encoding="utf-8")
            self.assertEqual(self.run_collection(tmp, []), 1)
            self.assertEqual(path.read_text(encoding="utf-8"), "previous subscription")
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_tls_failures_are_only_in_full_subscription(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = node(tls_ok=True)
            bad = node(f"trojan://pw@5.6.7.8:443", tls_ok=False)
            self.assertEqual(self.run_collection(tmp, [(good, 100), (bad, 1)]), 0)
            main = (Path(tmp) / "all.txt").read_text(encoding="utf-8")
            full = (Path(tmp) / "all-full.txt").read_text(encoding="utf-8")
            self.assertNotIn("5.6.7.8", main)
            self.assertIn("5.6.7.8", full)
            self.assertNotIn("5.6.7.8", (Path(tmp) / "clash.yaml").read_text(encoding="utf-8"))

    def test_all_tls_failures_preserve_previous_subscription(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub.txt"
            path.write_text("previous", encoding="utf-8")
            self.assertEqual(self.run_collection(tmp, [(node(tls_ok=False), 10)]), 1)
            self.assertEqual(path.read_text(encoding="utf-8"), "previous")

    def test_allow_shrink_zero_does_not_disable_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.json"
            path.write_text(json.dumps({"published_full": 1000}), encoding="utf-8")
            self.assertEqual(self.run_collection(tmp, [(node(tls_ok=True), 10)]), 1)
            self.assertEqual(json.loads(path.read_text())["published_full"], 1000)

    def test_converter_failure_preserves_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub.txt"
            path.write_text("previous", encoding="utf-8")
            with patch.object(clashout, "build_clash", side_effect=ValueError("broken export")):
                self.assertEqual(self.run_collection(tmp, [(node(tls_ok=True), 10)]), 1)
            self.assertEqual(path.read_text(), "previous")
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_failed_replacement_restores_previous_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            output.mkdir()
            (output / "sub.txt").write_text("previous", encoding="utf-8")
            rename = Path.rename

            def fail_stage(path, target):
                if path.name == "new":
                    raise PermissionError("Replacement blocked")
                return rename(path, target)

            with patch.object(Path, "rename", fail_stage):
                self.assertEqual(self.run_collection(output, [(node(tls_ok=True), 10)]), 1)
            self.assertEqual((output / "sub.txt").read_text(), "previous")

    def test_failed_restore_keeps_recoverable_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            output.mkdir()
            (output / "sub.txt").write_text("previous", encoding="utf-8")
            rename = Path.rename

            def fail_restore(path, target):
                if path != output:
                    raise PermissionError("Replacement and restore blocked")
                return rename(path, target)

            with patch.object(Path, "rename", fail_restore):
                self.assertEqual(self.run_collection(output, [(node(tls_ok=True), 10)]), 1)
            backups = list(Path(tmp).glob(".subscription-*-previous"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "sub.txt").read_text(), "previous")


class ProbeTests(unittest.TestCase):
    def test_captive_portal_is_not_a_working_proxy(self):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b"<html>Sign in</html>"
        response.__enter__.return_value = response
        opener = MagicMock()
        opener.open.return_value = response
        with patch("urllib.request.build_opener", return_value=opener):
            self.assertEqual(probe.probe_one(24000), (None, False))
            self.assertFalse(probe.probe_tls(24000))

    def test_no_proxy_environment_cannot_bypass_probe(self):
        response = MagicMock()
        response.status = 204
        response.read.return_value = b""
        response.__enter__.return_value = response
        opener = MagicMock()
        opener.open.return_value = response
        with patch.dict(os.environ, {"NO_PROXY": "*", "no_proxy": "*"}), \
                patch("urllib.request.build_opener", return_value=opener):
            self.assertIsNotNone(probe.probe_one(24000)[0])
            request = opener.open.call_args.args[0]
            self.assertIsInstance(request, urllib.request.Request)
            self.assertEqual(request.host, "127.0.0.1:24000")

    def test_no_free_ports_does_not_start_empty_process(self):
        with patch.object(probe, "free_ports", return_value=[]), \
                patch("subprocess.Popen") as start:
            self.assertEqual(probe._verify_prepared([(node(), {})], "sing-box"), [])
            start.assert_not_called()


class ClashTests(unittest.TestCase):
    def test_suffix_collisions_are_resolved(self):
        used = {}
        names = [clashout._unique(name, used) for name in ["node", "node #2", "node", "node #2"]]
        self.assertEqual(len(set(names)), len(names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
