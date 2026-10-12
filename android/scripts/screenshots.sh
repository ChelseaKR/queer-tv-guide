#!/usr/bin/env bash
# The screenshot tour (app/src/androidTest/.../ScreenshotTour.kt) on one
# connected device, in light and dark: installs the debug app and its tests,
# runs the tour twice, and pulls the PNGs into $1 (default: build/screenshots).
# Usage: scripts/screenshots.sh <out-dir> <name>   (name: phone, tablet, ...)
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-build/screenshots}"
name="${2:-device}"
adb="${ANDROID_HOME:-$HOME/Library/Android/sdk}/platform-tools/adb"
pkg=com.chelseakr.queertvguide
./gradlew --console=plain -q :app:installDebug :app:installDebugAndroidTest
mkdir -p "$out"
# An emulator's own "System UI isn't responding" dialog is not the app's; keep it out of the shots.
"$adb" shell settings put global hide_error_dialogs 1
for theme in light dark; do
  if [ "$theme" = dark ]; then "$adb" shell cmd uimode night yes; else "$adb" shell cmd uimode night no; fi
  "$adb" shell am force-stop "$pkg"
  "$adb" shell rm -rf "/sdcard/Android/data/$pkg/files/screenshots"
  "$adb" shell am instrument -w -e class "$pkg.ScreenshotTour" -e shotPrefix "$name-$theme" \
    "$pkg.test/androidx.test.runner.AndroidJUnitRunner" | tee "$out/$name-$theme-instrument.log"
  if grep -qE 'FAILURES|Process crashed|INSTRUMENTATION_FAILED' "$out/$name-$theme-instrument.log"; then
    echo "screenshots: the $theme tour failed on $name" >&2
    exit 1
  fi
  "$adb" pull "/sdcard/Android/data/$pkg/files/screenshots/." "$out/" >/dev/null
done
"$adb" shell cmd uimode night no
ls "$out"/"$name"-*.png | wc -l | xargs echo "screenshots: pulled for $name:"
