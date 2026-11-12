#!/bin/bash
set -euo pipefail

# Installation/removal may quit an app with this bundle ID. Only use an
# ephemeral GitHub-hosted runner, never an operator's logged-in workstation.
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted ]] || {
  echo 'This installation check requires an ephemeral GitHub-hosted runner.' >&2
  exit 1
}
[[ "$(uname -m)" == arm64 ]] || { echo 'An Apple Silicon runner is required.' >&2; exit 1; }

root="$(cd "$(dirname "$0")/.." && pwd)"
cask=philippgerard/tap/filen-menubar
app='/Applications/Filen Menubar.app'
[[ ! -e "$app" ]] || { echo 'Refusing to overwrite an existing app.' >&2; exit 1; }
brew tap philippgerard/tap "$root"
# Keep Homebrew's trust identity canonical even though the candidate was cloned
# locally rather than fetched from the published tap.
git -C "$(brew --repository philippgerard/tap)" remote set-url origin https://github.com/philippgerard/homebrew-tap
# The release updater may have changed the cask without committing it yet.
cp "$root/Casks/filen-menubar.rb" "$(brew --repository philippgerard/tap)/Casks/filen-menubar.rb"
brew trust --cask "$cask"
brew style "$cask"
brew audit --cask --online "$cask"
brew install --cask "$cask"

cleanup() { brew uninstall --cask "$cask"; }
trap cleanup EXIT
codesign --verify --deep --strict "$app"
codesign --verify --strict -R '=identifier "io.filen.menubar" and anchor apple generic and certificate leaf[subject.OU] = "7WS855G6D3"' "$app"
spctl --assess --type execute --verbose=2 "$app"
xcrun stapler validate "$app"
"$app/Contents/Helpers/filen-menubar-cli" --version
python3 - "$app" "$(brew info --json=v2 --cask "$cask")" <<'PY'
import json, pathlib, plistlib, sys
app = pathlib.Path(sys.argv[1])
cask = json.loads(sys.argv[2])["casks"][0]
with (app / "Contents/Info.plist").open("rb") as f:
    info = plistlib.load(f)
assert info["CFBundleIdentifier"] == "io.filen.menubar"
assert info["CFBundleShortVersionString"] == cask["version"]
for relative in (
    "Contents/MacOS/filen-menubar",
    "Contents/Helpers/filen-menubar-cli",
    "Contents/Resources/filen-cli/filen-cli.cjs",
    "Contents/Resources/licenses/filen-cli/runtime.cdx.json",
):
    assert (app / relative).is_file(), relative
print("Installed cask version, signing identity and bundled payload verified.")
PY
cleanup
trap - EXIT
[[ ! -e "$app" ]] || { echo 'Uninstall left the app bundle behind.' >&2; exit 1; }
