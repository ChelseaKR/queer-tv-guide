#!/usr/bin/env bash
# App Store screenshots for the iPhone 6.9" class (1320 x 2868), on the real
# bundled snapshot. Creates a throwaway iPhone 17 Pro Max simulator, sets a
# clean status bar, runs AppStoreScreenshotTests, exports the screenshots to
# docs/app-store/screenshots/, checks their size, and deletes the simulator.
# Run from ios/ via `make screenshots`.
set -euo pipefail

DEVICE_TYPE="${SCREENSHOT_DEVICE_TYPE:-iPhone 17 Pro Max}"
WIDTH=1320
HEIGHT=2868
OUT="../docs/app-store/screenshots"
WORK="$(mktemp -d)"
UDID="$(xcrun simctl create "qtg-screenshots" "$DEVICE_TYPE")"
done_ok=0
cleanup() {
  xcrun simctl shutdown "$UDID" >/dev/null 2>&1 || true
  xcrun simctl delete "$UDID" >/dev/null 2>&1 || true
  if [ "$done_ok" = 1 ]; then rm -rf "$WORK"; else echo "screenshots: failed; result bundle kept at $WORK/result.xcresult" >&2; fi
}
trap cleanup EXIT

xcrun simctl boot "$UDID"
xcrun simctl bootstatus "$UDID" -b >/dev/null
xcrun simctl status_bar "$UDID" override --time "9:41" --dataNetwork wifi --wifiMode active --wifiBars 3 \
  --cellularMode active --cellularBars 4 --batteryState charged --batteryLevel 100

if ! TEST_RUNNER_QTG_SCREENSHOTS=1 xcodebuild -quiet \
  -project QueerTVGuide.xcodeproj -scheme QueerTVGuide -configuration Debug \
  -destination "id=$UDID" -derivedDataPath "$WORK/dd" -resultBundlePath "$WORK/result.xcresult" \
  -parallel-testing-enabled NO \
  -only-testing:QueerTVGuideUITests/AppStoreScreenshotTests test; then
  # -quiet hides assertion text; print it from the result bundle.
  xcrun xcresulttool get test-results tests --path "$WORK/result.xcresult" --compact \
    | python3 -c 'import json,sys
def walk(n):
    if n.get("nodeType") == "Failure Message": print("failure:", n.get("name"))
    for c in n.get("children") or []: walk(c)
for t in json.load(sys.stdin).get("testNodes", []): walk(t)' >&2 || true
  exit 1
fi

xcrun xcresulttool export attachments --path "$WORK/result.xcresult" --output-path "$WORK/att" >/dev/null
mkdir -p "$OUT"
python3 - "$WORK/att" "$OUT" "$WIDTH" "$HEIGHT" <<'PY'
import json, shutil, subprocess, sys
att, out, width, height = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
manifest = json.load(open(f"{att}/manifest.json"))
written = []
for test in manifest:
    for a in test.get("attachments", []):
        name = a["suggestedHumanReadableName"]
        if not name.startswith("appstore-"):
            continue
        stem = name[len("appstore-"):].split("_")[0].removesuffix(".png")
        target = f"{out}/{stem}.png"
        shutil.copyfile(f"{att}/{a['exportedFileName']}", target)
        dims = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", target],
                              capture_output=True, text=True, check=True).stdout.split()
        w, h = dims[dims.index("pixelWidth:") + 1], dims[dims.index("pixelHeight:") + 1]
        if (w, h) != (width, height):
            sys.exit(f"{target} is {w}x{h}, not {width}x{height}")
        written.append(target)
if len(written) < 3:
    sys.exit(f"only {len(written)} screenshots were produced")
print("\n".join(sorted(written)))
PY
done_ok=1
