import XCTest
@testable import GuideCore

/// Absence renders as absence: every "nothing" state has words, and none of
/// those words could be mistaken for a value or for a fact the source never
/// asserted (schema/README's central rule).
final class PresentationTests: XCTestCase {
    func testWorthItAbsenceAndOpenText() {
        XCTAssertEqual(Presentation.worthIt(nil), "Not rated")
        XCTAssertEqual(Presentation.worthIt("Yes"), "Yes")
        XCTAssertEqual(Presentation.worthIt("TBD"), "TBD")
        XCTAssertEqual(Presentation.worthIt("Extremely"), "Extremely", "an unrecognised value is still shown, not hidden")
        XCTAssertNotEqual(Presentation.worthIt(nil), Presentation.worthIt("No"), "unrated must never read as 'No'")
    }

    func testRatingAbsenceIsNotZero() {
        XCTAssertEqual(Presentation.rating(nil, label: "Quality"), "Quality: not rated")
        XCTAssertEqual(Presentation.rating(3, label: "Quality"), "Quality: 3 of 5")
        XCTAssertFalse(Presentation.rating(nil, label: "Quality").contains("0"), "absence is not zero")
        XCTAssertEqual(Presentation.ratingValue(nil), "Not rated")
        XCTAssertEqual(Presentation.ratingValue(4), "4 of 5")
    }

    func testScoreAbsenceIsStatedAndIsNotAPercentage() {
        XCTAssertEqual(Presentation.score(nil), "No score recorded")
        XCTAssertTrue(Presentation.score(42.5).contains("ordinal"), "the score's own docs warn it is not a percentage")
    }

    // MARK: Death — no manufactured "survives" state

    func testDeathRecordedVsNotRecordedAreDistinctSentences() {
        let recorded = Death(died: true, deathKnown: true, dates: [], years: [2017])
        let recordedNoYear = Death(died: true, deathKnown: true, dates: [], years: [])
        let notRecorded = Death(died: nil, deathKnown: false, dates: [], years: [])

        let diesText = Presentation.death(recorded, name: "Odile Brandt")
        let diesNoYearText = Presentation.death(recordedNoYear, name: "Odile Brandt")
        let notRecordedText = Presentation.death(notRecorded, name: "Mara Quill")

        XCTAssertEqual(diesText, "Yes. Odile Brandt dies (2017).")
        XCTAssertEqual(diesNoYearText, "Yes. Odile Brandt dies. The year is not recorded.")
        XCTAssertEqual(notRecordedText, "No death is recorded for Mara Quill in this snapshot.")

        XCTAssertFalse(notRecordedText.lowercased().contains("survive"), "the contract has no survives state to assert")
        XCTAssertFalse(notRecordedText.hasPrefix("No.") , "must not read as a flat 'No' answer to 'does she die'")
        XCTAssertNotEqual(Presentation.deathShort(recorded), Presentation.deathShort(notRecorded))
    }

    func testMultipleDeathDatesAreAllStated() {
        let twice = Death(died: true, deathKnown: true, dates: [], years: [2015, 2019])
        XCTAssertEqual(Presentation.death(twice, name: "Odile Brandt"), "Yes. Odile Brandt dies more than once, recorded in 2015, 2019.")
    }

    func testDeathsSummary() throws {
        let s = try Repo.fixture()
        XCTAssertEqual(Presentation.deathsSummary(cast: s.characters(inShow: "lwtv:show:102")),
                       "1 of 2 listed characters dies: Odile Brandt.")
        XCTAssertEqual(Presentation.deathsSummary(cast: s.characters(inShow: "lwtv:show:101")),
                       "No recorded deaths among 2 listed characters.")
        XCTAssertEqual(Presentation.deathsSummary(cast: []),
                       "No queer characters are listed for this show in this snapshot.")
    }

    // MARK: Schedule — "unknown" vs "confirmed nothing upcoming"

    func testScheduleUnknownReadsDifferentlyFromConfirmedEmpty() {
        let unknown = Schedule(scheduleKnown: false, join: ScheduleJoin(method: .none, matched: false), tvmazeID: nil, tvmazeURL: nil, status: nil, premiered: nil, ended: nil, network: nil, webChannel: nil, nextEpisode: nil, previousEpisode: nil)
        let confirmedEmpty = Schedule(scheduleKnown: true, join: ScheduleJoin(method: .lwtvTvmazeID, matched: true), tvmazeID: 1, tvmazeURL: nil, status: "Ended", premiered: nil, ended: nil, network: nil, webChannel: nil, nextEpisode: nil, previousEpisode: nil)

        XCTAssertEqual(Presentation.nextEpisode(unknown), "Schedule unknown for this show.")
        XCTAssertEqual(Presentation.nextEpisode(confirmedEmpty), "No upcoming episode is known.")
        XCTAssertNotEqual(Presentation.nextEpisode(unknown), Presentation.nextEpisode(confirmedEmpty))
    }

    func testNextEpisodePresent() throws {
        let s = try Repo.fixture()
        // The fixture's next episode airs 2026-09-20; pin "today" before it.
        let text = Presentation.nextEpisode(try XCTUnwrap(s.show(id: "lwtv:show:101")).schedule, today: Self.day("2026-09-17"))
        XCTAssertTrue(text.hasPrefix("S3E4 “Fog Signal” — "), text)
        XCTAssertTrue(text.contains("2026"), text)
        XCTAssertFalse(text.contains("passed"), text)
    }

    /// A bundled or cached snapshot ages. Once the listed "next" episode's
    /// day is behind us, saying it is next would be a stale fact presented
    /// as current.
    func testNextEpisodeWhoseDateHasPassedIsNotPresentedAsUpcoming() throws {
        let schedule = try XCTUnwrap(try Repo.fixture().show(id: "lwtv:show:101")).schedule
        let onTheDay = Presentation.nextEpisode(schedule, today: Self.day("2026-09-20"))
        let dayAfter = Presentation.nextEpisode(schedule, today: Self.day("2026-09-21"))
        let weekAfter = Presentation.nextEpisode(schedule, today: Self.day("2026-09-27"))
        XCTAssertFalse(onTheDay.contains("passed"), onTheDay)
        XCTAssertFalse(dayAfter.contains("passed"), "one day of grace for broadcast time zones: \(dayAfter)")
        XCTAssertTrue(weekAfter.hasPrefix("S3E4 “Fog Signal” — listed for "), weekAfter)
        XCTAssertTrue(weekAfter.contains("which has passed. This data may be out of date."), weekAfter)
    }

    private static func day(_ ymd: String) -> Date {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        f.timeZone = TimeZone(identifier: "UTC")
        return f.date(from: ymd)!
    }

    // MARK: Show-level deaths — per character, with the source's limits stated

    func testShowDeathsNamesEachRecordedDeath() throws {
        let s = try Repo.fixture()
        let show = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        let deaths = Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show)
        XCTAssertEqual(deaths.headline, "1 of 2 listed characters has a recorded death.")
        XCTAssertEqual(deaths.lines, ["Odile Brandt dies (2017)."])
        XCTAssertEqual(deaths.notes, [], "the fixture's own tally agrees (1) and it has no death-revealing trope")
    }

    func testShowDeathsWithNoneRecordedNeverSaysNobodyDies() throws {
        let s = try Repo.fixture()
        let show = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        let deaths = Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show)
        XCTAssertEqual(deaths.headline, "No death is recorded for any of the 2 listed characters.")
        XCTAssertEqual(deaths.lines, [])
        let spoken = deaths.spoken.lowercased()
        for manufactured in ["survive", "nobody dies", "no one dies", "lives"] {
            XCTAssertFalse(spoken.contains(manufactured), "\(manufactured) is a fact LezWatch never records: \(deaths.spoken)")
        }
    }

    func testShowDeathsWithNoListedCastIsUnknownNotNo() throws {
        let s = try Repo.fixture()
        let show = try XCTUnwrap(s.show(id: "lwtv:show:104"))
        XCTAssertEqual(s.characters(inShow: show.id), [])
        let deaths = Presentation.showDeaths(cast: [], show: show)
        XCTAssertEqual(deaths.headline, "No queer characters are listed for this show in this snapshot, so there is no answer here.")
    }

    /// LezWatch records a death on the character. When the character is in
    /// more than one show, the record cannot say this show is where it
    /// happens, so the line says exactly that instead of "dies".
    func testADeadCharacterInSeveralShowsIsNotPinnedOnThisShow() throws {
        let data = try JSONEdit.editCharacter(try Repo.fixtureData(), index: 2) { odile in
            var shows = odile["shows"] as! [[String: Any]]
            shows.append(["show_id": "lwtv:show:101", "role": "guest", "years": []])
            odile["shows"] = shows
        }
        let s = try SnapshotDecoder().decode(data)
        let odile = try XCTUnwrap(s.character(id: "lwtv:character:203"))
        XCTAssertEqual(odile.shows.count, 2, "the edit landed")
        let show = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        let deaths = Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show)
        XCTAssertEqual(deaths.lines, ["Odile Brandt: a death is recorded (2017). Odile Brandt appears in 2 shows, and the record does not say which one."])
        XCTAssertFalse(deaths.lines[0].contains(" dies"), deaths.lines[0])
    }

    func testShowDeathsStatesADisagreeingSourceTally() throws {
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 1) { show in
            var counts = show["counts"] as! [String: Any]
            counts["deaths_source_reported"] = 0
            show["counts"] = counts
        }
        let s = try SnapshotDecoder().decode(data)
        let show = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        XCTAssertEqual(show.counts.deathsSourceReported, 0, "the edit landed")
        let deaths = Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show)
        XCTAssertEqual(deaths.notes, ["LezWatch.TV's own tally for this show is 0 deaths; its character records list 1."])
    }

    func testYearsAbsence() {
        XCTAssertEqual(Presentation.years(Years(start: nil, end: nil, onAir: .unknown)), "Air dates not recorded")
        XCTAssertEqual(Presentation.years(Years(start: 2021, end: nil, onAir: .yes)), "2021 – present")
        XCTAssertEqual(Presentation.years(Years(start: 2016, end: 2018, onAir: .no)), "2016 – 2018")
        XCTAssertEqual(Presentation.seasons(nil), "Seasons not recorded")
        XCTAssertEqual(Presentation.seasons(0), "Seasons not recorded", "LezWatch's 0 means never filled in, not zero seasons")
        XCTAssertEqual(Presentation.seasons(1), "1 season")
        XCTAssertEqual(Presentation.seasons(3), "3 seasons")
    }

    func testTermsListAbsence() {
        XCTAssertEqual(Presentation.terms([], empty: Presentation.noTropes), "No tropes listed.")
        XCTAssertEqual(Presentation.terms([Term(slug: "a", name: "A"), Term(slug: "b", name: "B")], empty: Presentation.noTropes), "A, B")
    }

    func testGeneratedAtIsLabelled() {
        XCTAssertTrue(Presentation.generatedAt(Date(timeIntervalSince1970: 0)).hasPrefix("Data as of "))
    }

    // MARK: Death spoilers never sit outside the reveal

    func testDeathRevealingTermsAreFilteredOutOfVisibleLists() {
        let cliches = [Term(slug: "student", name: "Student"), Term(slug: "dead", name: "Dead Queers"), Term(slug: "undead", name: "Undead")]
        XCTAssertEqual(Presentation.withoutSpoilers(cliches, Presentation.deathSpoilerClicheSlugs).map(\.slug), ["student", "undead"])
        let tropes = [Term(slug: "dead-queers", name: "Bury Your Queers"), Term(slug: "coming-out", name: "Coming Out")]
        XCTAssertEqual(Presentation.withoutSpoilers(tropes, Presentation.deathSpoilerTropeSlugs).map(\.slug), ["coming-out"])
    }

    func testTheBuryYourQueersTagMovesInsideTheShowReveal() throws {
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 0) { show in
            var tropes = show["tropes"] as! [[String: Any]]
            tropes.append(["slug": "dead-queers", "name": "Bury Your Queers"])
            show["tropes"] = tropes
        }
        let s = try SnapshotDecoder().decode(data)
        let show = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        XCTAssertTrue(show.tropes.contains { $0.slug == "dead-queers" }, "the edit landed")
        let deaths = Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show)
        XCTAssertEqual(deaths.headline, "No death is recorded for any of the 2 listed characters.")
        XCTAssertEqual(deaths.notes, ["LezWatch.TV tags this show “Bury Your Queers”."])
        XCTAssertFalse(Presentation.withoutSpoilers(show.tropes, Presentation.deathSpoilerTropeSlugs).contains { $0.slug == "dead-queers" })
    }
}
