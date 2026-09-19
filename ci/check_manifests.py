#!/usr/bin/env python3
"""
biz-14 manifest guard.

Two invariants for every */latest.json in this repo:

  1. It parses against schema/server-manifest.schema.json - the JSON-Schema
     mirror of the Elysium client's `ServerManifest` struct
     (elysium: source/src-tauri/src/updater.rs). A manifest the client cannot
     deserialize is a silent "could not reach update server", i.e. a false
     "you are up to date".

  2. Every `url` anywhere in the manifest returns HTTP 200. A url that 404s is
     exactly the lie biz-14 removed: the manifest advertises a download that
     does not exist. The honest alternative is to omit the url (the client's
     PlatformEntry.url is Option<String>), so there is simply nothing to fetch.

Exits non-zero (failing CI) if any manifest is invalid or any url is not 200.
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "schema" / "server-manifest.schema.json"
HTTP_TIMEOUT = 30
# Some CDNs (Cloudflare fronts updates.animusai.net) 403 the default urllib
# User-Agent as a suspected bot, which would make a genuinely-hosted 200 url
# look broken. Present a normal browser UA so the check reflects what a real
# client / curl sees.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36 animusai-manifest-check"
)


def find_manifests():
    return sorted(REPO.glob("*/latest.json"))


def collect_urls(node):
    """Every string value under a `url` key, anywhere in the manifest."""
    urls = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "url" and isinstance(value, str):
                urls.append(value)
            else:
                urls.extend(collect_urls(value))
    elif isinstance(node, list):
        for item in node:
            urls.extend(collect_urls(item))
    return urls


def url_status(url):
    """Return (ok, detail). Follows redirects; HEAD, falling back to GET."""
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url, method=method, headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return resp.status == 200, f"HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                # Some servers reject HEAD; retry with GET before giving up.
                continue
            return False, f"HTTP {e.code}"
        except urllib.error.URLError as e:
            return False, f"URL error: {e.reason}"
        except Exception as e:  # noqa: BLE001
            return False, f"error: {e}"
    return False, "unreachable"


def main():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)

    manifests = find_manifests()
    if not manifests:
        print("ERROR: no */latest.json manifests found", file=sys.stderr)
        return 1

    failures = []

    for manifest_path in manifests:
        rel = manifest_path.relative_to(REPO).as_posix()
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            failures.append(f"{rel}: not valid JSON: {e}")
            print(f"FAIL  {rel}: not valid JSON: {e}")
            continue

        schema_errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if schema_errors:
            for err in schema_errors:
                loc = "/".join(str(p) for p in err.path) or "(root)"
                failures.append(f"{rel}: schema: {loc}: {err.message}")
                print(f"FAIL  {rel}: schema at {loc}: {err.message}")
        else:
            print(f"ok    {rel}: parses against ServerManifest schema")

        urls = collect_urls(data)
        if not urls:
            print(f"ok    {rel}: no url advertised (nothing to 404)")
        for url in urls:
            ok, detail = url_status(url)
            if ok:
                print(f"ok    {rel}: url {url} -> {detail}")
            else:
                failures.append(f"{rel}: url {url} -> {detail}")
                print(f"FAIL  {rel}: url {url} -> {detail}")

    print()
    if failures:
        print(f"{len(failures)} problem(s) found:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"All {len(manifests)} manifest(s) valid; every advertised url returns 200.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
