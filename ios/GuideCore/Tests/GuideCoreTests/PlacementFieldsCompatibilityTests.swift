import XCTest
@testable import GuideCore

/// DECISIONS 0041 adds optional fields to the v1 snapshot: `episode_counts` on a
/// show, `placements` on each death date and `coverage.placements`. The app as
/// shipped in 1.0.0 must read such a file exactly as it read the file without
/// them. `Snapshot.swift` and `SnapshotDecoder.swift` are unchanged since the
/// v1.0.0 tag, so this decoder is the 1.0.0 decoder. The fixture is the v1
/// fixture plus only the new fields (pipeline/tests/test_snapshot_placements_contract.py
/// checks that, and that it validates against the schema).
final class PlacementFieldsCompatibilityTests: XCTestCase {
    private static let placementsFixtureURL: URL = Repo.iosRoot
        .appendingPathComponent("GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")

    func testTheNewFieldsDecodeToTheSameSnapshot() throws {
        let withFields = try SnapshotDecoder().decode(try Data(contentsOf: Self.placementsFixtureURL))
        let without = try Repo.fixture()
        XCTAssertEqual(withFields, without)
        XCTAssertEqual(withFields.schemaVersion, "1")
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
        XCTAssertEqual(try SnapshotDecoder().decode(data), try Repo.fixture())
    }
}
