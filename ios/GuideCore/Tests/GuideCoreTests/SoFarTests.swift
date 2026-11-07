import XCTest
@testable import GuideCore

/// "Has anyone died so far?" (DECISIONS 0043): one test per precision tier and
/// per edge case in growth/qf-progress-and-stats-2026-11-06.md. Names are
/// invented.
final class SoFarTests: XCTestCase {
    private typealias P = SoFar.Position
    private let show = "lwtv:show:102"

    private func at(_ season: Int, _ episode: Int) -> P { P(season: season, episode: episode) }

    private func event(_ name: String, _ precision: DeathPlacement.Precision, reason: String = "exact_date", season: Int? = nil, episodes: [Int]? = nil, airdate: String? = nil, year: Int? = 2017, show: Show.ID? = "lwtv:show:102") -> SoFar.Event {
        SoFar.Event(name: name, year: year, placement: DeathPlacement(showID: show, precision: precision, reason: reason, season: season, episodes: episodes, airdate: airdate))
    }

    private let tenTenSix = [SeasonEpisodeCount(season: 1, episodes: 10), SeasonEpisodeCount(season: 2, episodes: 10), SeasonEpisodeCount(season: 3, episodes: 6)]

    private func answer(_ events: [SoFar.Event], at position: P, counts: [SeasonEpisodeCount]? = nil) -> SoFar.Answer {
        SoFar.answer(events: events, episodeCounts: counts ?? tenTenSix, at: position)
    }

    /// No answer may open with a bare "No" or state a count of zero.
    private func assertNeverZeroOrNo(_ a: SoFar.Answer, file: StaticString = #filePath, line: UInt = #line) {
        for text in [a.headline, a.laterHeadline] + a.soFar + a.uncertain + a.later {
            XCTAssertNil(text.range(of: #"^\s*No\b"#, options: .regularExpression), text, file: file, line: line)
            XCTAssertFalse(text.contains(" 0 "), text, file: file, line: line)
            XCTAssertFalse(text.localizedCaseInsensitiveContains("none"), text, file: file, line: line)
            XCTAssertFalse(text.localizedCaseInsensitiveContains("still dead"), text, file: file, line: line)
        }
    }

    // MARK: Episode tier

    func testAnEpisodeDeathBeforeTheViewerIsSoFar() {
        let a = answer([event("Odile", .episode, season: 2, episodes: [7])], at: at(3, 4))
        XCTAssertEqual(a.headline, "Yes. 1 recorded death through season 3, episode 4.")
        XCTAssertEqual(a.soFar, ["Odile: season 2, episode 7."])
        XCTAssertEqual(a.uncertain, [])
        XCTAssertEqual(a.later, [])
        XCTAssertTrue(a.laterHeadline.hasPrefix("Not recorded after season 3, episode 4."))
        assertNeverZeroOrNo(a)
    }

    func testTheViewersOwnEpisodeCountsAsSoFar() {
        let a = answer([event("Odile", .episode, season: 2, episodes: [7])], at: at(2, 7))
        XCTAssertEqual(a.soFar.count, 1)
    }

    func testAnEpisodeDeathAfterTheViewerIsOnlyInLater() {
        let a = answer([event("Odile", .episode, season: 2, episodes: [7])], at: at(2, 6))
        XCTAssertEqual(a.headline, "Not recorded through season 2, episode 6. LezWatch.TV records no death of a listed character up to here.")
        XCTAssertEqual(a.soFar, [])
        XCTAssertFalse(a.spoken.contains("Odile"), "a later death must not be in the so-far answer: \(a.spoken)")
        XCTAssertEqual(a.laterHeadline, "After season 2, episode 6: 1 recorded death placed later.")
        XCTAssertEqual(a.later, ["Odile: season 2, episode 7."])
        assertNeverZeroOrNo(a)
    }

    func testOneDayOffSaysItWasMatchedByAirDate() {
        let a = answer([event("Odile", .episode, reason: "one_day_off", season: 1, episodes: [3])], at: at(1, 3))
        XCTAssertEqual(a.soFar, ["Odile: season 1, episode 3 (matched to an episode a day from the recorded date)."])
    }

    // MARK: Same-day double episodes

    func testAPairIsNeverResolvedToOneEpisode() {
        let pair = event("Odile", .episodePair, reason: "double_bill", season: 2, episodes: [7, 8])
        let after = answer([pair], at: at(2, 8))
        XCTAssertEqual(after.soFar, ["Odile: season 2, episode 7 or 8 (both aired the same day)."])

        let before = answer([pair], at: at(2, 6))
        XCTAssertEqual(before.soFar, [])
        XCTAssertEqual(before.uncertain, [])
        XCTAssertEqual(before.later, ["Odile: season 2, episode 7 or 8 (both aired the same day)."])
    }

    func testOnTheFirstOfAPairItSaysThisEpisodeOrTheNext() {
        let a = answer([event("Odile", .episodePair, reason: "double_bill", season: 2, episodes: [7, 8])], at: at(2, 7))
        XCTAssertEqual(a.soFar, [])
        XCTAssertEqual(a.uncertain, ["A recorded death in this episode or the next (episodes 7 and 8 aired the same day)."])
        XCTAssertTrue(a.headline.hasPrefix("Can't say for sure through season 2, episode 7."))
        XCTAssertFalse(a.spoken.contains("Odile"), "an uncertain death is not named in the so-far answer")
        XCTAssertEqual(a.later, ["May be before or after where you are:", "Odile: season 2, episode 7 or 8 (both aired the same day)."])
        assertNeverZeroOrNo(a)
    }

    // MARK: Whole-season drops and season-only tiers

    func testADropInsideTheViewersSeasonMayBeEitherSide() {
        let drop = event("Odile", .season, reason: "season_drop", season: 3)
        let a = answer([drop], at: at(3, 4))
        XCTAssertEqual(a.uncertain, ["Season 3 has a recorded death we can't place in an episode (the season was released all at once). It may be before or after episode 4."])
        XCTAssertEqual(a.soFar, [])
        XCTAssertFalse(a.spoken.contains("Odile"))
        XCTAssertFalse(a.spoken.contains("episode 1."), "a drop is never episode 1")
        assertNeverZeroOrNo(a)
    }

    func testADropInAnEarlierSeasonIsSoFarAndALaterOneIsLater() {
        let drop = event("Odile", .season, reason: "season_drop", season: 2)
        XCTAssertEqual(answer([drop], at: at(3, 1)).soFar, ["Odile: season 2; we can't place the episode."])
        let later = answer([drop], at: at(1, 10))
        XCTAssertEqual(later.soFar, [])
        XCTAssertEqual(later.uncertain, [])
        XCTAssertEqual(later.later, ["Odile: season 2; we can't place the episode."])
    }

    func testAFinishedSeasonCountsItsSeasonOnlyDeaths() {
        // Season 3 has 6 episodes; at episode 6 the viewer has seen all of it.
        let drop = event("Odile", .season, reason: "season_drop", season: 3)
        XCTAssertEqual(answer([drop], at: at(3, 6)).soFar, ["Odile: season 3; we can't place the episode."])
        XCTAssertEqual(answer([drop], at: at(3, 5)).soFar, [])
        // Without an episode count, the season is never taken as finished.
        let unknown = SoFar.answer(events: [drop], episodeCounts: nil, at: at(3, 6))
        XCTAssertEqual(unknown.soFar, [])
        XCTAssertEqual(unknown.uncertain.count, 1)
    }

    func testTwoDeathsInOneSeasonAreOneLineWithACount() {
        let a = answer([event("A", .season, reason: "within_a_week", season: 3), event("B", .season, reason: "within_a_week", season: 3)], at: at(3, 2))
        XCTAssertEqual(a.uncertain, ["Season 3 has 2 recorded deaths we can't place in an episode. They may be before or after episode 2."])
        XCTAssertEqual(a.later, ["May be before or after where you are:", "A: season 3; we can't place the episode.", "B: season 3; we can't place the episode."])
    }

    // MARK: Specials

    func testASpecialIsNamedByItsAirDateNotANumber() {
        let special = event("Odile", .special, reason: "special_same_day", season: 2, airdate: "2017-11-12")
        let a = answer([special], at: at(3, 1))
        XCTAssertEqual(a.soFar, ["Odile: a special that aired November 12, 2017."])
        let inside = answer([special], at: at(2, 4))
        XCTAssertEqual(inside.uncertain, ["A recorded death in a special that aired November 12, 2017, during season 2. It may be before or after episode 4."])
        let noSeason = answer([event("Odile", .special, reason: "special_same_day", airdate: "2017-11-12")], at: at(5, 1))
        XCTAssertEqual(noSeason.soFar, [])
        XCTAssertEqual(noSeason.uncertain.count, 1)
    }

    // MARK: Unplaced

    func testAnUnplacedDeathIsSaidPlainlyNeverZero() {
        let a = answer([event("Odile", .unplaced, reason: "between_seasons", year: 2019)], at: at(2, 1))
        XCTAssertEqual(a.soFar, [])
        XCTAssertEqual(a.uncertain, ["LezWatch.TV records a death in 2019 that we can't match to an episode, so we can't say whether it's before or after where you are."])
        XCTAssertTrue(a.headline.hasPrefix("Can't say for sure"))
        XCTAssertFalse(a.headline.hasPrefix("Not recorded"), "an unplaced death must not read as no death")
        assertNeverZeroOrNo(a)
    }

    func testAShowWithoutAnEpisodeListSaysItCanOnlyAnswerForTheWholeShow() {
        let a = SoFar.answer(events: [event("Odile", .unplaced, reason: "no_tvmaze_join"), event("Juno", .unplaced, reason: "no_tvmaze_join")], episodeCounts: nil, at: at(1, 1))
        XCTAssertEqual(a.uncertain, ["We don't have this show's episode list, so we can only answer for the whole show, in the reveal above."])
        assertNeverZeroOrNo(a)
    }

    func testAnUnrecognizedPrecisionIsUnplaced() {
        let a = answer([event("Odile", .unrecognized("scene"), reason: "new_rule", season: 2, episodes: [7])], at: at(3, 1))
        XCTAssertEqual(a.soFar, [])
        XCTAssertEqual(a.uncertain.count, 1)
    }

    func testAnEpisodePlacementMissingItsNumberIsUnplacedNotEpisodeOne() {
        let a = answer([event("Odile", .episode, season: 2, episodes: nil)], at: at(3, 1))
        XCTAssertEqual(a.soFar, [])
        XCTAssertEqual(a.uncertain.count, 1)
    }

    // MARK: Resurrections and crossovers (on a real decoded snapshot)

    private func fixture(_ edit: (inout [[String: Any]]) -> Void) throws -> Snapshot {
        let url = Repo.iosRoot.appendingPathComponent("GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")
        let data = try JSONEdit.edit(try Data(contentsOf: url)) { root in
            var characters = root["characters"] as! [[String: Any]]
            edit(&characters)
            root["characters"] = characters
        }
        return try SnapshotDecoder().decode(data)
    }

    private func placement(_ show: String, _ precision: String, _ reason: String, season: Int?, episodes: [Int]?) -> [String: Any] {
        ["show_id": show, "precision": precision, "reason": reason, "season": season as Any? ?? NSNull(), "episodes": episodes as Any? ?? NSNull(), "airdate": NSNull()]
    }

    func testEachDeathOfACharacterWhoDiedTwiceIsPlacedOnItsOwn() throws {
        let snapshot = try fixture { characters in
            var death = characters[2]["death"] as! [String: Any]
            death["dates"] = [
                ["date": "2017-11-12", "year": 2017, "raw": "20171112", "placements": [placement(show, "episode", "exact_date", season: 2, episodes: [7])]],
                ["date": "2018-03-01", "year": 2018, "raw": "20180301", "placements": [placement(show, "episode", "exact_date", season: 3, episodes: [2])]],
            ]
            death["years"] = [2017, 2018]
            characters[2]["death"] = death
        }
        let cartographers = try XCTUnwrap(snapshot.show(id: show))
        let a = SoFar.answer(show: cartographers, cast: snapshot.characters(inShow: show), at: at(3, 1))
        // The first death counts so far even though the second is after the viewer.
        XCTAssertEqual(a.headline, "Yes. 1 recorded death through season 3, episode 1.")
        XCTAssertEqual(a.soFar, ["Odile Brandt: season 2, episode 7."])
        XCTAssertEqual(a.later, ["Odile Brandt: season 3, episode 2."])
        XCTAssertFalse((a.spoken + a.laterSpoken).localizedCaseInsensitiveContains("still dead"))
        XCTAssertTrue(a.footer.contains("died at some point, not that they stay dead"))
    }

    func testACrossoverPlacedInAnotherShowIsNotCountedHere() throws {
        let snapshot = try fixture { characters in
            var death = characters[2]["death"] as! [String: Any]
            death["dates"] = [["date": "2017-11-12", "year": 2017, "raw": "20171112", "placements": [
                placement("lwtv:show:101", "episode", "exact_date", season: 1, episodes: [4]),
                placement(show, "other_show", "crossover_matched_other_show", season: nil, episodes: nil),
            ]]]
            characters[2]["death"] = death
        }
        let cartographers = try XCTUnwrap(snapshot.show(id: show))
        XCTAssertEqual(SoFar.events(cast: snapshot.characters(inShow: show), show: cartographers), [])
        let a = SoFar.answer(show: cartographers, cast: snapshot.characters(inShow: show), at: at(3, 6))
        XCTAssertTrue(a.headline.hasPrefix("Not recorded through season 3, episode 6."), a.headline)
        XCTAssertTrue(a.laterHeadline.hasPrefix("Not recorded after"), a.laterHeadline)
    }

    func testTheFixtureAnswersThroughTheDecodedSnapshot() throws {
        let snapshot = try SnapshotDecoder().decode(try Data(contentsOf: Repo.iosRoot.appendingPathComponent("GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")))
        let cartographers = try XCTUnwrap(snapshot.show(id: show))
        let cast = snapshot.characters(inShow: show)
        XCTAssertEqual(SoFar.answer(show: cartographers, cast: cast, at: at(2, 7)).soFar, ["Odile Brandt: season 2, episode 7."])
        XCTAssertEqual(SoFar.answer(show: cartographers, cast: cast, at: at(1, 1)).later, ["Odile Brandt: season 2, episode 7."])
    }

    func testADateWithoutPlacementsInAPlacedFileIsUnplacedByTheYearRule() throws {
        let snapshot = try fixture { characters in
            var death = characters[2]["death"] as! [String: Any]
            death["dates"] = [["date": "2017-11-12", "year": 2017, "raw": "20171112"]]
            characters[2]["death"] = death
        }
        let cartographers = try XCTUnwrap(snapshot.show(id: show))
        let a = SoFar.answer(show: cartographers, cast: snapshot.characters(inShow: show), at: at(3, 6))
        XCTAssertEqual(a.uncertain, ["LezWatch.TV records a death in 2017 that we can't match to an episode, so we can't say whether it's before or after where you are."])
    }

    func testAShowWithNoListedCharactersSaysSo() throws {
        let snapshot = try SnapshotDecoder().decode(try Data(contentsOf: Repo.iosRoot.appendingPathComponent("GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")))
        let radio = try XCTUnwrap(snapshot.show(id: "lwtv:show:104"))
        let a = SoFar.answer(show: radio, cast: snapshot.characters(inShow: radio.id), at: at(1, 1))
        XCTAssertTrue(a.headline.hasPrefix("Not recorded. LezWatch.TV lists no characters"), a.headline)
    }

    // MARK: Position past the list

    func testAPositionPastTheSeasonSaysItCountsAllOfIt() {
        let a = answer([], at: at(3, 9))
        XCTAssertEqual(a.notes, ["TVmaze lists 6 episodes in season 3, so this counts all of it."])
        let past = answer([], at: at(5, 1))
        XCTAssertEqual(past.notes, ["TVmaze lists episodes up to season 3, so this counts every listed episode."])
    }

    // MARK: The picker never depends on the episode list

    func testThePickerRangesComeFromLezWatchsSeasonCountOnly() throws {
        let snapshot = try SnapshotDecoder().decode(try Data(contentsOf: Repo.iosRoot.appendingPathComponent("GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")))
        for show in snapshot.shows {
            let expected: ClosedRange<Int> = {
                guard let seasons = show.seasons, seasons > 0 else { return 1...99 }
                return 1...(show.years.onAir == .yes ? seasons + 1 : seasons)
            }()
            XCTAssertEqual(SoFar.seasonRange(for: show), expected, show.title)
        }
        // Negative control: a show with an episode list and one without, same
        // LezWatch season count, get the same picker.
        let withList = try XCTUnwrap(snapshot.show(id: "lwtv:show:102"))
        let edited = try JSONEdit.editShow(try Data(contentsOf: Repo.iosRoot.appendingPathComponent("GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")), index: 1) { $0["episode_counts"] = NSNull() }
        let withoutList = try XCTUnwrap(try SnapshotDecoder().decode(edited).show(id: "lwtv:show:102"))
        XCTAssertNotNil(withList.episodeCounts)
        XCTAssertNil(withoutList.episodeCounts)
        XCTAssertEqual(SoFar.seasonRange(for: withList), SoFar.seasonRange(for: withoutList))
        XCTAssertEqual(SoFar.clamped(at(40, 2000), for: withList), SoFar.clamped(at(40, 2000), for: withoutList))
    }

    // MARK: Stored on the device

    func testThePositionIsStoredPerShow() throws {
        let suite = "SoFarTests-\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let store = WatchPositionStore(defaults: defaults)
        XCTAssertNil(store.position(for: show))
        store.set(at(3, 4), for: show)
        XCTAssertEqual(store.position(for: show), at(3, 4))
        XCTAssertNil(store.position(for: "lwtv:show:101"))
        XCTAssertEqual(WatchPositionStore(defaults: defaults).position(for: show), at(3, 4), "kept across launches")
        defaults.set([0, 4], forKey: "soFar.position.lwtv:show:101")
        XCTAssertNil(store.position(for: "lwtv:show:101"), "a bad stored value is ignored, not shown")
        store.clear(for: show)
        XCTAssertNil(store.position(for: show))
    }
}
