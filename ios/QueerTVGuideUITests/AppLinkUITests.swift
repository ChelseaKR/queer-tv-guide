import XCTest
import UIKit

/// `queerframe://show/<id>`, the link a widget row opens (and the same
/// route a reminder tap takes): the show opens on the Favorites tab, pushed,
/// so Back returns to Favorites.
final class AppLinkUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testAShowLinkOpensTheShowOverFavorites() throws {
        let root = try SnapshotFacts.root()
        let shows = try XCTUnwrap(root["shows"] as? [[String: Any]])
        let first = try XCTUnwrap(shows.first)
        let id = try XCTUnwrap(first["id"] as? String)
        let title = try XCTUnwrap(first["title"] as? String)

        let app = XCUIApplication.launchedGuide()
        app.open(try XCTUnwrap(URL(string: "queerframe://show/\(id)")))
        XCTAssertTrue(app.staticTexts["Do any queer characters die?"].waitForExistence(timeout: 30), "the link did not open a show")
        XCTAssertTrue(app.navigationBars[title].exists || app.staticTexts[title].exists, "the link opened another show than \(title)")
        XCTAssertTrue(app.navigationBars["Favorites"].exists || app.tabBars.buttons["Favorites"].isSelected, "the link did not open on Favorites")

        // At regular width (iPad) the show sits beside the Favorites list,
        // so there is no Back to take.
        guard UIDevice.current.userInterfaceIdiom != .pad else {
            XCTAssertTrue(app.navigationBars["Favorites"].exists, "Favorites is not beside the show")
            return
        }
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertTrue(app.navigationBars["Favorites"].waitForExistence(timeout: 10), "Back did not return to Favorites")
    }

    @MainActor
    func testALinkToAShowTheDataLacksSaysSo() throws {
        let app = XCUIApplication.launchedGuide()
        app.open(try XCTUnwrap(URL(string: "queerframe://show/lwtv:show:not-in-this-data")))
        XCTAssertTrue(app.staticTexts["Show not found"].waitForExistence(timeout: 30))
    }
}
