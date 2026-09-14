import XCTest
@testable import GuideCore

final class SearchIndexTests: XCTestCase {
    private func index() throws -> SearchIndex { SearchIndex(snapshot: try Repo.fixture()) }

    private func titles(_ hits: [SearchIndex.Hit]) -> [String] {
        hits.map {
            switch $0 {
            case .show(let s): return "show:\(s.title)"
            case .character(let c): return "char:\(c.name)"
            }
        }
    }

    func testEmptyQueryReturnsNothing() throws {
        XCTAssertEqual(try index().search(""), [])
        XCTAssertEqual(try index().search("   "), [])
    }

    func testFindsShowByTitlePrefix() throws {
        XCTAssertEqual(titles(try index().search("harb")).first, "show:Harbor Lights")
    }

    func testFindsCharacterByName() throws {
        XCTAssertEqual(titles(try index().search("odile")).first, "char:Odile Brandt")
    }

    func testFindsCharacterByActor() throws {
        XCTAssertTrue(titles(try index().search("Example Actor Three")).contains("char:Odile Brandt"))
    }

    func testFindsCharacterByShowTitle() throws {
        let hits = titles(try index().search("cartographers"))
        XCTAssertEqual(hits.first, "show:The Cartographers")
        XCTAssertTrue(hits.contains("char:Odile Brandt"))
        XCTAssertTrue(hits.contains("char:Thea Marsh"))
    }

    func testDiacriticAndCaseInsensitive() throws {
        XCTAssertEqual(titles(try index().search("INES")).first, "char:Inés Varga")
        XCTAssertEqual(titles(try index().search("inés")).first, "char:Inés Varga")
    }

    func testAmpersandTitle() throws {
        XCTAssertEqual(titles(try index().search("salt &")).first, "show:Salt & Ember")
    }

    func testExactMatchRanksAboveSubstring() throws {
        let hits = titles(try index().search("night shift radio"))
        XCTAssertEqual(hits.first, "show:Night Shift Radio")
    }

    func testLimit() throws {
        XCTAssertEqual(try index().search("e", limit: 2).count, 2)
    }

    func testFindsCharacterByAlternateShowName() throws {
        XCTAssertTrue(titles(try index().search("Cartographers")).contains("show:The Cartographers"))
    }

    // MARK: Filters

    func testNoRecordedDeathsFilterExcludesCastlessShows() throws {
        let idx = try index()
        let shows = idx.browse(filters: .init(noRecordedDeaths: true)).map(\.title)
        // Harbor Lights (2 characters, neither with a recorded death) and
        // Salt & Ember (1 character, no recorded death) both pass. Night
        // Shift Radio has zero listed characters — absence of any cast is
        // not the same as a checked, deathless cast — and The Cartographers
        // has a recorded death; both are excluded.
        XCTAssertEqual(shows, ["Harbor Lights", "Salt & Ember"])
        XCTAssertFalse(shows.contains("Night Shift Radio"), "a show with no listed characters is not 'no deaths'")
        XCTAssertFalse(shows.contains("The Cartographers"), "a show with a recorded death must be excluded")
    }

    func testDeathCoverageDistinguishesNoCastFromNoRecordedDeath() throws {
        let idx = try index()
        let s = try Repo.fixture()
        XCTAssertEqual(idx.deathCoverage(s.show(id: "lwtv:show:102")!).anyRecordedDeath, true)
        XCTAssertEqual(idx.deathCoverage(s.show(id: "lwtv:show:101")!), SearchIndex.DeathCoverage(hasCharacters: true, anyRecordedDeath: false))
        XCTAssertEqual(idx.deathCoverage(s.show(id: "lwtv:show:103")!), SearchIndex.DeathCoverage(hasCharacters: true, anyRecordedDeath: false))
        XCTAssertEqual(idx.deathCoverage(s.show(id: "lwtv:show:104")!), SearchIndex.DeathCoverage(hasCharacters: false, anyRecordedDeath: false))
    }

    func testWorthItFilter() throws {
        let idx = try index()
        XCTAssertEqual(idx.browse(filters: .init(worthIt: [.yes])).map(\.title), ["Harbor Lights"])
        XCTAssertEqual(idx.browse(filters: .init(worthIt: [.yes, .meh])).map(\.title), ["Harbor Lights", "The Cartographers"])
        XCTAssertFalse(idx.browse(filters: .init(worthIt: [.no])).map(\.title).contains("Salt & Ember"), "not rated is not 'no'")
    }

    func testHasWatchLinkFilter() throws {
        XCTAssertEqual(try index().browse(filters: .init(hasWatchLink: true)).map(\.title), ["Harbor Lights", "Night Shift Radio"])
    }

    func testFilterAppliesToCharacterHitsThroughTheirShows() throws {
        let hits = titles(try index().search("a", filters: .init(worthIt: [.yes]), limit: 100))
        XCTAssertTrue(hits.contains("char:Mara Quill"))
        XCTAssertFalse(hits.contains("char:Odile Brandt"))
    }
}
