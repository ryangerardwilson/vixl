#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys

API_URL = "https://api.github.com/repos/indygreg/python-build-standalone/releases?per_page=50"
TOKEN = os.environ.get("GITHUB_TOKEN")

cmd = [
    "curl",
    "-fsSL",
    "--retry",
    "8",
    "--retry-all-errors",
    "--connect-timeout",
    "10",
    "--max-time",
    "60",
]
if TOKEN:
    cmd += ["-H", f"Authorization: Bearer {TOKEN}"]
cmd.append(API_URL)

try:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
except subprocess.CalledProcessError as exc:
    sys.stderr.write(exc.stderr or "curl failed\n")
    sys.exit(exc.returncode or 1)

try:
    releases = json.loads(result.stdout)
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
