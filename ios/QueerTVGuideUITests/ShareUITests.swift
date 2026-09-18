import XCTest

/// The show screen's Share button hands the system share sheet the show's
/// LezWatch.TV page. What it shares is checked in GuideCore (SharingTests);
/// this checks the button is there, named for the show, and opens the sheet.
final class ShareUITests: XCTestCase {
    /// Xena: Warrior Princess, as in AttributionUITests.
    static let referenceShowID = "lwtv:show:26"

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testShowScreenSharesItsLezWatchPage() throws {
        let title = try SnapshotFacts.title(ofShow: Self.referenceShowID)
        let app = XCUIApplication.launchedGuide()
        app.openShow(titled: title)

        let share = app.buttons["share-show"]
        XCTAssertTrue(share.waitForExistence(timeout: 10), "no Share button on the show screen")
        XCTAssertEqual(share.label, "Share \(title)", "the Share button is not named for the show")
        // The show screen with its new toolbar, in whatever appearance the
        // simulator is set to (run once light, once dark).
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = "share-show-screen"
        shot.lifetime = .keepAlways
        add(shot)
        share.tap()
        // The share sheet is system UI whose element names vary by release;
        // any of its known markers will do. Measured on iOS 26.5 under
        // load, it can take more than 30 seconds to appear.
        let sheet = app.descendants(matching: .any).matching(NSPredicate(
            format: "identifier == 'ActivityListView' OR identifier == 'UIActivityContentView' OR label == 'Copy' OR identifier == 'Copy'"
        )).firstMatch
        XCTAssertTrue(sheet.waitForExistence(timeout: 90), "the share sheet did not open")
    }
}
