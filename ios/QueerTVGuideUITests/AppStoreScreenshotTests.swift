import XCTest

/// App Store screenshots on the real bundled snapshot, never the fixture.
/// Skipped unless `QTG_SCREENSHOTS=1` reaches the runner
/// (`TEST_RUNNER_QTG_SCREENSHOTS=1`); `make -C ios screenshots` sets it,
/// runs these on a fresh iPhone 17 Pro Max (6.9", 1320 × 2868) with a clean
/// status bar, and exports them to docs/app-store/screenshots/.
///
/// No spoiler may show openly: every "does she die" reveal stays closed,
/// plot notes and worth-it explanations stay collapsed, and the shows used
/// carry no outcome tropes (their visible trope list is "None!").
final class AppStoreScreenshotTests: XCTestCase {
    /// Abbott Elementary: a running show with a next episode, a where-to-watch
    /// link and no outcome tropes.
    static let detailShowID = "lwtv:show:90395"
    /// Running shows with a next episode, favourited for the "next episode"
    /// shot: Abbott Elementary, Ted Lasso, Fire Country, North of North.
    static let followedShowIDs = ["lwtv:show:90395", "lwtv:show:76283", "lwtv:show:83667", "lwtv:show:98878"]

    override func setUpWithError() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["QTG_SCREENSHOTS"] == "1", "set TEST_RUNNER_QTG_SCREENSHOTS=1 (make -C ios screenshots)")
        continueAfterFailure = false
        try SnapshotFacts.requireRealData()
    }

    /// Fails the run if any death answer is on screen: every shot is taken
    /// with the reveals closed.
    @MainActor
    private func assertNoDeathSpoiler(_ app: XCUIApplication) {
        let spoiler = NSPredicate(format: "label CONTAINS[c] 'recorded death' OR label CONTAINS[c] 'death is recorded' OR label CONTAINS[c] ' dies'")
        XCTAssertEqual(app.staticTexts.matching(spoiler).count, 0, "a death answer is visible")
    }

    @MainActor
    private func keep(_ name: String, _ app: XCUIApplication) {
        assertNoDeathSpoiler(app)
        let shot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        shot.name = "appstore-\(name)"
        shot.lifetime = .keepAlways
        add(shot)
    }

    @MainActor
    private func filterButton(_ app: XCUIApplication) -> XCUIElement {
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Filter'")).firstMatch
    }

    @MainActor
    private func backToSearch(_ app: XCUIApplication) {
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertTrue(app.searchFields.firstMatch.waitForExistence(timeout: 30))
    }

    @MainActor
    func testAppStoreScreenshots() throws {
        let app = XCUIApplication.launchedGuide()

        // 1. Browse: shows with a where-to-watch link.
        filterButton(app).tap()
        let filter = app.buttons["Has a where-to-watch link"]
        XCTAssertTrue(filter.waitForExistence(timeout: 10))
        filter.tap()
        XCTAssertTrue(app.cells.firstMatch.waitForExistence(timeout: 30))
        keep("01-browse", app)
        filterButton(app).tap()
        let clearFilters = app.buttons["Clear filters"]
        XCTAssertTrue(clearFilters.waitForExistence(timeout: 10))
        clearFilters.tap()

        // 2. A show, with the "does she die" reveal closed.
        let title = try SnapshotFacts.title(ofShow: Self.detailShowID)
        app.openShow(titled: title)
        XCTAssertTrue(app.buttons["Reveal"].exists, "the reveal must be closed")
        keep("02-show-reveal-closed", app)

        // 3. Where to watch, same show, reveal still closed.
        let heading = app.staticTexts["Where to watch"]
        for _ in 0..<6 where !heading.isHittable { app.swipeUp() }
        XCTAssertTrue(heading.isHittable)
        keep("03-where-to-watch", app)
        backToSearch(app)

        // 4. Next episodes for followed shows.
        for id in Self.followedShowIDs {
            app.openShow(titled: try SnapshotFacts.title(ofShow: id))
            let add = app.buttons["Add to favourites"]
            if add.exists { add.tap() }
            backToSearch(app)
        }
        app.tabBars.buttons["Favourites"].tap()
        XCTAssertTrue(app.buttons["tvmaze-credit-link"].waitForExistence(timeout: 30))
        keep("04-next-episodes", app)

        // 5. About: the privacy posture and the sources, credited.
        app.tabBars.buttons["About"].tap()
        XCTAssertTrue(app.staticTexts["Privacy"].waitForExistence(timeout: 30))
        keep("05-privacy-and-sources", app)
    }
}
