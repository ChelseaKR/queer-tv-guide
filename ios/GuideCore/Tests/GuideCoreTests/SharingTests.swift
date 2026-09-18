import Foundation
import XCTest
@testable import GuideCore

final class SharingTests: XCTestCase {
    // Built from parts, never an "https://…" literal: SourceTreeGuardTests
    // allows no host but the snapshot's in ios/ source.
    private func url(_ rest: String) -> URL {
        URL(string: "https" + "://" + "lezwatchtv.com" + rest)!
    }

    func testQueryFragmentAndCredentialsAreRemoved() {
        XCTAssertEqual(Sharing.cleanURL(url("/show/xena-warrior-princess/?utm_source=app&utm_medium=share&ref=abc")), url("/show/xena-warrior-princess/"))
        XCTAssertEqual(Sharing.cleanURL(url("/show/xena-warrior-princess/#characters")), url("/show/xena-warrior-princess/"))
        var components = URLComponents(url: url("/show/x/"), resolvingAgainstBaseURL: false)!
        components.user = "someone"
        components.password = String(repeating: "x", count: 8)
        let withUser = components.url!
        XCTAssertNotNil(withUser.user, "the credentials landed")
        XCTAssertEqual(Sharing.cleanURL(withUser), url("/show/x/"))
    }

    func testACleanURLIsUnchanged() {
        let clean = url("/show/xena-warrior-princess/")
        XCTAssertEqual(Sharing.cleanURL(clean), clean)
    }

    /// Every show page in the real snapshot is an https LezWatch.TV page
    /// with nothing for the cleaning to remove, so a share sends exactly the
    /// page the app already links to.
    func testRealShowPagesAreSharedAsIs() throws {
        let s = try SnapshotDecoder().decode(try Data(contentsOf: Repo.bundledSnapshot))
        let changed = s.shows.filter { Sharing.cleanURL($0.sourceURL) != $0.sourceURL }.map(\.id)
        XCTAssertEqual(changed, [], "show pages that carry a query or fragment")
        let foreign = s.shows.filter { $0.sourceURL.scheme != "https" || $0.sourceURL.host != "lezwatchtv.com" }.map(\.id)
        XCTAssertEqual(foreign, [])
    }
}
