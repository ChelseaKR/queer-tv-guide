import XCTest
@testable import QueerTVGuide

/// The count under "N filters on" while a query and a filter are both on
/// (`SearchView.matchCount`).
@MainActor
final class SearchCountTests: XCTestCase {
    func testTopOnlyWhenSearchHeldMatchesBack() {
        XCTAssertEqual(SearchView.matchCount(1, isCapped: false), "1 match")
        XCTAssertEqual(SearchView.matchCount(12, isCapped: false), "12 matches")
        // Exactly as many matches as search returns: all of them are shown.
        XCTAssertEqual(SearchView.matchCount(50, isCapped: false), "50 matches")
        XCTAssertEqual(SearchView.matchCount(50, isCapped: true), "Top 50 matches")
    }
}
