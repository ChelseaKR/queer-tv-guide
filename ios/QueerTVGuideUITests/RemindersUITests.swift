import XCTest

/// Episode reminders are built behind `FeatureFlags.episodeReminders`, off.
/// Off, nothing about them appears and nothing asks for permission. With the
/// Debug-only override, the switch and the explanation before the system
/// prompt are reachable, and they pass Xcode's accessibility audit.
final class RemindersUITests: XCTestCase {
    /// Xena: Warrior Princess, as in AttributionUITests.
    static let referenceShowID = "lwtv:show:26"

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    private func launchWithAFavoriteShow(arguments: [String]) throws -> XCUIApplication {
        let title = try SnapshotFacts.title(ofShow: Self.referenceShowID)
        let app = XCUIApplication.launchedGuide(arguments: arguments)
        app.openShow(titled: title)
        let add = app.buttons["Add to favourites"]
        if add.waitForExistence(timeout: 5) { add.tap() }
        XCTAssertTrue(app.buttons["Remove from favourites"].waitForExistence(timeout: 10))
        app.tabBars.buttons["Favourites"].tap()
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", title)).firstMatch.waitForExistence(timeout: 30))
        return app
    }

    @MainActor
    func testRemindersDoNotAppearWhileTheFlagIsOff() throws {
        let app = try launchWithAFavoriteShow(arguments: ["-feature.episodeReminders", "NO"])
        XCTAssertFalse(app.switches["New-episode reminders"].exists, "reminders appear with the flag off")
    }

    @MainActor
    func testThePrimerExplainsBeforeAnyPromptAndPassesTheAudit() throws {
        let app = try launchWithAFavoriteShow(arguments: ["-feature.episodeReminders", "YES"])
        let toggle = app.switches["New-episode reminders"]
        for _ in 0..<4 where !toggle.isHittable { app.swipeUp() }
        XCTAssertTrue(toggle.waitForExistence(timeout: 10), "no reminders switch with the override on")
        XCTAssertEqual(toggle.value as? String, "0", "reminders start off")
        // The row's own hit point is its label, which does not flip a
        // switch; tap the switch inside it.
        let inner = toggle.switches.firstMatch
        (inner.exists ? inner : toggle).tap()

        let accept = app.buttons["reminders-accept"]
        XCTAssertTrue(accept.waitForExistence(timeout: 30), "no explanation before the system prompt")
        XCTAssertFalse(app.alerts.firstMatch.exists, "the system prompt came before the explanation")
        let text = app.staticTexts.allElementsBoundByIndex.map(\.label).joined(separator: " ")
        for needle in ["Episode titles are left out", "Nothing is sent to a server", "can be early, late or wrong"] {
            XCTAssertTrue(text.contains(needle), "the explanation does not say \"\(needle)\"")
        }
        try app.performAccessibilityAudit { issue in
            print("audit issue: \(issue.compactDescription) | \(issue.detailedDescription) | \(issue.element?.label ?? "no element")")
            return false
        }

        app.buttons["reminders-decline"].tap()
        XCTAssertTrue(toggle.waitForExistence(timeout: 10))
        XCTAssertEqual(toggle.value as? String, "0", "declining left reminders on")
    }
}
