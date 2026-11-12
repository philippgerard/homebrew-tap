import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("update_cask", Path(__file__).resolve().parents[1] / "scripts/update-cask.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.commit = "a" * 40
        self.tag = "v0.1.38"
        self.name = "Filen.Menubar_0.1.38_aarch64.dmg"
        self.dmg = b"signed application fixture"
        self.digest = hashlib.sha256(self.dmg).hexdigest()
        self.sums = f"{self.digest}  ./{self.name}\n".encode()
        self.assets = [self.asset(self.name, self.dmg), self.asset("SHA256SUMS", self.sums)]
        self.release = {"tag_name": self.tag, "draft": False, "prerelease": False,
                        "published_at": "2026-11-12T12:00:00Z", "assets": self.assets}
        self.run = {"id": 123, "head_sha": self.commit, "head_branch": "main",
                    "event": "workflow_dispatch", "path": ".github/workflows/build.yml",
                    "status": "completed", "conclusion": "success", "html_url": "https://github.com/example/run/123"}
        self.downloads = {self.assets[0]["browser_download_url"]: self.dmg,
                          self.assets[1]["browser_download_url"]: self.sums}

    def asset(self, name, data):
        return {"name": name, "state": "uploaded", "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                "browser_download_url": f"https://github.com/{updater.REPO}/releases/download/{self.tag}/{name}"}

    def api(self, path):
        if path == "releases/latest":
            return self.release
        if path == f"git/ref/tags/{self.tag}":
            return {"object": {"type": "tag", "sha": "b" * 40}}
        if path == "git/tags/" + "b" * 40:
            return {"object": {"type": "commit", "sha": self.commit}}
        if path.startswith("actions/workflows/build.yml/runs?"):
            return {"workflow_runs": [self.run]}
        raise AssertionError(path)

    def verify(self):
        with patch.object(updater, "api_json", side_effect=self.api), patch.object(updater, "fetch", side_effect=lambda url: self.downloads[url]):
            return updater.verified_release()

    def test_valid_annotated_release(self):
        self.assertEqual(self.verify(), {"version": "0.1.38", "sha256": self.digest, "commit": self.commit, "workflow": self.run["html_url"]})

    def test_unpublished_and_nonstable_releases_rejected(self):
        for key, value in [("draft", True), ("prerelease", True), ("published_at", None), ("tag_name", "v0.1.38-rc1"), ("tag_name", "v00.1.38")]:
            with self.subTest(key=key, value=value):
                original = self.release[key]
                self.release[key] = value
                with self.assertRaises(ValueError):
                    self.verify()
                self.release[key] = original

    def test_failed_or_unrelated_workflow_rejected(self):
        for key, value in [("conclusion", "failure"), ("status", "in_progress"), ("head_sha", "c" * 40), ("head_branch", "feature"), ("event", "push"), ("path", ".github/workflows/other.yml")]:
            with self.subTest(key=key):
                original = self.run[key]
                self.run[key] = value
                with self.assertRaises(ValueError):
                    self.verify()
                self.run[key] = original

    def test_unsafe_missing_or_duplicate_asset_rejected(self):
        for key, value in [("browser_download_url", "https://example.com/payload.dmg"), ("digest", ""), ("state", "new")]:
            with self.subTest(key=key):
                original = self.assets[0][key]
                self.assets[0][key] = value
                with self.assertRaises(ValueError):
                    self.verify()
                self.assets[0][key] = original
        self.assets.append(copy.deepcopy(self.assets[0]))
        with self.assertRaises(ValueError):
            self.verify()

    def test_corrupt_download_rejected(self):
        for asset in self.assets:
            with self.subTest(asset=asset["name"]):
                url = asset["browser_download_url"]
                original = self.downloads[url]
                self.downloads[url] = b"tampered bytes"
                with self.assertRaises(ValueError):
                    self.verify()
                self.downloads[url] = original

    def test_checksums_must_have_one_matching_dmg(self):
        for sums in [b"malformed", self.sums * 2, f"{'0' * 64}  {self.name}\n".encode(), f"{self.digest}  another.dmg\n".encode()]:
            with self.subTest(sums=sums):
                self.assets[1] = self.asset("SHA256SUMS", sums)
                self.downloads[self.assets[1]["browser_download_url"]] = sums
                with self.assertRaises(ValueError):
                    self.verify()


class CaskTests(unittest.TestCase):
    def setUp(self):
        self.text = 'cask "filen-menubar" do\n  version "0.1.37"\n  sha256 "' + 'a' * 64 + '"\n  app "Filen Menubar.app"\nend\n'

    def test_only_version_and_digest_change(self):
        result = updater.updated_cask(self.text, {"version": "0.1.38", "sha256": "b" * 64})
        self.assertEqual(result, self.text.replace('"0.1.37"', '"0.1.38"').replace('"' + 'a' * 64 + '"', '"' + 'b' * 64 + '"'))

    def test_current_release_is_idempotent(self):
        self.assertEqual(updater.updated_cask(self.text, {"version": "0.1.37", "sha256": "a" * 64}), self.text)

    def test_downgrade_rewrite_and_invalid_version_fail(self):
        for release in [{"version": "0.1.36", "sha256": "a" * 64}, {"version": "0.1.37", "sha256": "b" * 64}, {"version": "0.1.38\ninjected", "sha256": "a" * 64}, {"version": "0.1.38", "sha256": "invalid"}]:
            with self.subTest(release=release), self.assertRaises(ValueError):
                updater.updated_cask(self.text, release)


if __name__ == "__main__":
    unittest.main()
