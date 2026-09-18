# queer-tv-guide/ios — build and test from the command line.
#
# No CocoaPods, no third-party SPM packages: `xcodegen generate` regenerates
# QueerTVGuide.xcodeproj from project.yml (the project file itself is
# derived and can be safely deleted and regenerated; it is still committed
# so `xcodebuild` works without xcodegen installed).

SCHEME := QueerTVGuide
PROJECT := QueerTVGuide.xcodeproj
SIMULATOR := platform=iOS Simulator,name=iPhone 17 Pro

# The one published snapshot URL (schema/README.md, "Where the file is
# published") and the copy the app bundles as its first-launch/offline data.
SNAPSHOT_URL := https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json
BUNDLED_SNAPSHOT := QueerTVGuide/Resources/snapshot.v1.json

.PHONY: generate package-test build test test-unit test-ui clean bundle-snapshot

# Regenerate QueerTVGuide.xcodeproj from project.yml. Requires xcodegen
# (`brew install xcodegen`); only needed after editing project.yml or
# adding/removing files — not for every build.
generate:
	xcodegen generate

# GuideCore (the data/decoding/search/favourites layer) is a plain Swift
# package and the fastest test loop: no simulator boot, runs on macOS.
package-test: $(BUNDLED_SNAPSHOT)
	cd GuideCore && swift test

# Full app build for the simulator.
build: $(BUNDLED_SNAPSHOT)
	xcodebuild -project $(PROJECT) -scheme $(SCHEME) \
		-destination '$(SIMULATOR)' -configuration Debug build

# Everything: GuideCore package tests, then the app's unit + UI tests in
# the simulator (XCTest, including the negative-control assertions in
# SourceTreeGuardTests and SnapshotDecoderTests).
test: package-test
	xcodebuild -project $(PROJECT) -scheme $(SCHEME) \
		-destination '$(SIMULATOR)' -configuration Debug test

# Just the hosted unit tests (GuideCoreTests + QueerTVGuideTests), skipping
# the slower UI smoke tests.
test-unit: package-test
	xcodebuild -project $(PROJECT) -scheme $(SCHEME) \
		-destination '$(SIMULATOR)' -configuration Debug \
		-only-testing:QueerTVGuideTests test

test-ui: $(BUNDLED_SNAPSHOT)
	xcodebuild -project $(PROJECT) -scheme $(SCHEME) \
		-destination '$(SIMULATOR)' -configuration Debug \
		-only-testing:QueerTVGuideUITests test

clean:
	xcodebuild -project $(PROJECT) -scheme $(SCHEME) clean
	cd GuideCore && rm -rf .build

# The bundled snapshot is gitignored (see the root .gitignore): fetch it the
# first time anything needs it. `make bundle-snapshot` refreshes it on demand.
$(BUNDLED_SNAPSHOT):
	$(MAKE) bundle-snapshot

# Replace the bundled snapshot with the pipeline's latest PUBLISHED one, byte
# for byte: the same bytes anyone can fetch under CC BY-SA 4.0, which is what
# docs/LICENSES-AND-ATTRIBUTION.md says ships inside the app. Checks the
# published .sha256 and refuses a hand-made fixture or a locally built file
# (no workflow run id). GuideCore's BundledSnapshotTests re-check the result
# on every `swift test`. Run before every archive (docs/APP-STORE.md §5).
bundle-snapshot:
	@tmp=$$(mktemp -d) && trap 'rm -rf "$$tmp"' EXIT && \
	curl -fsS --compressed -o "$$tmp/snapshot.v1.json" "$(SNAPSHOT_URL)" && \
	curl -fsS -o "$$tmp/snapshot.v1.json.sha256" "$(SNAPSHOT_URL).sha256" && \
	want=$$(awk '{print $$1}' "$$tmp/snapshot.v1.json.sha256") && \
	got=$$(shasum -a 256 "$$tmp/snapshot.v1.json" | awk '{print $$1}') && \
	if [ -z "$$want" ] || [ "$$want" != "$$got" ]; then echo "bundle-snapshot: sha256 mismatch (published '$$want', downloaded '$$got')" >&2; exit 1; fi && \
	python3 -c 'import json, sys; d = json.load(open(sys.argv[1])); b = d["build"]; assert d["schema_version"] == "1", "schema_version is not 1"; assert "fixture" not in b["pipeline_version"], "refusing a fixture"; assert b["run"]["workflow_run_id"], "refusing a snapshot with no workflow run id (not published by the nightly workflow)"; print("bundle-snapshot: %d shows, %d characters, generated_at %s, pipeline %s, run %s" % (len(d["shows"]), len(d["characters"]), d["generated_at"], b["pipeline_version"], b["run"]["workflow_run_id"]))' "$$tmp/snapshot.v1.json" && \
	mkdir -p "$(dir $(BUNDLED_SNAPSHOT))" && \
	cp "$$tmp/snapshot.v1.json" "$(BUNDLED_SNAPSHOT)" && \
	echo "bundle-snapshot: wrote $(BUNDLED_SNAPSHOT) (sha256 $$got)"
