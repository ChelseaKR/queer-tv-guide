import XCTest
@testable import GuideCore

final class SearchIndexTests: XCTestCase {
    private func index() throws -> SearchIndex { SearchIndex(snapshot: try Repo.fixture()) }

    private func titles(_ results: SearchIndex.SearchResults) -> [String] {
        results.hits.map {
            switch $0 {
            case .show(let s): return "show:\(s.title)"
            case .character(let c): return "char:\(c.name)"
            }
        }
    }

    func testEmptyQueryReturnsNothing() throws {
        XCTAssertEqual(try index().search(""), SearchIndex.SearchResults(hits: [], totalCount: 0))
        XCTAssertEqual(try index().search("   "), SearchIndex.SearchResults(hits: [], totalCount: 0))
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
        XCTAssertEqual(try index().search("e", limit: 2).hits.count, 2)
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

    // MARK: Punctuation, word order, speed

    func testPunctuationDoesNotHaveToBeTyped() throws {
        XCTAssertEqual(titles(try index().search("salt and ember")).first, "show:Salt & Ember")
        XCTAssertEqual(titles(try index().search("harborlights")).first, "show:Harbor Lights", "a title typed without its space")
    }

    func testWordsMatchInAnyOrder() throws {
        XCTAssertEqual(titles(try index().search("lights harbor")).first, "show:Harbor Lights")
        XCTAssertEqual(titles(try index().search("radio night")).first, "show:Night Shift Radio")
    }

    /// A character found by name plus the show they are in.
    func testNameAndShowWordsTogetherFindACharacter() throws {
        XCTAssertEqual(titles(try index().search("odile cartog")).first, "char:Odile Brandt")
        XCTAssertFalse(titles(try index().search("odile harbor")).contains("char:Odile Brandt"), "every word must match")
    }

    func testFoldingDropsApostrophesAndReadsAmpersandAsAnd() {
        XCTAssertEqual(SearchIndex.fold("Grey’s Anatomy"), "greys anatomy")
        XCTAssertEqual(SearchIndex.fold("Grey's Anatomy"), "greys anatomy")
        XCTAssertEqual(SearchIndex.fold("Xena: Warrior Princess"), "xena warrior princess")
        XCTAssertEqual(SearchIndex.fold("Law & Order"), "law and order")
        XCTAssertEqual(SearchIndex.fold("  L-Word:  Generation Q "), "l word generation q")
    }

    /// Measured on the real snapshot before this change: "greys anatomy"
    /// and "xena warrior" found nothing, because the titles carry a curly
    /// apostrophe and a colon the query did not.
    func testRealTitlesWithPunctuationAreFound() throws {
        let s = try SnapshotDecoder().decode(try Data(contentsOf: Repo.bundledSnapshot))
        let idx = SearchIndex(snapshot: s)
        for (query, id) in [("greys anatomy", "lwtv:show:"), ("xena warrior", "lwtv:show:26")] {
            guard case .show(let show)? = idx.search(query).hits.first else {
                XCTFail("no show first for \(query)")
                continue
            }
            XCTAssertTrue(show.id.hasPrefix(id), "\(query) found \(show.title) first")
            XCTAssertTrue(SearchIndex.fold(show.title).hasPrefix(SearchIndex.fold(query)), "\(query) found \(show.title) first")
        }
        // Trigger-warning levels read mildest first, whatever order the
        // taxonomy lists them in (High, Low, Medium in the 2026-09-18 file).
        XCTAssertEqual(idx.filterOptions.triggerWarnings.map(\.slug), ["low", "medium", "high"])
        XCTAssertFalse(idx.filterOptions.tropes.contains { Presentation.deathSpoilerTropeSlugs.contains($0.slug) })
    }

    // MARK: More filters

    func testFilterOptionsComeFromTheSnapshot() throws {
        let options = try index().filterOptions
        XCTAssertEqual(options.watchHosts, [
            SearchIndex.WatchHost(key: "example.com", showCount: 2),
            SearchIndex.WatchHost(key: "store.example.org", showCount: 1),
        ])
        XCTAssertEqual(options.tropes.map(\.name), ["Found Family", "Slow Burn"])
        XCTAssertEqual(options.triggerWarnings.map(\.slug), ["violence"])
        XCTAssertEqual(options.triggerWarnings.first?.showCount, 1)
    }

    func testWatchHostFilterIgnoresWWW() throws {
        let idx = try index()
        XCTAssertEqual(idx.browse(filters: .init(watchHosts: ["example.com"])).map(\.title), ["Harbor Lights", "Night Shift Radio"])
        XCTAssertEqual(idx.browse(filters: .init(watchHosts: ["store.example.org"])).map(\.title), ["Night Shift Radio"])
        XCTAssertEqual(SearchIndex.WatchHost.key(for: "WWW.Netflix.com"), "netflix.com")
    }

    func testTropeFilterKeepsShowsWithAnySelectedTrope() throws {
        let idx = try index()
        XCTAssertEqual(idx.browse(filters: .init(tropes: ["slow-burn"])).map(\.title), ["Harbor Lights"])
        XCTAssertEqual(idx.browse(filters: .init(tropes: ["slow-burn", "found-family"])).map(\.title), ["Harbor Lights"])
    }

    /// Hiding a trigger-warning level leaves out the shows rated at it and
    /// keeps every show with none listed.
    func testHiddenTriggerWarningsLeaveOutOnlyShowsRatedAtThatLevel() throws {
        let titles = try index().browse(filters: .init(hiddenTriggerWarnings: ["violence"])).map(\.title)
        XCTAssertEqual(titles, ["Harbor Lights", "Night Shift Radio", "Salt & Ember"])
    }

    func testFiltersCombineAndCount() throws {
        let filters = SearchIndex.Filters(worthIt: [.yes, .no], hasWatchLink: true, watchHosts: ["store.example.org"], tropes: [], hiddenTriggerWarnings: ["violence"])
        XCTAssertEqual(filters.activeCount, 5)
        XCTAssertFalse(filters.isEmpty)
        XCTAssertEqual(try index().browse(filters: filters).map(\.title), ["Night Shift Radio"])
        XCTAssertEqual(SearchIndex.Filters().activeCount, 0)
    }

    /// "Bury Your Queers" is never offered as a filter: choosing it would
    /// answer "does she die" for every show it returns. The edit puts it in
    /// the taxonomy and on a show, so the omission is the filter's doing.
    func testTheDeathRevealingTropeIsNeverOffered() throws {
        let data = try JSONEdit.edit(try Repo.fixtureData()) { root in
            var taxonomies = root["taxonomies"] as! [String: Any]
            var tropes = taxonomies["tropes"] as! [[String: Any]]
            tropes.append(["lwtv_id": 9999, "slug": "dead-queers", "name": "Bury Your Queers", "count": 1])
            taxonomies["tropes"] = tropes
            root["taxonomies"] = taxonomies
            var shows = root["shows"] as! [[String: Any]]
            var show = shows[0]
            show["tropes"] = (show["tropes"] as! [[String: Any]]) + [["slug": "dead-queers", "name": "Bury Your Queers"]]
            shows[0] = show
            root["shows"] = shows
        }
        let s = try SnapshotDecoder().decode(data)
        XCTAssertTrue(s.shows[0].tropes.contains { $0.slug == "dead-queers" }, "the edit landed")
        let offered = SearchIndex(snapshot: s).filterOptions.tropes.map(\.slug)
        XCTAssertFalse(offered.contains("dead-queers"))
        XCTAssertEqual(offered, ["found-family", "slow-burn"])
    }
}
