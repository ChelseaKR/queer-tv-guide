import XCTest

/// The first-run pager (OnboardingView): shown on a fresh install, five
/// pages reached with Next (or a swipe), skippable at once, not shown again,
/// and reachable from About. Every other UI test starts past it
/// (`XCUIApplication.skipOnboarding`).
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

    /// Taps Next until the last page, collecting every text on the way.
    @MainActor
    @discardableResult
    private func nextToTheEnd(_ app: XCUIApplication) -> String {
        var text = app.staticTexts.allElementsBoundByIndex.map(\.label).joined(separator: " ")
        let next = app.buttons["onboarding-next"]
        for _ in 0..<4 {
            XCTAssertTrue(next.waitForExistence(timeout: 10), "no Next button")
            next.tap()
            _ = app.staticTexts.firstMatch.waitForExistence(timeout: 5)
            text += " " + app.staticTexts.allElementsBoundByIndex.map(\.label).joined(separator: " ")
        }
        XCTAssertFalse(next.exists, "Next is still offered on the last page")
        return text
    }

    @MainActor
    func testFirstRunExplainsSpoilersSourcesAndPrivacyAndCanBeSkipped() throws {
        let app = launchFresh()
        XCTAssertTrue(app.staticTexts["onboarding-welcome"].waitForExistence(timeout: 30), "no first-run screen")
        XCTAssertEqual(app.otherElements["onboarding-page-indicator"].label, "Page 1 of 5")
        XCTAssertFalse(app.buttons["onboarding-back"].exists, "Back on the first page")
        XCTAssertFalse(app.tabBars.buttons["Search"].exists, "the tabs are showing under the first-run screen")

        // Each point is its own page, in order.
        let next = app.buttons["onboarding-next"]
        for (page, id) in ["spoilers", "not-recorded", "sources", "privacy"].enumerated() {
            next.tap()
            XCTAssertTrue(app.staticTexts["onboarding-point-\(id)"].waitForExistence(timeout: 10), "no \(id) page")
            XCTAssertEqual(app.otherElements["onboarding-page-indicator"].label, "Page \(page + 2) of 5")
        }
        XCTAssertTrue(app.buttons["onboarding-finish"].exists, "no Start browsing on the last page")

        // Back goes back a page.
        app.buttons["onboarding-back"].tap()
        XCTAssertTrue(app.staticTexts["onboarding-point-sources"].waitForExistence(timeout: 10), "Back did not go back")
        // Names both sources and the non-endorsement, by name.
        let sources = app.staticTexts.allElementsBoundByIndex.map(\.label).joined(separator: " ")
        for needle in ["LezWatch.TV", "TVmaze", "CC BY-SA 4.0", "do not endorse this app"] {
            XCTAssertTrue(sources.contains(needle), "the sources page does not say \(needle)")
        }

        app.buttons["Skip"].tap()
        XCTAssertTrue(app.tabBars.buttons["Search"].waitForExistence(timeout: 30), "Skip did not reach Search")
    }

    /// The "not recorded" promise is on its page, by its words.
    @MainActor
    func testEveryPageSaysWhatItShould() throws {
        let app = launchFresh()
        XCTAssertTrue(app.staticTexts["onboarding-welcome"].waitForExistence(timeout: 30))
        let text = nextToTheEnd(app)
        for needle in ["Welcome to ", "Reveal", "Not recorded", "LezWatch.TV", "TVmaze", "No account, no analytics, no tracking"] {
            XCTAssertTrue(text.contains(needle), "the first-run pages do not say \(needle)")
        }
    }

    /// Finishing once is remembered: the next launch starts on Search.
    @MainActor
    func testFinishingIsRemembered() throws {
        let app = launchFresh()
        XCTAssertTrue(app.staticTexts["onboarding-welcome"].waitForExistence(timeout: 30))
        nextToTheEnd(app)
        app.buttons["onboarding-finish"].tap()
        XCTAssertTrue(app.tabBars.buttons["Search"].waitForExistence(timeout: 30))
        app.terminate()

        // No argument this time: the stored value decides.
        let again = XCUIApplication()
        again.launch()
        XCTAssertTrue(again.tabBars.buttons["Search"].waitForExistence(timeout: 30), "the first-run screen came back")
        XCTAssertFalse(again.staticTexts["onboarding-welcome"].exists)
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
        XCTAssertTrue(app.staticTexts["onboarding-welcome"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["Skip"].exists, "a reopened introduction offers Skip")
        XCTAssertTrue(app.buttons["Close"].exists, "a reopened introduction has no Close")
        nextToTheEnd(app)
        let done = app.buttons["onboarding-finish"]
        XCTAssertEqual(done.label, "Done")
        done.tap()
        XCTAssertTrue(app.staticTexts["onboarding-welcome"].waitForNonExistence(timeout: 10), "Done did not close the introduction")
        XCTAssertTrue(open.waitForExistence(timeout: 10), "Done did not return to About")
    }
}
