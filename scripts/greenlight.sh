#!/usr/bin/env bash
# The `greenlight` gate: Greenlight's static App Store preflight over the iOS
# app and widget targets (CI-CD-STANDARD §9: `make greenlight` is what
# `make verify` and the pipeline CI job both run).
#
# Pinned scanner: Greenlight v0.2.0 (github.com/RevylAI/greenlight, MIT),
# commit db0ec50f0f8bdefc8d3d4e525cb935f2ef9014c5 (the v0.2.0 tag's commit).
# Why a source install instead of a release-binary download: `go install` of
# a commit is resolved by the Go module proxy and its module hash is checked
# against the Go checksum database, and this script then checks the built
# binary's recorded module hash against GL_MODULE_HASH below, so a moved tag
# or a swapped proxy copy fails closed. The install is never `@latest`.
# To bump: change GL_COMMIT, GL_VERSION and GL_MODULE_HASH together (the hash
# is the `mod` line of `go version -m <binary>`), and re-run tests/.
#
# Only the static `preflight` command runs. It reads local files: no account,
# no network, no upload. The `scan` (App Store Connect) command and the
# `--verify` flag (which sends flows to a third-party cloud device) are never
# used; tests/test_greenlight_gate.py fails if this file mentions them in a
# command line.
#
# Scope: ios/QueerTVGuide and ios/QueerTVGuideWidgets, each scanned as its
# own project root. Not the repository root: Greenlight's privacy scanner
# greps every .swift file, tests included, and
# ios/GuideCore/Tests/GuideCoreTests/SourceTreeGuardTests.swift names the
# Required Reason APIs on purpose, which reads as undeclared use (false
# CRITICALs). Its `.greenlight.yml` ignore list applies to the code scan only.
# Each target is copied to build/greenlight/stage/ with ios/greenlight.yml as
# its .greenlight.yml (one waiver, below) so nothing is added inside the
# Xcode source folders.
#
# The waiver (ios/greenlight.yml): rule iap-no-restore is a regex for the word
# "StoreKit"; App/ReviewRequest.swift imports it only for SwiftUI's
# requestReview (DECISIONS 0017). The file is waived by path, so the rule
# still fires on any other file; make appstore forbids every purchase API.
#
# Failure: `--exit-code` fails on any CRITICAL or HIGH finding and on a
# scanner crash; so does a report that is missing or says passed:false.
# WARN and INFO findings are printed, not gating. The widget's INFO about
# ITSAppUsesNonExemptEncryption is left as is: the app declares the key
# through INFOPLIST_KEY_ in ios/Config/Product.xcconfig (checked by
# make appstore), which is what App Store Connect asks about per upload.
#
# Not installable (no Go, no network): locally the gate prints
# "SKIPPED: greenlight not installed", writes $GREENLIGHT_OUT/SKIPPED, exits 0,
# and `make verify`'s summary then reports it as skipped, not passed. When CI
# or GITHUB_ACTIONS is set, a skip is an error.
#
# Environment (tests use these): GREENLIGHT_SRC (default ios), GREENLIGHT_OUT
# (default build/greenlight), GREENLIGHT_CONFIG (default ios/greenlight.yml),
# QTG_TOOLS_DIR (tool cache, shared with scripts/fetch-tool.sh).
set -euo pipefail

GL_VERSION=v0.2.0
GL_COMMIT=db0ec50f0f8bdefc8d3d4e525cb935f2ef9014c5
GL_MODULE_HASH=h1:IqoEUPzz+JV4C0jd4Lfbg/VoHZRT+CBxNlOIDkXban4=
GL_TARGETS="QueerTVGuide QueerTVGuideWidgets"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src="${GREENLIGHT_SRC:-$root/ios}"
out="${GREENLIGHT_OUT:-$root/build/greenlight}"
config="${GREENLIGHT_CONFIG:-$root/ios/greenlight.yml}"
cache="${QTG_TOOLS_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/queer-tv-guide-tools}"
dir="$cache/greenlight-$GL_VERSION-${GL_COMMIT:0:12}"
bin="$dir/greenlight"

mkdir -p "$out"
rm -f "$out/SKIPPED"

skip() {
  echo "greenlight: $1" >&2
  if [ -n "${CI:-}" ] || [ -n "${GITHUB_ACTIONS:-}" ]; then
    echo "greenlight: not installed, and a skip is a failure in CI" >&2
    exit 1
  fi
  echo "SKIPPED: greenlight not installed"
  echo "$1" > "$out/SKIPPED"
  exit 0
}

install_pinned() {
  command -v go >/dev/null 2>&1 || return 1
  local tmp
  tmp="$(mktemp -d "$cache/tmp.XXXXXX")"
  trap 'rm -rf "$tmp"' RETURN
  GOTOOLCHAIN="${GOTOOLCHAIN:-local}" GOBIN="$tmp" \
    go install "github.com/RevylAI/greenlight/cmd/greenlight@$GL_COMMIT" || return 1
  local recorded
  recorded="$(go version -m "$tmp/greenlight" | awk '$1 == "mod" {print $2, $3, $4}')"
  if [ "$recorded" != "github.com/RevylAI/greenlight $GL_VERSION $GL_MODULE_HASH" ]; then
    echo "greenlight: built module '$recorded' != pinned $GL_VERSION $GL_MODULE_HASH" >&2
    exit 1
  fi
  mkdir -p "$dir"
  mv "$tmp/greenlight" "$bin"
  touch "$dir/.verified"
}

if [ ! -x "$bin" ] || [ ! -f "$dir/.verified" ]; then
  mkdir -p "$cache"
  install_pinned || skip "could not install greenlight $GL_VERSION (needs Go and network)"
fi

stage="$out/stage"
rm -rf "$stage"
status=0
for target in $GL_TARGETS; do
  if [ ! -d "$src/$target" ]; then
    echo "greenlight: $src/$target is not a directory" >&2
    exit 1
  fi
  mkdir -p "$stage"
  cp -R "$src/$target" "$stage/$target"
  cp "$config" "$stage/$target/.greenlight.yml"
  report="$out/$target.json"
  rm -f "$report"
  echo "greenlight: preflight $target ($GL_VERSION)"
  rc=0
  "$bin" preflight "$stage/$target" --exit-code --format json --output "$report" || rc=$?
  if [ ! -s "$report" ]; then
    echo "greenlight: $target wrote no report (exit $rc)" >&2
    status=1
    continue
  fi
  # One summary line per report, taken from the report itself.
  counts="$(tr -d ' \n' < "$report" | grep -o '"summary":{[^}]*}' || true)"
  echo "greenlight: $target $counts"
  if [ "$rc" -ne 0 ] || ! grep -Eq '"passed": *true' "$report"; then
    echo "greenlight: $target FAILED (exit $rc); findings in $report:" >&2
    grep -E '"(severity|title|file)"' "$report" >&2 || true
    status=1
  fi
done
rm -rf "$stage"
exit "$status"
