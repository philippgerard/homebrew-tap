cask "filen-menubar" do
  version "0.1.37"
  sha256 "79d9a2a87a9ef6acf8e48791035f7ab17dacdd02113afc8eec6191d070fbd88d"

  url "https://github.com/philippgerard/filen-menubar/releases/download/v#{version}/Filen.Menubar_#{version}_aarch64.dmg"
  name "Filen Menubar"
  desc "Menu bar controller for Filen cloud sync"
  homepage "https://github.com/philippgerard/filen-menubar"

  livecheck do
    url :url
    strategy :github_latest
  end

  depends_on arch: :arm64
  depends_on macos: :ventura

  app "Filen Menubar.app"

  uninstall quit: "io.filen.menubar"

  zap trash: [
    "~/Library/Caches/io.filen.menubar",
    "~/Library/Logs/io.filen.menubar",
    "~/Library/Saved Application State/io.filen.menubar.savedState",
  ]
end
