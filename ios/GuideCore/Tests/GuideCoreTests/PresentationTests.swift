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
        let text = Presentation.nextEpisode(try XCTUnwrap(s.show(id: "lwtv:show:101")).schedule)
        XCTAssertTrue(text.hasPrefix("S3E4 “Fog Signal” — "), text)
        XCTAssertTrue(text.contains("2026"), text)
    }

    func testYearsAbsence() {
        XCTAssertEqual(Presentation.years(Years(start: nil, end: nil, onAir: .unknown)), "Air dates not recorded")
        XCTAssertEqual(Presentation.years(Years(start: 2021, end: nil, onAir: .yes)), "2021 – present")
        XCTAssertEqual(Presentation.years(Years(start: 2016, end: 2018, onAir: .no)), "2016 – 2018")
        XCTAssertEqual(Presentation.seasons(nil), "Seasons not recorded")
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
}
