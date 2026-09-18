#!/usr/bin/env bash
# Download one pinned scanner binary, verify its SHA-256, and print its path.
# Used by the root Makefile, so `make verify` and CI run the exact same bytes
# (CI-CD-STANDARD §9, CICD-27).
#
#   scripts/fetch-tool.sh gitleaks      -> <cache>/gitleaks-8.30.1/gitleaks
#   scripts/fetch-tool.sh osv-scanner   -> <cache>/osv-scanner-2.6.0/osv-scanner
#
# <cache> is $QTG_TOOLS_DIR, else ${XDG_CACHE_HOME:-$HOME/.cache}/queer-tv-guide-tools:
# outside the checkout, so nothing downloaded can be committed by accident and
# every worktree shares one verified copy.
#
# The digests below were copied from each release's own checksums file
# (gitleaks_8.30.1_checksums.txt, osv-scanner_SHA256SUMS) on 2026-09-17.
# A mismatch, an unknown platform, or a failed download exits non-zero and
# prints nothing on stdout, so a caller that captures the path fails closed.
# To bump a tool: change its version AND every digest in the same commit.
set -euo pipefail

tool="${1:?usage: fetch-tool.sh <gitleaks|osv-scanner>}"
cache="${QTG_TOOLS_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/queer-tv-guide-tools}"

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) plat=linux-x64 ;;
  Linux-aarch64 | Linux-arm64) plat=linux-arm64 ;;
  Darwin-arm64) plat=darwin-arm64 ;;
  Darwin-x86_64) plat=darwin-x64 ;;
  *) echo "fetch-tool: unsupported platform $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac

case "$tool" in
  gitleaks)
    version=8.30.1
    case "$plat" in
      linux-x64) asset=gitleaks_${version}_linux_x64.tar.gz; sha=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb ;;
      linux-arm64) asset=gitleaks_${version}_linux_arm64.tar.gz; sha=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080 ;;
      darwin-arm64) asset=gitleaks_${version}_darwin_arm64.tar.gz; sha=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 ;;
      darwin-x64) asset=gitleaks_${version}_darwin_x64.tar.gz; sha=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 ;;
    esac
    url="https://github.com/gitleaks/gitleaks/releases/download/v${version}/${asset}"
    ;;
  osv-scanner)
    version=2.6.0
    case "$plat" in
      linux-x64) asset=osv-scanner_linux_amd64; sha=ca69b3d3cd08f889a49dc0a383122f71cc528b83803671df5fd874d97485b108 ;;
      linux-arm64) asset=osv-scanner_linux_arm64; sha=2c71403eb443d05891c4f268c3ad771cf4f16e5443463fd7851ef8f454d3c7e4 ;;
      darwin-arm64) asset=osv-scanner_darwin_arm64; sha=98c460dcd37de25819babd757d04542045b6243113e209edcd4d89fedb0256b4 ;;
      darwin-x64) asset=osv-scanner_darwin_amd64; sha=60c5296637e977b28eeda5c7f13573e447659a632922737f94d11fa7e30ad6ca ;;
    esac
    url="https://github.com/google/osv-scanner/releases/download/v${version}/${asset}"
    ;;
  *) echo "fetch-tool: unknown tool $tool" >&2; exit 1 ;;
esac

dir="$cache/$tool-$version"
bin="$dir/$tool"
if [ -x "$bin" ] && [ -f "$dir/.verified" ]; then
  echo "$bin"
  exit 0
fi

mkdir -p "$dir"
tmp="$(mktemp "$dir/download.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
curl --proto '=https' --tlsv1.2 -sSfL "$url" -o "$tmp"

if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "$tmp" | cut -d' ' -f1)"
else
  actual="$(shasum -a 256 "$tmp" | cut -d' ' -f1)"
fi
if [ "$actual" != "$sha" ]; then
  echo "fetch-tool: $asset sha256 $actual != pinned $sha" >&2
  exit 1
fi

case "$asset" in
  *.tar.gz) tar -xzf "$tmp" -C "$dir" "$tool" ;;
  *) cp "$tmp" "$bin" ;;
esac
chmod +x "$bin"
touch "$dir/.verified"
echo "$bin"
