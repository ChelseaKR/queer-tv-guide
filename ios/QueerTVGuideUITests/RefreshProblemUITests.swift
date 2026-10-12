import XCTest

/// The data footer when a look for new data fails: plain words for the
/// kind of failure, the promise that the data stays, and Try again.
/// `-UITestRefreshProblem` (Debug builds only) makes the look fail without
/// touching the network.
final class RefreshProblemUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testOfflineIsSaidInPlainWordsWithTryAgain() throws {
        let app = XCUIApplication.launchedGuide(arguments: ["-UITestRefreshProblem", "offline"])
        // A search that matches nothing leaves the footer right under the
        // empty state.
        let field = app.searchFields.firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 30))
        field.tap()
        field.typeText("zzqxj")
        let problem = app.staticTexts["data-refresh-problem"]
        let tryAgain = app.buttons["Try again"]
        for _ in 0..<4 where !(problem.exists && tryAgain.exists) { app.swipeUp() }
        XCTAssertTrue(problem.waitForExistence(timeout: 30), "no refresh problem in the footer")
        XCTAssertTrue(problem.label.contains("offline"), problem.label)
        XCTAssertTrue(problem.label.hasSuffix("The data on screen stays as it is."), problem.label)
        XCTAssertFalse(problem.label.contains("Refresh failed"), "the raw system error is back")
        XCTAssertTrue(tryAgain.exists, "no Try again")
        tryAgain.tap()
        XCTAssertTrue(problem.waitForExistence(timeout: 10), "a failed Try again lost the message")
    }
}
