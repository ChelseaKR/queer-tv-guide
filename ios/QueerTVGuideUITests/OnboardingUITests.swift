import XCTest

/// The first-run screen (OnboardingView): shown on a fresh install, skippable
/// at once, not shown again, and reachable from About. Every other UI test
/// starts past it (`XCUIApplication.skipOnboarding`).
final class OnboardingUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    /// A launch that forgets any earlier choice: the argument domain wins
    /// over what a previous test stored.
    @MainActor
    private func launchFresh() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += ["-onboarding.v1.seen", "NO"]
        app.launch()
        return app
    }

    @MainActor
    func testFirstRunExplainsSpoilersSourcesAndPrivacyAndCanBeSkipped() throws {
        let app = launchFresh()
        XCTAssertTrue(app.staticTexts["onboarding-point-spoilers"].waitForExistence(timeout: 30), "no first-run screen")
        for id in ["not-recorded", "sources", "privacy"] {
            XCTAssertTrue(app.staticTexts["onboarding-point-\(id)"].exists, "no \(id) point")
        }
        // Names both sources and the non-endorsement, by name.
        let text = app.staticTexts.allElementsBoundByIndex.map(\.label).joined(separator: " ")
        for needle in ["LezWatch.TV", "TVmaze", "CC BY-SA 4.0", "do not endorse this app", "Not recorded"] {
            XCTAssertTrue(text.contains(needle), "the first-run screen does not say \(needle)")
        }
        XCTAssertFalse(app.tabBars.buttons["Search"].exists, "the tabs are showing under the first-run screen")

        app.buttons["Skip"].tap()
        XCTAssertTrue(app.tabBars.buttons["Search"].waitForExistence(timeout: 30), "Skip did not reach Search")
    }

    /// Finishing once is remembered: the next launch starts on Search.
    @MainActor
    func testFinishingIsRemembered() throws {
        let app = launchFresh()
        let finish = app.buttons["onboarding-finish"]
        XCTAssertTrue(finish.waitForExistence(timeout: 30))
        for _ in 0..<6 where !finish.isHittable { app.swipeUp() }
        finish.tap()
        XCTAssertTrue(app.tabBars.buttons["Search"].waitForExistence(timeout: 30))
        app.terminate()

        // No argument this time: the stored value decides.
        let again = XCUIApplication()
        again.launch()
        XCTAssertTrue(again.tabBars.buttons["Search"].waitForExistence(timeout: 30), "the first-run screen came back")
        XCTAssertFalse(again.staticTexts["onboarding-point-spoilers"].exists)
    }

    @MainActor
    func testAboutOpensItAgain() throws {
        let app = XCUIApplication.launchedGuide()
        app.tabBars.buttons["About"].tap()
        XCTAssertTrue(app.staticTexts["Privacy"].waitForExistence(timeout: 30))
        let open = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'How ' AND label ENDSWITH ' works'")).firstMatch
        for _ in 0..<10 where !(open.exists && open.isHittable) { app.swipeUp() }
        XCTAssertTrue(open.waitForExistence(timeout: 30))
        open.tap()
        XCTAssertTrue(app.staticTexts["onboarding-point-spoilers"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["Skip"].exists, "a reopened introduction offers Skip")
        let done = app.buttons["onboarding-finish"]
        for _ in 0..<6 where !done.isHittable { app.swipeUp() }
        done.tap()
        // Back on About, still scrolled to its last row (a List may not keep
        // the Privacy heading, far above, in the tree).
        XCTAssertTrue(app.staticTexts["onboarding-point-spoilers"].waitForNonExistence(timeout: 10), "Done did not close the introduction")
        XCTAssertTrue(open.waitForExistence(timeout: 10), "Done did not return to About")
    }
}
