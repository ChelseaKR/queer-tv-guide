import XCTest
@testable import GuideCore

/// DECISIONS 0053: the snapshot says whether a recorded death is counted
/// (`death.counted`). A date on a character LezWatch.TV lists as alive (Holby
/// City's Bernie Wolfe, Warrior Nun's Ava Silva, Sara Lance, Nora West-Allen)
/// is neither a death nor "alive". Absent `counted` (a file from before 0053,
/// and every 1.0.0 file) reads as before.
final class DeathCountedTests: XCTestCase {
    private let listedAliveLine = "LezWatch.TV records a death date (2017) for Odile Brandt but lists the character as alive, so it is not counted here."

    /// The fixture with Odile Brandt's `counted` set (nil removes the key).
    private func odile(counted: Bool?) throws -> Snapshot {
        let data = try JSONEdit.editCharacter(try Repo.fixtureData(), index: 2) { odile in
            var death = odile["death"] as! [String: Any]
            if let counted { death["counted"] = counted } else { death.removeValue(forKey: "counted") }
            odile["death"] = death
        }
        return try SnapshotDecoder().decode(data)
    }

    func testAnOldSnapshotHasNoCountedFieldAndReadsAsBefore() throws {
        let s = try Repo.fixture()
        XCTAssertTrue(s.characters.allSatisfy { $0.death.counted == nil })
        let show = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        let deaths = Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show)
        XCTAssertEqual(deaths.headline, "1 of 2 listed characters has a recorded death.")
        XCTAssertEqual(deaths.lines, ["Odile Brandt dies (2017)."])
    }

    func testCountedTrueReadsAsBeforeAndFalseDecodes() throws {
        XCTAssertEqual(try odile(counted: true).character(id: "lwtv:character:203")?.death.counted, true)
        XCTAssertEqual(try odile(counted: false).character(id: "lwtv:character:203")?.death.counted, false)
        let s = try odile(counted: true)
        let show = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        XCTAssertEqual(Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show).headline,
                       "1 of 2 listed characters has a recorded death.")
    }

    func testADateOnACharacterListedAsAliveIsNotADeathAndNotAlive() throws {
        let s = try odile(counted: false)
        let show = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        let cast = s.characters(inShow: show.id)
        let deaths = Presentation.showDeaths(cast: cast, show: show)
        XCTAssertEqual(deaths.headline, "Not recorded. LezWatch.TV does not list any of the 2 listed characters as dead.")
        XCTAssertEqual(deaths.lines, ["Odile Brandt: not recorded. \(listedAliveLine)"])
        XCTAssertTrue(deaths.notes.contains("One listed character has a recorded death date, but LezWatch.TV lists the character as alive, so it is not counted here."))
        let odile = try XCTUnwrap(s.character(id: "lwtv:character:203"))
        XCTAssertEqual(Presentation.death(odile.death, name: "Odile Brandt"), "Not recorded. \(listedAliveLine)")
        XCTAssertEqual(Presentation.deathShort(odile.death), "Death date recorded, listed as alive")
        XCTAssertEqual(Presentation.deathsSummary(cast: cast, showID: show.id),
                       "Not recorded. LezWatch.TV does not list any of the 2 listed characters as dead.")
        for text in [deaths.headline, deaths.lines[0], Presentation.death(odile.death, name: "Odile Brandt")] {
            XCTAssertFalse(text.contains(" dies"), text)
            XCTAssertFalse(text.lowercased().contains("is alive"), text)
        }
    }

    func testAShowWithOnlyAListedAliveDateStaysOutOfTheNoRecordedDeathsFilter() throws {
        let s = try odile(counted: false)
        let show = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        XCTAssertTrue(SearchIndex(snapshot: s).deathCoverage(show).anyRecordedDeath, "a date is on record, so the filter must not admit the show")
    }

    /// Sara Lance: several dates, linked to more than one show, listed as alive.
    /// The status rule is applied before 0030's placement, as on the site.
    func testAMultiShowCharacterListedAliveGetsTheStatusSentenceNotThePlacementOne() throws {
        let data = try JSONEdit.editCharacter(try Repo.fixtureData(), index: 2) { odile in
            var shows = odile["shows"] as! [[String: Any]]
            shows.append(["show_id": "lwtv:show:101", "role": "guest", "years": ["2022"]])
            odile["shows"] = shows
            var death = odile["death"] as! [String: Any]
            death["years"] = [2014, 2016, 2021]
            death["dates"] = [2014, 2016, 2021].map { ["date": NSNull(), "year": $0, "raw": "\($0)"] as [String: Any] }
            death["counted"] = false
            odile["death"] = death
        }
        let s = try SnapshotDecoder().decode(data)
        let sara = try XCTUnwrap(s.character(id: "lwtv:character:203"))
        XCTAssertEqual(Presentation.deathPlacement(sara, inShow: "lwtv:show:101"), .listedAlive)
        XCTAssertEqual(Presentation.deathPlacement(sara, inShow: "lwtv:show:102"), .listedAlive)
        XCTAssertEqual(Presentation.death(sara.death, name: "Odile Brandt"),
                       "Not recorded. LezWatch.TV records death dates (2014, 2016, 2021) for Odile Brandt but lists the character as alive, so it is not counted here.")
    }

    func testADeathEntryWithNoYearListedAsAliveSaysSo() {
        let death = Death(died: true, deathKnown: true, dates: [], years: [], counted: false)
        XCTAssertEqual(Presentation.death(death, name: "Nora West-Allen"),
                       "Not recorded. LezWatch.TV records a death but no date for Nora West-Allen but lists the character as alive, so it is not counted here.")
    }

    /// Negative control: with the field removed the same record is a death again,
    /// so the tests above fail if `counted` were ignored.
    func testNegativeControlWithoutTheFieldTheDateCountsAgain() throws {
        let s = try odile(counted: nil)
        let show = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        XCTAssertEqual(Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show).headline,
                       "1 of 2 listed characters has a recorded death.")
    }
}
