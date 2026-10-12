import Foundation
import XCTest
@testable import GuideCore

/// The "Rate" row's link: the App Store review sheet for this app, and
/// nothing else.
final class AppStoreReviewTests: XCTestCase {
    func testWriteReviewURLIsTheReviewSheetForThisApp() throws {
        let url = AppStoreReview.writeReviewURL
        XCTAssertEqual(url.scheme, "https")
        XCTAssertEqual(url.host, "apps.apple.com")
        XCTAssertEqual(url.path, "/app/id\(AppStoreReview.appID)")
        let items = try XCTUnwrap(URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems)
        XCTAssertEqual(items, [URLQueryItem(name: "action", value: "write-review")])
    }

    /// The same App Store ID the published site's badge and Smart App
    /// Banner use, so the two cannot point at different apps.
    func testAppIDMatchesThePipelinesAppStoreID() throws {
        let pipeline = Repo.iosRoot.deletingLastPathComponent()
            .appendingPathComponent("pipeline/src/qtv_pipeline/app_store.py")
        let text = try String(contentsOf: pipeline, encoding: .utf8)
        XCTAssertTrue(text.contains("APP_STORE_ID = \"\(AppStoreReview.appID)\""), "app_store.py's APP_STORE_ID is not \(AppStoreReview.appID)")
        XCTAssertTrue(AppStoreReview.appID.allSatisfy(\.isNumber))
    }
}
