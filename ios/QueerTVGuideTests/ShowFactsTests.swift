import XCTest
import GuideCore
@testable import QueerTVGuide

/// What VoiceOver reads for a show's years, seasons and networks
/// (`ShowDetailView.spokenFacts`): words, not punctuation.
@MainActor
final class ShowFactsTests: XCTestCase {
    func testSpokenFactsReadAsWordsOnEveryRealShow() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "snapshot.v1", withExtension: "json"))
        let snapshot = try SnapshotDecoder().decode(try Data(contentsOf: url))
        for show in snapshot.shows {
            let spoken = ShowDetailView.spokenFacts(show)
            XCTAssertFalse(spoken.contains("–"), "\(show.id): \(spoken)")
            XCTAssertFalse(spoken.contains("·"), "\(show.id): \(spoken)")
            XCTAssertTrue(spoken.contains(Presentation.seasons(show.seasons)), "\(show.id): \(spoken)")
            for network in show.networks {
                XCTAssertTrue(spoken.contains(network.name), "\(show.id) dropped \(network.name): \(spoken)")
            }
        }
        let xena = try XCTUnwrap(snapshot.show(id: "lwtv:show:26"))
        XCTAssertTrue(ShowDetailView.spokenFacts(xena).hasPrefix("1995 to 2001. "), ShowDetailView.spokenFacts(xena))
        // Every shape of the years line reads as words.
        for show in snapshot.shows {
            let spoken = ShowDetailView.spokenFacts(show)
            XCTAssertFalse(spoken.contains(" to ongoing"), "\(show.id): \(spoken)")
        }
    }
}
