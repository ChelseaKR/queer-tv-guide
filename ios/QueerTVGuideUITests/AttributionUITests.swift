import XCTest

/// Every credit the sources require is on screen, checked in the running
/// app on real data (DECISIONS 0012; docs/LICENSES-AND-ATTRIBUTION.md).
/// CI runs only `swift test`; SourceTreeGuardTests there catches a credit
/// removed from source, and these catch one that stops rendering.
final class AttributionUITests: XCTestCase {
    /// Xena: Warrior Princess, one of LezWatch.TV's oldest records, matched
    /// to TVmaze (so its schedule, and TVmaze's credit, show).
    static let referenceShowID = "lwtv:show:26"

    override func setUpWithError() throws {
        continueAfterFailure = false
        try SnapshotFacts.requireRealData()
    }

    @MainActor
    func testShowScreenLinksItsLezWatchPageAndCreditsTVmaze() throws {
        let title = try SnapshotFacts.title(ofShow: Self.referenceShowID)
        let app = XCUIApplication.launchedGuide()
        app.openShow(titled: title)

        let source = app.buttons["lezwatch-source-link"]
        XCTAssertTrue(source.waitForExistence(timeout: 10), "no LezWatch.TV link on the show screen")
        XCTAssertEqual(source.label, "View \(title) on LezWatch.TV")
        XCTAssertTrue(app.buttons["tvmaze-credit-link"].exists, "schedule shown without TVmaze's credit")
        XCTAssertEqual(app.buttons["tvmaze-license-link"].label, "License: CC BY-SA 4.0")
    }

    @MainActor
    func testCharacterScreenLinksItsLezWatchPage() throws {
        let title = try SnapshotFacts.title(ofShow: Self.referenceShowID)
        let app = XCUIApplication.launchedGuide()
        app.openShow(titled: title)
        let character = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", ", from ")).firstMatch
        if !character.exists { app.swipeUp() }
        XCTAssertTrue(character.waitForExistence(timeout: 10))
        let name = String(character.label.split(separator: ",").first ?? "")
        character.tap()

        let source = app.buttons["lezwatch-source-link"]
        XCTAssertTrue(source.waitForExistence(timeout: 30), "no LezWatch.TV link on the character screen")
        XCTAssertEqual(source.label, "View \(name) on LezWatch.TV")
    }

    @MainActor
    func testAboutNamesAndLinksBothSourcesTheirLicensesAndNonEndorsement() throws {
        let app = XCUIApplication.launchedGuide()
        app.tabBars.buttons["About"].tap()
        XCTAssertTrue(app.staticTexts["Data sources"].waitForExistence(timeout: 30))
        for id in ["source-link-lezwatch", "source-link-tvmaze", "license-link-lezwatch", "license-link-tvmaze"] {
            let link = app.buttons[id]
            if !link.exists { app.swipeUp() }
            XCTAssertTrue(link.waitForExistence(timeout: 10), "About is missing \(id)")
        }
        XCTAssertEqual(app.buttons["license-link-tvmaze"].label, "License: CC BY-SA 4.0")
        let endorsement = app.staticTexts["LezWatch.TV and TVmaze do not endorse this app."]
        if !endorsement.exists { app.swipeUp() }
        XCTAssertTrue(endorsement.waitForExistence(timeout: 10), "About lacks the non-endorsement statement")
    }

    @MainActor
    func testFavoritesCreditTVmazeForTheNextEpisodesTheyShow() throws {
        let title = try SnapshotFacts.title(ofShow: Self.referenceShowID)
        let app = XCUIApplication.launchedGuide()
        app.openShow(titled: title)
        app.buttons["Add to favorites"].tap()
        app.tabBars.buttons["Favorites"].tap()
        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", title)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 30))
        let credited = app.buttons["tvmaze-credit-link"].waitForExistence(timeout: 10) && app.buttons["tvmaze-license-link"].exists

        // Leave favorites empty for the other tests on this simulator.
        row.swipeLeft()
        let delete = app.buttons["Delete"]
        if delete.waitForExistence(timeout: 10) { delete.tap() }
        XCTAssertTrue(app.staticTexts["No favorites yet"].waitForExistence(timeout: 10), "the test favorite was not removed")

        XCTAssertTrue(credited, "Favorites show TVmaze next episodes without its credit")
    }
}
