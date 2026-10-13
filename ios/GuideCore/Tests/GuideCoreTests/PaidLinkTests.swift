import Foundation
import XCTest
@testable import GuideCore

/// DECISIONS 0019: only an Apple TV or iTunes link carrying an `at=` token
/// is a paid link, and it says so. URLs are built from parts: the app never
/// fetches any of them (SourceTreeGuardTests keeps hosts out of ios/).
final class PaidLinkTests: XCTestCase {
    private func link(_ host: String, _ query: String?) throws -> WatchLink {
        var c = URLComponents()
        c.scheme = "https"
        c.host = host
        c.path = "/us/show/example/umc.cmc.1"
        c.percentEncodedQuery = query
        let data = try JSONSerialization.data(withJSONObject: ["url": try XCTUnwrap(c.url).absoluteString, "host": host])
        return try JSONDecoder().decode(WatchLink.self, from: data)
    }

    func testAnAppleLinkWithTheTokenIsPaid() throws {
        XCTAssertTrue(try link("tv.apple.com", "action=play&at=1l3vabc").isPaidLink)
        XCTAssertTrue(try link("itunes.apple.com", "i=1&at=1l3vabc").isPaidLink)
        let paid = try link("tv.apple.com", "at=1l3vabc")
        XCTAssertEqual(Presentation.watchLinkSpoken(paid, networks: []), "Watch on tv.apple.com, paid link")
        XCTAssertEqual(Presentation.paidLinkNote, "Paid link")
    }

    /// The negative control: the same links without a token, an empty one,
    /// or a token on another host are not paid, and read as before.
    func testAnythingElseIsNotPaid() throws {
        XCTAssertFalse(try link("tv.apple.com", "action=play").isPaidLink)
        XCTAssertFalse(try link("tv.apple.com", nil).isPaidLink)
        XCTAssertFalse(try link("tv.apple.com", "at=").isPaidLink)
        XCTAssertFalse(try link("music.apple.com", "at=1l3vabc").isPaidLink)
        XCTAssertFalse(try link("www.netflix.com", "at=1l3vabc").isPaidLink)
        let plain = try link("tv.apple.com", "action=play")
        XCTAssertEqual(Presentation.watchLinkSpoken(plain, networks: []), Presentation.watchLinkLabel(plain, networks: []))
    }
}
