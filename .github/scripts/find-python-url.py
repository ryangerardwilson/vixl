#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import time

API_URL = "https://api.github.com/repos/astral-sh/python-build-standalone/releases?per_page=100"
TOKEN = os.environ.get("GITHUB_TOKEN")

def fetch_releases(max_attempts: int = 8) -> str:
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        cmd = [
            "curl",
            "-fsSL",
            "-L",
            "-w",
            "%{http_code}",
            "--connect-timeout",
            "10",
            "--max-time",
            "60",
        ]
        if TOKEN:
            cmd += ["-H", f"Authorization: Bearer {TOKEN}"]
        cmd.append(API_URL)

        proc = subprocess.run(cmd, capture_output=True, text=True)
        stdout = proc.stdout[:-3] if len(proc.stdout) >= 3 else ""
        status = proc.stdout[-3:]

        if proc.returncode == 0 and status == "200":
            return stdout

        # Retry on HTTP 5xx
        if status.isdigit() and status.startswith("5") and attempt < max_attempts:
            sleep_for = min(5 * attempt, 30)
            sys.stderr.write(
                f"curl returned {status}. Retrying in {sleep_for}s (attempt {attempt}/{max_attempts})\n"
            )
            sys.stderr.flush()
            time.sleep(sleep_for)
            continue

        sys.stderr.write(proc.stderr or f"curl failed with status {status}\n")
        sys.exit(proc.returncode or 1)

    sys.stderr.write("Exceeded retry attempts fetching releases\n")
    sys.exit(1)

result = fetch_releases()

try:
    releases = json.loads(result)
except json.JSONDecodeError as exc:
    sys.stderr.write(f"Failed to parse releases JSON: {exc}\n")
    sys.exit(1)

pattern = re.compile(r"cpython-3\.11\.\d+\+\d{8}-x86_64.*-unknown-linux-gnu-.*\.tar\.zst$")
for release in releases:
    for asset in release.get("assets", []):
        url = asset.get("browser_download_url", "")
        if pattern.search(url):
            print(url)
            sys.exit(0)

sys.stderr.write(
    "No matching python-build-standalone asset found for CPython 3.11 x86_64 linux-gnu in last 50 releases\n"
)
sys.exit(1)
