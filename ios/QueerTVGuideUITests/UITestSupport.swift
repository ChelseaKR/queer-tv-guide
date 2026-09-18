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
    /// Starts past the first-run screen (`OnboardingView.seenKey`, read from
    /// UserDefaults' argument domain), as every test but the onboarding
    /// ones needs.
    static let skipOnboarding = ["-onboarding.v1.seen", "YES"]

    /// The app, set to start on Search. Not launched yet. Not main-actor
    /// bound, like the `XCUIApplication()` it replaces in the smoke tests.
    static func guide() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += skipOnboarding
        return app
    }

    /// Launches and waits for the Search tab.
    @MainActor
    static func launchedGuide(arguments: [String] = []) -> XCUIApplication {
        let app = XCUIApplication.guide()
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

    /// A show row in a results list. Show rows are read "<title>. Worth it:
    /// …", which sets them apart from character rows and from the
    /// active-filters row above the results.
    @MainActor
    var firstShowRow: XCUIElement {
        buttons.matching(NSPredicate(format: "label CONTAINS %@", ". Worth it: ")).firstMatch
    }

    /// Search → Filter → "Has a where-to-watch link" → show the results.
    /// Returns when a show row is on screen.
    @MainActor
    func applyWhereToWatchFilter(file: StaticString = #filePath, line: UInt = #line) {
        let filter = buttons.matching(NSPredicate(format: "label BEGINSWITH 'Filter'")).firstMatch
        XCTAssertTrue(filter.waitForExistence(timeout: 30), "no Filter button", file: file, line: line)
        filter.tap()
        let toggle = buttons["Has a where-to-watch link"]
        XCTAssertTrue(toggle.waitForExistence(timeout: 10), "no where-to-watch filter", file: file, line: line)
        // At accessibility text sizes the filters are taller than the screen.
        for _ in 0..<8 where !toggle.isHittable { swipeUp() }
        toggle.tap()
        XCTAssertTrue(toggle.isSelected, "the where-to-watch filter did not turn on", file: file, line: line)
        let showResults = buttons["filters-show-results"]
        for _ in 0..<8 where !(showResults.exists && showResults.isHittable) { swipeUp() }
        XCTAssertTrue(showResults.waitForExistence(timeout: 10), "no Show results button", file: file, line: line)
        showResults.tap()
        XCTAssertTrue(firstShowRow.waitForExistence(timeout: 30), "the filter left no show rows", file: file, line: line)
    }
}
