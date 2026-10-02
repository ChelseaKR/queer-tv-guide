import XCTest
@testable import GuideCore

/// Where-to-watch labels: a readable "Watch on …", with a service name only
/// when one of the show's own networks is the site's name, and the bare host
/// otherwise. Never a guessed name.
final class WatchLinkLabelTests: XCTestCase {
    private func link(_ host: String) -> WatchLink {
        WatchLink(url: URL(fileURLWithPath: "/watch"), host: host)
    }

    private func networks(_ names: String...) -> [Term] {
        names.map { Term(slug: $0.lowercased(), name: $0) }
    }

    func testANetworkThatNamesTheSiteIsUsed() {
        XCTAssertEqual(Presentation.watchLinkLabel(link("www.netflix.com"), networks: networks("Netflix")), "Watch on Netflix")
        XCTAssertEqual(Presentation.watchLinkLabel(link("www.primevideo.com"), networks: networks("Prime Video")), "Watch on Prime Video")
        XCTAssertEqual(Presentation.watchLinkLabel(link("www.hbomax.com"), networks: networks("HBO", "HBO Max")), "Watch on HBO Max")
        XCTAssertEqual(Presentation.watchLinkLabel(link("abc.com"), networks: networks("ABC")), "Watch on ABC")
    }

    /// Absence stays absence: with no matching network, the label is the
    /// host, never a name the data does not give.
    func testWithoutAMatchingNetworkTheHostIsTheLabel() {
        XCTAssertEqual(Presentation.watchLinkLabel(link("www.amazon.com"), networks: networks("Prime Video")), "Watch on amazon.com", "amazon.com is not guessed to be Prime Video")
        XCTAssertEqual(Presentation.watchLinkLabel(link("tv.apple.com"), networks: networks("Apple TV+")), "Watch on tv.apple.com")
        XCTAssertEqual(Presentation.watchLinkLabel(link("www.hulu.com"), networks: []), "Watch on hulu.com")
        XCTAssertEqual(Presentation.watchLinkLabel(link("www.netflix.com"), networks: networks("Netflix Kids")), "Watch on netflix.com", "a name that only contains the site's is not used")
        XCTAssertEqual(Presentation.watchLinkLabel(link("localhost"), networks: networks("localhost")), "Watch on localhost", "no site name to compare")
    }

    func testOnlyALeadingWwwIsDropped() {
        XCTAssertEqual(Presentation.displayHost("www.amazon.com"), "amazon.com")
        XCTAssertEqual(Presentation.displayHost("WWW.Amazon.com"), "Amazon.com")
        XCTAssertEqual(Presentation.displayHost("itunes.apple.com"), "itunes.apple.com")
        XCTAssertEqual(Presentation.displayHost("wwwfoo.com"), "wwwfoo.com")
    }

    /// The real bundled data: every label is "Watch on " plus either one of
    /// that show's own network names or the host without "www.", and no
    /// label is the raw "www." host the audit called not human-readable.
    func testEveryLabelInTheBundledSnapshotIsANetworkOrTheHost() throws {
        let snapshot = try SnapshotDecoder().decode(try Data(contentsOf: Repo.bundledSnapshot))
        var links = 0, named = 0
        for show in snapshot.shows {
            for watch in show.watchLinks {
                links += 1
                let label = Presentation.watchLinkLabel(watch, networks: show.networks)
                XCTAssertTrue(label.hasPrefix("Watch on "), label)
                let service = String(label.dropFirst("Watch on ".count))
                XCTAssertFalse(service.isEmpty)
                XCTAssertFalse(service.lowercased().hasPrefix("www."), label)
                if show.networks.map(\.name).contains(service) {
                    named += 1
                } else {
                    XCTAssertEqual(service, Presentation.displayHost(watch.host), "\(show.title): \(label)")
                }
            }
        }
        XCTAssertGreaterThan(links, 0, "the bundled snapshot has where-to-watch links")
        XCTAssertGreaterThan(named, 0, "some links are named by their show's network")
        XCTAssertLessThan(named, links, "and some fall back to the host")
    }
}
