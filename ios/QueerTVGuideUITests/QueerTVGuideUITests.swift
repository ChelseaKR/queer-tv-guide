import XCTest

/// A minimal smoke test: launch the real app in the simulator and confirm
/// the three tabs exist and the Search screen renders something from the
/// bundled snapshot without a network connection. Not a substitute for
/// `GuideCoreTests`/`QueerTVGuideTests` — this only proves the app actually
/// launches and draws.
final class QueerTVGuideUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testLaunchesToSearchWithTabsPresent() throws {
        let app = XCUIApplication()
        app.launch()

        XCTAssertTrue(app.tabBars.buttons["Search"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.tabBars.buttons["Favourites"].exists)
        XCTAssertTrue(app.tabBars.buttons["About"].exists)
    }

    func testSearchFindsABundledShowOffline() throws {
        let app = XCUIApplication()
        app.launch()

        let searchField = app.searchFields.firstMatch
        XCTAssertTrue(searchField.waitForExistence(timeout: 10))
        searchField.tap()
        searchField.typeText("Harbor")

        XCTAssertTrue(app.staticTexts["Harbor Lights"].waitForExistence(timeout: 5))
    }

    func testFavouritesTabShowsEmptyStateOnFirstLaunch() throws {
        let app = XCUIApplication()
        app.launch()

        app.tabBars.buttons["Favourites"].tap()
        XCTAssertTrue(app.staticTexts["No favourites yet"].waitForExistence(timeout: 5))
    }

    func testAboutScreenStatesThePrivacyPosture() throws {
        let app = XCUIApplication()
        app.launch()

        app.tabBars.buttons["About"].tap()
        XCTAssertTrue(app.staticTexts["Privacy"].waitForExistence(timeout: 5))
    }

    /// `ShowRow` shows the title, worth-it verdict, AND network (e.g. "·
    /// Example Network") to sighted users, but combines its children into
    /// one accessibility element with an explicit `.accessibilityLabel`.
    /// That explicit label wins over the automatic combine, so a VoiceOver
    /// user must hear the network too, not just title + worth-it — a
    /// silent drop is exactly the "Image, Image, Button, no context" failure
    /// mode this app otherwise avoids.
    func testShowRowAnnouncesNetworkToVoiceOver() throws {
        let app = XCUIApplication()
        app.launch()

        let searchField = app.searchFields.firstMatch
        XCTAssertTrue(searchField.waitForExistence(timeout: 10))
        searchField.tap()
        searchField.typeText("Harbor")

        let row = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Harbor Lights")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        XCTAssertTrue(row.label.contains("Example Network"), "VoiceOver announcement dropped the network name: \"\(row.label)\"")
    }
}
