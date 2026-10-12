#!/usr/bin/env bash
# Boots the simulator an xcodebuild destination names and waits until it has
# finished booting, then prints its UDID. `make test-a11y` runs this first and
# tests on `id=<that UDID>`, so the device booted is the device tested.
#
# Why: inside `xcodebuild test` the simulator boots on demand, and the first
# test pays for it. In CI the first app launch took 7 to 59 s, near XCTest's
# 60-second launch limit, and once it failed ("Failed to launch", "Failed to
# send signal 19", run 36977058690). Booting first takes that out of the test.
#
# Usage: boot-simulator.sh 'platform=iOS Simulator,name=iPhone 17 Pro,OS=26.5'
#    or: boot-simulator.sh 'platform=iOS Simulator,id=<udid>'
set -euo pipefail

destination="${1:?usage: boot-simulator.sh '<xcodebuild destination>'}"
name="" os="" udid=""
IFS=',' read -r -a fields <<< "$destination"
for field in "${fields[@]}"; do
  case "$field" in
    id=*) udid="${field#id=}" ;;
    name=*) name="${field#name=}" ;;
    OS=*) os="${field#OS=}" ;;
  esac
done

if [ -z "$udid" ]; then
  [ -n "$name" ] || { echo "boot-simulator: no name= or id= in '$destination'" >&2; exit 1; }
  # The first available device with that name, on the iOS runtime named by
  # OS= when there is one (runtime keys look like ...SimRuntime.iOS-26-5).
  udid="$(xcrun simctl list devices available -j | python3 -c '
import json, sys
name, os_version = sys.argv[1], sys.argv[2]
runtime_suffix = "iOS-" + os_version.replace(".", "-") if os_version else None
for runtime, devices in json.load(sys.stdin)["devices"].items():
    if runtime_suffix and not runtime.endswith(runtime_suffix):
        continue
    for device in devices:
        if device["name"] == name:
            print(device["udid"])
            sys.exit(0)
' "$name" "$os")" || true
  [ -n "$udid" ] || { echo "boot-simulator: no available '$name' simulator${os:+ on iOS $os}" >&2; exit 1; }
fi

# "Unable to boot device in current state: Booted" is not an error here.
xcrun simctl boot "$udid" >/dev/null 2>&1 || true
xcrun simctl bootstatus "$udid" -b >&2
echo "$udid"
