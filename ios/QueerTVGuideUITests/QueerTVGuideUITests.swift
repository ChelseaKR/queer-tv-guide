import XCTest

/// A minimal smoke test: launch the real app in the simulator and confirm
/// the three tabs exist and the Search screen renders a real show from the
/// bundled snapshot. Not a substitute for `GuideCoreTests`/`QueerTVGuideTests`
/// — this only proves the app actually launches and draws.
final class QueerTVGuideUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testLaunchesToSearchWithTabsPresent() throws {
        let app = XCUIApplication.guide()
        app.launch()

        XCTAssertTrue(app.tabBars.buttons["Search"].waitForExistence(timeout: 30))
        XCTAssertTrue(app.tabBars.buttons["Favourites"].exists)
        XCTAssertTrue(app.tabBars.buttons["About"].exists)
    }

    func testSearchFindsABundledShow() throws {
        let show = try BundledData.referenceShow()
        let app = XCUIApplication.guide()
        app.launch()

        let searchField = app.searchFields.firstMatch
        XCTAssertTrue(searchField.waitForExistence(timeout: 30))
        searchField.tap()
        searchField.typeText(show.query)

        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", show.title)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 30), "no row for \(show.title)")
    }

    func testFavouritesTabShowsEmptyStateOnFirstLaunch() throws {
        let app = XCUIApplication.guide()
        app.launch()

        app.tabBars.buttons["Favourites"].tap()
        XCTAssertTrue(app.staticTexts["No favourites yet"].waitForExistence(timeout: 30))
    }

    func testAboutScreenStatesThePrivacyPosture() throws {
        let app = XCUIApplication.guide()
        app.launch()

        app.tabBars.buttons["About"].tap()
        XCTAssertTrue(app.staticTexts["Privacy"].waitForExistence(timeout: 30))
    }

    /// `ShowRow` shows the title, worth-it verdict, AND network to sighted
    /// users, but combines its children into one accessibility element with
    /// an explicit `.accessibilityLabel`. That explicit label wins over the
    /// automatic combine, so a VoiceOver user must hear the network too, not
    /// just title + worth-it — a silent drop is exactly the "Image, Image,
    /// Button, no context" failure mode this app otherwise avoids.
    func testShowRowAnnouncesNetworkToVoiceOver() throws {
        let show = try BundledData.referenceShow()
        XCTAssertFalse(show.networks.isEmpty, "the reference show has no network to check")
        let app = XCUIApplication.guide()
        app.launch()

        let searchField = app.searchFields.firstMatch
        XCTAssertTrue(searchField.waitForExistence(timeout: 30))
        searchField.tap()
        searchField.typeText(show.query)

        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", show.title)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 30))
        for network in show.networks {
            XCTAssertTrue(row.label.contains(network), "VoiceOver announcement dropped the network \"\(network)\": \"\(row.label)\"")
        }
    }
}

/// The UI tests run against the real bundled snapshot, so they read their
/// expectations from that same file (through this source file's path on the
/// host, which simulator test processes can read) rather than hard-coding a
/// title or network that a later `make bundle-snapshot` could change.
private enum BundledData {
    struct ReferenceShow {
        let title: String
        let query: String
        let networks: [String]
    }

    /// Xena: Warrior Princess — one of LezWatch.TV's oldest show records
    /// (post id 26), with a title and networks.
    static let referenceShowID = "lwtv:show:26"

    static let bundledSnapshot: URL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent() // QueerTVGuideUITests
        .deletingLastPathComponent() // ios
        .appendingPathComponent("QueerTVGuide/Resources/snapshot.v1.json")

    static func referenceShow() throws -> ReferenceShow {
        let data = try Data(contentsOf: bundledSnapshot)
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let shows = try XCTUnwrap(root["shows"] as? [[String: Any]])
        let show = try XCTUnwrap(shows.first { $0["id"] as? String == referenceShowID }, "\(referenceShowID) is not in the bundled snapshot")
        let title = try XCTUnwrap(show["title"] as? String)
        let networks = ((show["networks"] as? [[String: Any]]) ?? []).compactMap { $0["name"] as? String }
        let query = String(title.split(separator: ":").first ?? Substring(title))
        return ReferenceShow(title: title, query: query, networks: networks)
    }
}
