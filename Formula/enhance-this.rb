# Formula/enhance-this.rb
class EnhanceThis < Formula
  include Language::Python::Virtualenv

  desc "CLI tool to enhance prompts using Ollama AI"
  homepage "https://github.com/hariharen9/enhance-this"
  # url "https://pypi.io/packages/source/e/enhance-this/enhance-this-0.1.0.tar.gz" # <-- TODO: Update with real URL on first release
  # sha256 "..." # <-- TODO: Update with real hash on first release
  url "https://github.com/hariharen9/enhance-this/archive/v0.1.0.tar.gz" # Placeholder
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # Placeholder

  depends_on "python@3.11"

  resource "click" do
    url "https://pypi.io/packages/source/c/click/click-8.1.7.tar.gz"
    sha256 "ca9853ad459e78b31683208753b81ece57b6b4863e0330d93a8a47e08b485497"
  end

  resource "requests" do
    url "https://pypi.io/packages/source/r/requests/requests-2.31.0.tar.gz"
    sha256 "942c3a62805036524852309990243c27a03575b2342c06f735638df83343ed91"
  end

  resource "pyyaml" do
    url "https://pypi.io/packages/source/P/PyYAML/PyYAML-6.0.1.tar.gz"
    sha256 "565d219cb938e6c18298551b4a4b39709b3f0a54218e4a855a45dc1b8a2c8a5b"
  end

  resource "pyperclip" do
    url "https://pypi.io/packages/source/p/pyperclip/pyperclip-1.8.2.tar.gz"
    sha256 "b9c60536f60b2a157b4f67c3c15c11c053f745344c365534403c95a89c0013c7"
  end

  resource "rich" do
    url "https://pypi.io/packages/source/r/rich/rich-13.7.1.tar.gz"
    sha256 "a2d38e15f2a3648427a0f423e0651412a6b797153a5471f03f3139a625591ce7"
  end

  resource "questionary" do
    url "https://pypi.io/packages/source/q/questionary/questionary-2.0.1.tar.gz"
    sha256 "313461388279236405d834b9c3699018a4646435415c668b8a3a663c45148668"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/enhance", "--version"
  end
end
