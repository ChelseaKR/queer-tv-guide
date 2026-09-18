import XCTest
@testable import GuideCore

/// `characters(inShow:)` is served from an index built once per snapshot.
/// It must return exactly what the obvious linear scan returns: same
/// characters, same (snapshot) order, each once.
final class SnapshotIndexTests: XCTestCase {
    private func linear(_ s: Snapshot, _ id: Show.ID) -> [Character] {
        s.characters.filter { c in c.shows.contains { $0.showID == id } }
    }

    func testIndexMatchesALinearScanForEveryShow() throws {
        let s = try Repo.fixture()
        for show in s.shows {
            XCTAssertEqual(s.characters(inShow: show.id), linear(s, show.id), show.id)
        }
        XCTAssertEqual(s.characters(inShow: "lwtv:show:101").map(\.name), ["Mara Quill", "Inés Varga"])
        XCTAssertEqual(s.characters(inShow: "lwtv:show:104"), [], "a show with no listed cast")
        XCTAssertEqual(s.characters(inShow: "lwtv:show:999999"), [], "an id not in the snapshot")
    }

    func testACharacterListedTwiceForOneShowAppearsOnce() throws {
        // Two stints on the same show are two entries in LezWatch's show group.
        let data = try JSONEdit.editCharacter(try Repo.fixtureData(), index: 0) { mara in
            var shows = mara["shows"] as! [[String: Any]]
            shows.append(shows[0])
            mara["shows"] = shows
        }
        let s = try SnapshotDecoder().decode(data)
        XCTAssertEqual(s.character(id: "lwtv:character:201")?.shows.count, 2, "the edit landed")
        XCTAssertEqual(s.characters(inShow: "lwtv:show:101").map(\.name), ["Mara Quill", "Inés Varga"])
    }
}
