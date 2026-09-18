import XCTest

/// Facts the UI tests read from the real bundled snapshot (through this
/// file's path on the host, which simulator test processes can read), so
/// no test hard-codes a title or network a later `make bundle-snapshot`
/// could change.
enum SnapshotFacts {
    static let bundledSnapshot: URL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent() // QueerTVGuideUITests
        .deletingLastPathComponent() // ios
        .appendingPathComponent("QueerTVGuide/Resources/snapshot.v1.json")

    static func root() throws -> [String: Any] {
        let data = try Data(contentsOf: bundledSnapshot)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    /// Refuses to run on the hand-made fixture: screenshots and attribution
    /// checks are about the real data the app ships.
    static func requireRealData() throws {
        let build = try XCTUnwrap(try root()["build"] as? [String: Any])
        let version = try XCTUnwrap(build["pipeline_version"] as? String)
        XCTAssertFalse(version.contains("fixture"), "the bundled snapshot is the fixture")
    }

    static func show(_ id: String) throws -> [String: Any] {
        let shows = try XCTUnwrap(try root()["shows"] as? [[String: Any]])
        return try XCTUnwrap(shows.first { $0["id"] as? String == id }, "\(id) is not in the bundled snapshot")
    }

    static func title(ofShow id: String) throws -> String {
        try XCTUnwrap(try show(id)["title"] as? String)
    }
}

extension XCUIApplication {
    /// Launches and waits for the Search tab.
    @MainActor
    static func launchedGuide(arguments: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += arguments
        app.launch()
        XCTAssertTrue(app.tabBars.buttons["Search"].waitForExistence(timeout: 30))
        return app
    }

    /// Search tab → search `title` → open its show screen.
    @MainActor
    func openShow(titled title: String) {
        tabBars.buttons["Search"].tap()
        let field = searchFields.firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 30))
        field.tap()
        // A previous search's text survives going back; clear it so the
        // new title is not appended to the old one.
        let clear = field.buttons["Clear text"]
        if clear.waitForExistence(timeout: 2) { clear.tap() }
        field.typeText(title)
        let row = buttons.matching(NSPredicate(format: "label BEGINSWITH %@", title)).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 30), "no row for \(title)")
        row.tap()
        XCTAssertTrue(staticTexts["Do any queer characters die?"].waitForExistence(timeout: 30), "did not reach \(title)")
    }
}
