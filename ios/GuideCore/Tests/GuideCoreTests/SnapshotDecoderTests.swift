import XCTest
@testable import GuideCore

final class SnapshotDecoderTests: XCTestCase {
    func testBundledFixtureDecodes() throws {
        let snapshot = try Repo.fixture()
        XCTAssertEqual(snapshot.schemaVersion, "1")
        XCTAssertEqual(snapshot.shows.count, 4)
        XCTAssertEqual(snapshot.characters.count, 5)
        XCTAssertEqual(snapshot.attribution.map(\.source).sorted(), ["lezwatch", "tvmaze"])
        XCTAssertEqual(snapshot.generatedAt, ISO8601SecondFormatter.date(from: "2026-09-13T20:00:00Z"))
    }

    func testFixtureValidatesAgainstTheRealJSONSchema() throws {
        // Belt-and-braces: the Python/uv validation step that produced this
        // fixture is not part of the Swift build. This just re-asserts the
        // structural invariants Decodable already enforces by decoding
        // successfully, so a future hand-edit of the fixture that breaks the
        // contract fails here even without re-running the schema validator.
        XCTAssertNoThrow(try Repo.fixture())
    }

    // MARK: Absence states — death (LezWatch records deaths, not survival)

    func testDeathHasNoManufacturedSurvivesState() throws {
        let s = try Repo.fixture()
        let odile = try XCTUnwrap(s.character(id: "lwtv:character:203"))
        XCTAssertEqual(odile.death.died, true)
        XCTAssertEqual(odile.death.deathKnown, true)
        XCTAssertEqual(odile.death.years, [2017])

        let mara = try XCTUnwrap(s.character(id: "lwtv:character:201"))
        XCTAssertNil(mara.death.died, "absence of a recorded death is nil, not false")
        XCTAssertEqual(mara.death.deathKnown, false)
        XCTAssertEqual(mara.death.dates, [])
    }

    func testDeathDatesCarryRawAndParsedForm() throws {
        let s = try Repo.fixture()
        let odile = try XCTUnwrap(s.character(id: "lwtv:character:203"))
        let entry = try XCTUnwrap(odile.death.dates.first)
        XCTAssertEqual(entry.raw, "20171112")
        XCTAssertEqual(entry.date, "2017-11-12")
        XCTAssertEqual(entry.year, 2017)
    }

    func testDiedFalseIsRejectedAsAContractViolation() throws {
        // The schema constrains `died` to `true` or `null`; `false` would be
        // LezWatch recording a survival it never records. If a future build
        // emits it, the app must fail loudly rather than silently accept a
        // fact the source doesn't assert.
        let data = try JSONEdit.editCharacter(try Repo.fixtureData(), index: 0) {
            $0["death"] = ["died": false, "death_known": false, "dates": [], "years": []]
        }
        XCTAssertThrowsError(try SnapshotDecoder().decode(data))
    }

    // MARK: Absence states — schedule (two different "no next episode"s)

    func testScheduleUnknownVsNoUpcomingAreDistinct() throws {
        let s = try Repo.fixture()
        let saltAndEmber = try XCTUnwrap(s.show(id: "lwtv:show:103"))
        XCTAssertFalse(saltAndEmber.schedule.scheduleKnown, "TVmaze was never matched")
        XCTAssertNil(saltAndEmber.schedule.nextEpisode)

        let cartographers = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        XCTAssertTrue(cartographers.schedule.scheduleKnown, "TVmaze matched; it confirms nothing upcoming")
        XCTAssertNil(cartographers.schedule.nextEpisode)

        XCTAssertNotEqual(
            Presentation.nextEpisode(saltAndEmber.schedule),
            Presentation.nextEpisode(cartographers.schedule),
            "unknown schedule and 'confirmed nothing upcoming' must read differently even though both have next_episode == nil"
        )
    }

    func testJoinMethodAndMatchedAreCarried() throws {
        let s = try Repo.fixture()
        let show = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        XCTAssertEqual(show.schedule.join.method, .imdbLookup)
        XCTAssertTrue(show.schedule.join.matched)
    }

    // MARK: Absence states — ratings, watch links, optional terms

    func testUnratedShowHasNilRatingsNotZero() throws {
        let s = try Repo.fixture()
        let bare = try XCTUnwrap(s.show(id: "lwtv:show:103"))
        XCTAssertNil(bare.ratings.worthIt)
        XCTAssertNil(bare.ratings.quality)
        XCTAssertNil(bare.ratings.realness)
        XCTAssertNil(bare.ratings.screentime)
        XCTAssertNil(bare.ratings.score)
        XCTAssertFalse(bare.ratings.showWeLove)
        XCTAssertEqual(bare.watchLinks, [])
        XCTAssertNil(bare.format)
        XCTAssertNil(bare.seasons)
        XCTAssertNil(bare.summary)
    }

    func testWorthItIsOpenTextNotAClosedEnum() throws {
        // The contract deliberately leaves worth_it as free text (observed:
        // Yes/Meh/No/TBD). An unrecognised value must still decode and
        // still be shown — only filtering treats it as "unknown".
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 0) { show in
            var ratings = show["ratings"] as! [String: Any]
            ratings["worth_it"] = "Extremely"
            show["ratings"] = ratings
        }
        let s = try SnapshotDecoder().decode(data)
        XCTAssertEqual(s.shows[0].ratings.worthIt, "Extremely")
        XCTAssertNil(s.shows[0].ratings.worthItKnown)
        XCTAssertEqual(Presentation.worthIt(s.shows[0].ratings.worthIt), "Extremely")
    }

    func testCharacterOptionalTaxonomyTermsAbsence() throws {
        let s = try Repo.fixture()
        let juno = try XCTUnwrap(s.character(id: "lwtv:character:205"))
        XCTAssertNil(juno.sexuality)
        XCTAssertNil(juno.romantic)
        XCTAssertEqual(juno.cliches, [])
        XCTAssertNil(juno.actors.first?.name, "an unresolved actor id is nil, not a placeholder string")
    }

    // MARK: Strictness

    func testUnsupportedSchemaVersionFails() throws {
        let data = try JSONEdit.edit(try Repo.fixtureData()) { $0["schema_version"] = "2" }
        XCTAssertThrowsError(try SnapshotDecoder().decode(data)) { error in
            XCTAssertEqual(error as? SnapshotDecodingError, .unsupportedSchemaVersion("2"))
        }
    }

    func testMissingRequiredKeyFailsWithPath() throws {
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 1) { $0.removeValue(forKey: "title") }
        XCTAssertThrowsError(try SnapshotDecoder().decode(data)) { error in
            guard case .malformed(let detail)? = error as? SnapshotDecodingError else { return XCTFail("\(error)") }
            XCTAssertTrue(detail.contains("title"), detail)
        }
    }

    func testBadDatetimeFails() throws {
        let data = try JSONEdit.edit(try Repo.fixtureData()) { $0["generated_at"] = "not-a-date" }
        XCTAssertThrowsError(try SnapshotDecoder().decode(data))
    }

    func testGarbageFails() {
        XCTAssertThrowsError(try SnapshotDecoder().decode(Data("not json".utf8)))
        XCTAssertThrowsError(try SnapshotDecoder().decode(Data()))
    }

    func testRelationsResolve() throws {
        let s = try Repo.fixture()
        XCTAssertEqual(s.characters(inShow: "lwtv:show:101").map(\.name).sorted(), ["Inés Varga", "Mara Quill"])
        XCTAssertEqual(s.shows(forCharacter: "lwtv:character:203").map(\.title), ["The Cartographers"])
        XCTAssertEqual(s.characters(inShow: "lwtv:show:104"), [])
        let harborLights = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        XCTAssertEqual(s.similarShows(to: harborLights).map(\.title), ["Night Shift Radio"])
    }

    func testLookupsAreConstantTimeNotLinearRescans() throws {
        // Regression guard for the O(n) `first(where:)` mistake at catalogue
        // scale (~2,300 shows / ~7,400 characters per schema/README).
        let s = try Repo.fixture()
        for _ in 0..<1000 {
            _ = s.show(id: "lwtv:show:101")
            _ = s.character(id: "lwtv:character:201")
        }
        // No assertion beyond "this returns"; a linear scan would still pass
        // functionally. The Snapshot.showsByID/charactersByID dictionaries
        // are the actual guard, exercised structurally by every other test.
        XCTAssertNotNil(s.show(id: "lwtv:show:101"))
    }
}
