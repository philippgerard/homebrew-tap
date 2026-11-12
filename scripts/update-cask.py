#!/usr/bin/env python3
"""Publish only checksum-verified stable releases with successful release CI."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.request import Request, urlopen

REPO = "philippgerard/filen-menubar"
API = f"https://api.github.com/repos/{REPO}"
VERSION = re.compile(r"0|[1-9][0-9]*")
SHA256 = re.compile(r"[0-9a-f]{64}")
CASK = Path(__file__).resolve().parents[1] / "Casks/filen-menubar.rb"


def version_tuple(value):
    parts = value.split(".")
    if len(parts) != 3 or not all(VERSION.fullmatch(p) for p in parts):
        raise ValueError("Expected a stable three-part version")
    return tuple(map(int, parts))


def fetch(url, *, api=False):
    headers = {"User-Agent": "filen-menubar-homebrew-updater"}
    if api:
        if not url.startswith(API + "/"):
            raise ValueError("Unexpected API URL")
        headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=120) as response:
        return response.read()


def api_json(path):
    return json.loads(fetch(API + "/" + path, api=True))


def release_asset(release, name, tag):
    assets = [a for a in release["assets"] if a["name"] == name]
    if len(assets) != 1:
        raise ValueError(f"Expected exactly one {name} release asset")
    asset = assets[0]
    expected = f"https://github.com/{REPO}/releases/download/{tag}/{name}"
    digest = asset.get("digest", "")
    if (asset.get("state") != "uploaded" or asset.get("browser_download_url") != expected
            or not digest.startswith("sha256:") or not SHA256.fullmatch(digest[7:])):
        raise ValueError(f"Untrusted URL or missing digest for {name}")
    return asset


def verified_bytes(asset):
    data = fetch(asset["browser_download_url"])
    if hashlib.sha256(data).hexdigest() != asset["digest"][7:]:
        raise ValueError(f"GitHub digest mismatch for {asset['name']}")
    return data


def resolve_commit(tag):
    obj = api_json(f"git/ref/tags/{tag}")["object"]
    for _ in range(5):
        if obj["type"] == "commit" and re.fullmatch(r"[0-9a-f]{40}", obj["sha"]):
            return obj["sha"]
        if obj["type"] != "tag" or not re.fullmatch(r"[0-9a-f]{40}", obj["sha"]):
            break
        obj = api_json(f"git/tags/{obj['sha']}")["object"]
    raise ValueError("Release tag does not resolve to a commit")


def verify_release_ci(commit):
    path = ("actions/workflows/build.yml/runs?event=workflow_dispatch&branch=main"
            f"&head_sha={commit}&per_page=100")
    runs = api_json(path)["workflow_runs"]
    matches = [r for r in runs if r.get("head_sha") == commit
               and r.get("head_branch") == "main"
               and r.get("event") == "workflow_dispatch"
               and r.get("path") == ".github/workflows/build.yml"
               and r.get("status") == "completed" and r.get("conclusion") == "success"]
    if not matches:
        raise ValueError("No successful upstream release workflow at the exact tagged commit")
    return max(matches, key=lambda r: r["id"])["html_url"]


def verified_release():
    release = api_json("releases/latest")
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease") or not release.get("published_at") or not tag.startswith("v"):
        raise ValueError("Expected a published stable release")
    version = tag[1:]
    version_tuple(version)
    commit = resolve_commit(tag)
    workflow = verify_release_ci(commit)
    name = f"Filen.Menubar_{version}_aarch64.dmg"
    dmg = release_asset(release, name, tag)
    sums = verified_bytes(release_asset(release, "SHA256SUMS", tag)).decode("utf-8")
    matching = []
    for line in sums.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](?:\./)?(.+)", line)
        if not match:
            raise ValueError("Invalid SHA256SUMS entry")
        if match[2] == name:
            matching.append(match[1])
    digest = dmg["digest"][7:]
    if matching != [digest]:
        raise ValueError("Missing, duplicate or inconsistent DMG checksum")
    verified_bytes(dmg)
    return {"version": version, "sha256": digest, "commit": commit, "workflow": workflow}


def updated_cask(text, release):
    versions = re.findall(r'^  version "([^"]+)"$', text, re.MULTILINE)
    hashes = re.findall(r'^  sha256 "([0-9a-f]{64})"$', text, re.MULTILINE)
    if len(versions) != 1 or len(hashes) != 1:
        raise ValueError("Expected one version and checksum in the cask")
    current, target = version_tuple(versions[0]), version_tuple(release["version"])
    if not SHA256.fullmatch(release["sha256"]):
        raise ValueError("Invalid target checksum")
    if target < current:
        raise ValueError("Refusing a version downgrade")
    if target == current:
        if hashes[0] != release["sha256"]:
            raise ValueError("Release asset changed for an already packaged version")
        return text
    text = re.sub(r'^  version "[^"]+"$', f'  version "{release["version"]}"', text, flags=re.MULTILINE)
    return re.sub(r'^  sha256 "[0-9a-f]{64}"$', f'  sha256 "{release["sha256"]}"', text, flags=re.MULTILINE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify and report without changing the cask")
    args = parser.parse_args()
    release = verified_release()
    original = CASK.read_text()
    updated = updated_cask(original, release)
    changed = updated != original
    if changed and not args.check:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=CASK.parent, delete=False) as file:
                temporary = Path(file.name)
                file.write(updated)
            temporary.chmod(0o644)
            temporary.replace(CASK)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    print(json.dumps({**release, "changed": changed, "check_only": args.check}))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as file:
            file.write(f"changed={str(changed).lower()}\nversion={release['version']}\n")


if __name__ == "__main__":
    main()
