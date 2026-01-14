import json
import os
import re
import sys
from urllib.request import Request, urlopen

TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

req = Request(
    "https://api.github.com/repos/indygreg/python-build-standalone/releases?per_page=50",
    headers=HEADERS,
)
with urlopen(req) as resp:
    releases = json.load(resp)

pattern = re.compile(r"cpython-3\.11\.\d+\+\d{8}-x86_64.*-unknown-linux-gnu-.*\.tar\.zst$")
for release in releases:
    for asset in release.get("assets", []):
        url = asset.get("browser_download_url", "")
        if pattern.search(url):
            print(url)
            sys.exit(0)

print("No matching python-build-standalone asset found for CPython 3.11 x86_64 linux-gnu in last 50 releases", file=sys.stderr)
sys.exit(1)
