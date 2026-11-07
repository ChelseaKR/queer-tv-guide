import XCTest
@testable import GuideCore

/// DECISIONS 0041 adds optional fields to the v1 snapshot: `episode_counts` on a
/// show, `placements` on each death date and `coverage.placements`. The 1.0.0
/// decoder ignored them (this test proved it while `Snapshot.swift` was
/// unchanged since the v1.0.0 tag; Android's PlacementFieldsCompatibilityTest
/// still does for its decoder). From 1.1 GuideCore reads them for "so far"
/// (DECISIONS 0043), so this test now checks both directions: a file without
/// them decodes with every new field `nil` (not computed), and a file with
/// them decodes to the same snapshot apart from those fields. The fixture is
/// the v1 fixture plus only the new fields
/// (pipeline/tests/test_snapshot_placements_contract.py checks that, and that
/// it validates against the schema).
final class PlacementFieldsCompatibilityTests: XCTestCase {
    private static let placementsFixtureURL: URL = Repo.iosRoot
        .appendingPathComponent("GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")

    func testAFileWithoutTheFieldsDecodesWithNothingComputed() throws {
        let without = try Repo.fixture()
        XCTAssertNil(without.coverage.placements)
        XCTAssertTrue(without.shows.allSatisfy { $0.episodeCounts == nil })
        XCTAssertTrue(without.characters.flatMap(\.death.dates).allSatisfy { $0.placements == nil })
        XCTAssertFalse(SoFar.isAvailable(in: without))
    }

    func testTheNewFieldsDecodeToTheSameSnapshotApartFromThem() throws {
        let withFields = try SnapshotDecoder().decode(try Data(contentsOf: Self.placementsFixtureURL))
        let without = try Repo.fixture()
        XCTAssertEqual(withFields.schemaVersion, "1")
        XCTAssertEqual(withFields.shows.map(\.id), without.shows.map(\.id))
        XCTAssertEqual(withFields.shows.map(\.title), without.shows.map(\.title))
        XCTAssertEqual(withFields.shows.map(\.schedule), without.shows.map(\.schedule))
        XCTAssertEqual(withFields.characters.map(\.id), without.characters.map(\.id))
        XCTAssertEqual(withFields.characters.map(\.death.dates.count), without.characters.map(\.death.dates.count))
        XCTAssertEqual(withFields.characters.flatMap(\.death.dates).map(\.date), without.characters.flatMap(\.death.dates).map(\.date))
        XCTAssertEqual(withFields.attribution, without.attribution)
        XCTAssertEqual(withFields.coverage.fields, without.coverage.fields)

        XCTAssertEqual(withFields.coverage.placements?.deathEvents, 1)
        XCTAssertTrue(SoFar.isAvailable(in: withFields))
        let cartographers = try XCTUnwrap(withFields.show(id: "lwtv:show:102"))
        XCTAssertEqual(cartographers.episodeCounts, [SeasonEpisodeCount(season: 1, episodes: 10), SeasonEpisodeCount(season: 2, episodes: 10), SeasonEpisodeCount(season: 3, episodes: 6)])
        XCTAssertNil(try XCTUnwrap(withFields.show(id: "lwtv:show:103")).episodeCounts, "null means no list, not zero episodes")
        let odile = try XCTUnwrap(withFields.character(id: "lwtv:character:203"))
        XCTAssertEqual(odile.death.dates.first?.placements, [DeathPlacement(showID: "lwtv:show:102", precision: .episode, reason: "exact_date", season: 2, episodes: [7], airdate: nil)])
    }

    func testTheFixtureReallyCarriesTheNewFields() throws {
        // Negative control: if the fields were missing, the test above would prove nothing.
        let object = try JSONSerialization.jsonObject(with: try Data(contentsOf: Self.placementsFixtureURL)) as! [String: Any]
        let coverage = object["coverage"] as! [String: Any]
        XCTAssertNotNil(coverage["placements"])
        let shows = object["shows"] as! [[String: Any]]
        XCTAssertTrue(shows.allSatisfy { $0.keys.contains("episode_counts") })
        let characters = object["characters"] as! [[String: Any]]
        let dates = characters.flatMap { (($0["death"] as! [String: Any])["dates"] as! [[String: Any]]) }
        XCTAssertFalse(dates.isEmpty)
        XCTAssertTrue(dates.allSatisfy { $0["placements"] != nil })
    }

    func testEveryPrecisionDecodes() throws {
        // Each precision the pipeline can write, including a null show id, on one date.
        let precisions: [[String: Any]] = [
            ["show_id": "lwtv:show:102", "precision": "episode", "reason": "exact_date", "season": 2, "episodes": [7], "airdate": NSNull()],
            ["show_id": "lwtv:show:102", "precision": "episode_pair", "reason": "double_bill", "season": 2, "episodes": [7, 8], "airdate": NSNull()],
            ["show_id": "lwtv:show:102", "precision": "special", "reason": "special_same_day", "season": 2, "episodes": NSNull(), "airdate": "2017-11-12"],
            ["show_id": "lwtv:show:102", "precision": "season", "reason": "season_drop", "season": 2, "episodes": NSNull(), "airdate": NSNull()],
            ["show_id": "lwtv:show:102", "precision": "unplaced", "reason": "between_seasons", "season": NSNull(), "episodes": NSNull(), "airdate": NSNull()],
            ["show_id": "lwtv:show:102", "precision": "other_show", "reason": "crossover_matched_other_show", "season": NSNull(), "episodes": NSNull(), "airdate": NSNull()],
            ["show_id": NSNull(), "precision": "unplaced", "reason": "no_show_in_death_year", "season": NSNull(), "episodes": NSNull(), "airdate": NSNull()],
        ]
        let data = try JSONEdit.editCharacter(try Data(contentsOf: Self.placementsFixtureURL), index: 2) { character in
            var death = character["death"] as! [String: Any]
            var dates = death["dates"] as! [[String: Any]]
            dates[0]["placements"] = precisions
            death["dates"] = dates
            character["death"] = death
        }
        let decoded = try SnapshotDecoder().decode(data)
        let precisionsRead = try XCTUnwrap(decoded.characters[2].death.dates[0].placements).map(\.precision)
        XCTAssertEqual(precisionsRead, [.episode, .episodePair, .special, .season, .unplaced, .otherShow, .unplaced])
        XCTAssertEqual(decoded.characters[2].death.dates[0].placements?.last?.showID, nil)
    }

    /// A precision a newer pipeline adds must not make the whole file
    /// unreadable: it reads as unrecognized, which "so far" treats as unplaced.
    func testAnUnknownPrecisionDecodesAsUnrecognized() throws {
        let data = try JSONEdit.editCharacter(try Data(contentsOf: Self.placementsFixtureURL), index: 2) { character in
            var death = character["death"] as! [String: Any]
            var dates = death["dates"] as! [[String: Any]]
            dates[0]["placements"] = [["show_id": "lwtv:show:102", "precision": "scene", "reason": "new_rule", "season": 2, "episodes": [7], "airdate": NSNull()]]
            death["dates"] = dates
            character["death"] = death
        }
        let decoded = try SnapshotDecoder().decode(data)
        XCTAssertEqual(decoded.characters[2].death.dates[0].placements?.first?.precision, .unrecognized("scene"))
    }
}
