#!/usr/bin/env python3
"""Run Python checks in isolated processes with consistent UTF-8 output."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUITES = ("selftest.py", "testconv.py", "testclash.py", "testregressions.py", "e2etest.py", "testsingbox.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-singbox", action="store_true", help="Fail if the real sing-box executable is missing")
    args = parser.parse_args()
    env = dict(os.environ, PYTHONUTF8="1", TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
    if args.require_singbox:
        env["REQUIRE_SINGBOX"] = "1"
    for suite in SUITES:
        print(f"\n=== {suite} ===", flush=True)
        result = subprocess.run([sys.executable, "-X", "utf8", suite], cwd=ROOT, env=env)
        if result.returncode:
            return result.returncode
    print("\nAll Python suites passed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
