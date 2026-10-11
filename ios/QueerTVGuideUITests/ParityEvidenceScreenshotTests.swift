import XCTest
import UIKit

/// Review evidence, not App Store screenshots: the new and changed surfaces
/// in light and dark, and on iPad in both orientations. Skipped unless
/// `QTG_EVIDENCE=1` reaches the runner (`TEST_RUNNER_QTG_EVIDENCE=1`).
/// Each image is an attachment named `evidence-<device>-<appearance>-<orientation>-<screen>`.
final class ParityEvidenceScreenshotTests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = true
        try XCTSkipUnless(ProcessInfo.processInfo.environment["QTG_EVIDENCE"] == "1", "set TEST_RUNNER_QTG_EVIDENCE=1")
    }

    override func tearDown() {
        XCUIDevice.shared.orientation = .portrait
        XCUIDevice.shared.appearance = .light
        super.tearDown()
    }

    @MainActor
    private func shot(_ name: String, _ appearance: String, _ orientation: String) {
        sleep(2)
        let device = UIDevice.current.userInterfaceIdiom == .pad ? "ipad" : "iphone"
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = "evidence-\(device)-\(appearance)-\(orientation)-\(name)"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    @MainActor
    private func tab(_ app: XCUIApplication, _ name: String) {
        let inBar = app.tabBars.buttons[name]
        if inBar.exists { inBar.tap() } else { app.buttons[name].firstMatch.tap() }
    }

    @MainActor
    func testLight() throws { try capture(appearance: .light, name: "light") }

    @MainActor
    func testDark() throws { try capture(appearance: .dark, name: "dark") }

    @MainActor
    private func capture(appearance: XCUIDevice.Appearance, name: String) throws {
        XCUIDevice.shared.appearance = appearance
        let isPad = UIDevice.current.userInterfaceIdiom == .pad
        let orientations: [(UIDeviceOrientation, String)] = isPad
            ? [(.portrait, "portrait"), (.landscapeLeft, "landscape")]
            : [(.portrait, "portrait")]
        let root = try SnapshotFacts.root()
        let shows = try XCTUnwrap(root["shows"] as? [[String: Any]])
        let show = try XCTUnwrap(shows.first { ($0["title"] as? String)?.count ?? 0 > 4 })
        let id = try XCTUnwrap(show["id"] as? String)
        let title = try XCTUnwrap(show["title"] as? String)

        for (orientation, o) in orientations {
            XCUIDevice.shared.orientation = orientation
            let app = XCUIApplication()
            app.launchArguments += ["-onboarding.v1.seen", "NO", "-UITestRefreshProblem", "offline"]
            app.launch()
            XCTAssertTrue(app.staticTexts["onboarding-welcome"].waitForExistence(timeout: 120))
            shot("onboarding-1-welcome", name, o)
            app.buttons["onboarding-next"].tap()
            shot("onboarding-2-spoilers", name, o)
            for _ in 0..<3 { app.buttons["onboarding-next"].tap() }
            shot("onboarding-5-privacy", name, o)
            app.buttons["onboarding-finish"].tap()

            XCTAssertTrue(app.searchFields.firstMatch.waitForExistence(timeout: 60))
            shot("search", name, o)
            let field = app.searchFields.firstMatch
            field.tap()
            field.typeText(title)
            let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", title)).firstMatch
            if row.waitForExistence(timeout: 60) {
                row.tap()
                _ = app.staticTexts["Do any queer characters die?"].waitForExistence(timeout: 60)
                shot("show", name, o)
            }
            if !isPad { app.navigationBars.buttons.firstMatch.tap() }
            field.tap()
            if field.buttons["Clear text"].exists { field.buttons["Clear text"].tap() }
            field.typeText("zzqxj")
            let tryAgain = app.buttons["Try again"]
            for _ in 0..<4 where !tryAgain.exists { app.swipeUp() }
            _ = tryAgain.waitForExistence(timeout: 10)
            shot("refresh-offline", name, o)

            app.open(try XCTUnwrap(URL(string: "queerframe://show/\(id)")))
            _ = app.staticTexts["Do any queer characters die?"].waitForExistence(timeout: 60)
            shot("link-opens-show-over-favorites", name, o)

            tab(app, "About")
            sleep(2)
            shot("about", name, o)
            app.terminate()
        }
    }
}
