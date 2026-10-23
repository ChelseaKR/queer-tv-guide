# queer-tv-guide/android: build, test and lint the Android app from the
# command line (DECISIONS 0018). Gradle drives the build; this file exposes
# the gates the root Makefile and CI run, as ios/Makefile does for iOS.
#
# Needs a JDK (17 or newer; CI uses 21) and the Android SDK with platform 36
# (ANDROID_HOME, or sdk.dir in local.properties). The Gradle wrapper fetches
# Gradle itself, checksum-pinned in gradle/wrapper/gradle-wrapper.properties.

SHELL := bash
.SHELLFLAGS := -euo pipefail -c

GRADLE := ./gradlew --console=plain --no-daemon

# The one published snapshot URL (schema/README.md) and the copy the app
# bundles as its first-launch and offline data: the same bytes iOS bundles.
SNAPSHOT_URL := https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json
BUNDLED_SNAPSHOT := app/src/main/assets/snapshot.v1.json

.PHONY: verify test lint build bundle-snapshot instrumented screenshots

# Every Android gate CI runs: the JVM tests (core's parity with GuideCore,
# the decoder's rules, the reminder planner, the real snapshot, the source
# guard), Android lint with warnings as errors, and a release build (R8 on).
verify: $(BUNDLED_SNAPSHOT)
	$(GRADLE) :core:test :app:testDebugUnitTest :app:lintRelease :app:assembleRelease

test: $(BUNDLED_SNAPSHOT)
	$(GRADLE) :core:test :app:testDebugUnitTest

lint: $(BUNDLED_SNAPSHOT)
	$(GRADLE) :app:lintRelease

build: $(BUNDLED_SNAPSHOT)
	$(GRADLE) :app:assembleDebug :app:assembleRelease

# The on-device tests (a running emulator or device): the spoiler reveal
# under TalkBack's tree, the device's own date formatting against the parity
# file, deep links, and the screenshot tour. Local, not in CI (emulators on
# hosted runners are slow and flaky; see DECISIONS 0018).
instrumented: $(BUNDLED_SNAPSHOT)
	$(GRADLE) :app:connectedDebugAndroidTest

$(BUNDLED_SNAPSHOT):
	$(MAKE) bundle-snapshot

# Replace the bundled snapshot with the pipeline's latest PUBLISHED one, byte
# for byte, as ios/Makefile's bundle-snapshot does: checks the published
# .sha256 and refuses a fixture or a locally built file.
bundle-snapshot:
	@tmp=$$(mktemp -d) && trap 'rm -rf "$$tmp"' EXIT && \
	curl -fsSL --max-redirs 3 --proto-redir =https --compressed -o "$$tmp/snapshot.v1.json" "$(SNAPSHOT_URL)" && \
	curl -fsSL --max-redirs 3 --proto-redir =https -o "$$tmp/snapshot.v1.json.sha256" "$(SNAPSHOT_URL).sha256" && \
	want=$$(awk '{print $$1}' "$$tmp/snapshot.v1.json.sha256") && \
	got=$$( (sha256sum "$$tmp/snapshot.v1.json" 2>/dev/null || shasum -a 256 "$$tmp/snapshot.v1.json") | awk '{print $$1}') && \
	if [ -z "$$want" ] || [ "$$want" != "$$got" ]; then echo "bundle-snapshot: sha256 mismatch (published '$$want', downloaded '$$got')" >&2; exit 1; fi && \
	python3 -c 'import json, sys; d = json.load(open(sys.argv[1])); b = d["build"]; assert d["schema_version"] == "1", "schema_version is not 1"; assert "fixture" not in b["pipeline_version"], "refusing a fixture"; assert b["run"]["workflow_run_id"], "refusing a snapshot with no workflow run id"; print("bundle-snapshot: %d shows, %d characters, generated_at %s" % (len(d["shows"]), len(d["characters"]), d["generated_at"]))' "$$tmp/snapshot.v1.json" && \
	mkdir -p "$(dir $(BUNDLED_SNAPSHOT))" && \
	cp "$$tmp/snapshot.v1.json" "$(BUNDLED_SNAPSHOT)" && \
	echo "bundle-snapshot: wrote $(BUNDLED_SNAPSHOT) (sha256 $$got)"
