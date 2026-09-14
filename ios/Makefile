# queer-tv-guide/ios — build and test from the command line.
#
# No CocoaPods, no third-party SPM packages: `xcodegen generate` regenerates
# QueerTVGuide.xcodeproj from project.yml (the project file itself is
# derived and can be safely deleted and regenerated; it is still committed
# so `xcodebuild` works without xcodegen installed).

SCHEME := QueerTVGuide
PROJECT := QueerTVGuide.xcodeproj
SIMULATOR := platform=iOS Simulator,name=iPhone 17 Pro

.PHONY: generate package-test build test test-unit test-ui clean

# Regenerate QueerTVGuide.xcodeproj from project.yml. Requires xcodegen
# (`brew install xcodegen`); only needed after editing project.yml or
# adding/removing files — not for every build.
generate:
	xcodegen generate

# GuideCore (the data/decoding/search/favourites layer) is a plain Swift
# package and the fastest test loop: no simulator boot, runs on macOS.
package-test:
	cd GuideCore && swift test

# Full app build for the simulator.
build:
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

test-ui:
	xcodebuild -project $(PROJECT) -scheme $(SCHEME) \
		-destination '$(SIMULATOR)' -configuration Debug \
		-only-testing:QueerTVGuideUITests test

clean:
	xcodebuild -project $(PROJECT) -scheme $(SCHEME) clean
	cd GuideCore && rm -rf .build
