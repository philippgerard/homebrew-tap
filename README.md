# Homebrew tap

Install [Filen Menubar](https://github.com/philippgerard/filen-menubar), a native
menu bar app for Filen cloud sync:

```sh
brew install --cask philippgerard/tap/filen-menubar
```

This installs the upstream signed and notarized application, including its
private sync backend and Node runtime. No separate Filen CLI or Node install is
needed. The current macOS release supports Apple Silicon and macOS 13.5 or newer.
On Homebrew 6 and newer, the fully qualified installation trusts this cask only.

Quit the app before upgrading, then reopen it:

```sh
brew update
brew upgrade --cask filen-menubar
open -a 'Filen Menubar'
```

If a launch agent manages the app, stop that agent before upgrading and restart
it after verifying the new bundle. Homebrew updates the app on disk; it does not
replace a running process. Login-at-startup remains a separate user setting.

## Existing installations

Before the first Homebrew install, quit the existing app and move its bundle
out of `/Applications` to a backup location. Homebrew will then install and own
`/Applications/Filen Menubar.app`. Preserve the app's configuration and the
Filen CLI login/state directories. Do not run two sync engines against the same
sync pair. Users of `mac-setup` should follow its migration runbook to retire
the old Nix-store launcher and Home Manager app copy.

`brew uninstall --cask filen-menubar` removes the app, not your synced files,
configuration or login state. Even `--zap` only removes caches, logs and saved
window state; it deliberately preserves configuration and credentials.

## Release updates

The `Update cask` workflow checks every six hours while GitHub keeps its
schedule enabled (see below), or on manual dispatch. It requires a published
stable release, a successful upstream release workflow
from `main` at the exact tagged commit, matching GitHub asset digests and
`SHA256SUMS`, and a checksum-verified DMG. Before publishing the bump, macOS CI
audits the cask, installs it, verifies the expected signing team and bundle ID,
checks Gatekeeper, and tests removal without launching the sync engine.

Only validated version/checksum changes are pushed to this tap. The workflow
uses this repository's short-lived `GITHUB_TOKEN`; no cross-repository write
token is required. Homebrew's `livecheck` can also discover upstream releases,
but detection alone does not publish a cask update.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/update-cask.py --check
brew style Casks/filen-menubar.rb
```

`--check` verifies the latest upstream release and reports whether the cask
needs an update, without changing it. The updater fails closed on missing
release evidence, a changed asset for an already packaged version, or a
downgrade. The upstream release workflow runs only from `main`, so dispatch it
while the tagged commit is still the tip of `main`. If `main` has already
advanced, that release cannot be published automatically; publish a new
reviewed release from the current `main` tip instead.

GitHub disables scheduled workflows in public repositories after 60 days
without repository activity. If that happens, re-enable `Update cask` on the
Actions page (or `gh workflow enable update.yml`), then run it once with
`gh workflow run update.yml`.
