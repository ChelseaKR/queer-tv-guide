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
        XCTAssertEqual(Presentation.worthIt("Extremely"), "Extremely", "an unrecognized value is still shown, not hidden")
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
        XCTAssertEqual(notRecordedText, "Not recorded. This snapshot does not record a death for Mara Quill.")

        XCTAssertFalse(notRecordedText.lowercased().contains("survive"), "the contract has no survives state to assert")
        XCTAssertFalse(Self.opensWithNo(notRecordedText), "must not read as a flat 'No' answer to 'does she die'")
        XCTAssertNotEqual(Presentation.deathShort(recorded), Presentation.deathShort(notRecorded))
    }

    /// "No death is recorded …" opens with "No", and a VoiceOver user who
    /// moves on after the first word hears "No" to "does she die?". Every
    /// unknown answer, per character and per show, opens with "Not recorded".
    func testEveryUnknownDeathAnswerOpensWithNotRecordedNeverNo() throws {
        let s = try Repo.fixture()
        let notRecorded = Death(died: nil, deathKnown: false, dates: [], years: [])
        let noneDead = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        let noCast = try XCTUnwrap(s.show(id: "lwtv:show:104"))
        let oneAlive = try XCTUnwrap(s.characters(inShow: noneDead.id).first)
        let answers = [
            Presentation.death(notRecorded, name: "Mara Quill"),
            Presentation.showDeaths(cast: s.characters(inShow: noneDead.id), show: noneDead).headline,
            Presentation.showDeaths(cast: [oneAlive], show: noneDead).headline,
            Presentation.showDeaths(cast: [], show: noCast).headline,
            Presentation.deathsSummary(cast: s.characters(inShow: noneDead.id)),
            Presentation.deathsSummary(cast: []),
        ]
        XCTAssertEqual(answers.count, 6, "the denominator")
        for answer in answers {
            XCTAssertTrue(answer.hasPrefix("Not recorded"), answer)
            XCTAssertFalse(Self.opensWithNo(answer), answer)
        }
        XCTAssertEqual(Presentation.deathShort(notRecorded), "Death not recorded")
        // The detector itself: a bare "No" opener is caught, "Not" is not.
        XCTAssertTrue(Self.opensWithNo("No death is recorded for Mara Quill."))
        XCTAssertTrue(Self.opensWithNo("No. Mara Quill lives."))
        XCTAssertFalse(Self.opensWithNo("Not recorded."))
    }

    /// True when `text` opens with the word "No" (not "Not", "None", …).
    static func opensWithNo(_ text: String) -> Bool {
        text.range(of: #"^\s*No\b"#, options: [.regularExpression, .caseInsensitive]) != nil
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
                       "Not recorded for any of the 2 listed characters.")
        XCTAssertEqual(Presentation.deathsSummary(cast: []),
                       "Not recorded. This snapshot does not list any queer characters for this show.")
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
        XCTAssertTrue(weekAfter.hasPrefix("S3E4 “Fog Signal” — "), weekAfter)
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
        XCTAssertEqual(deaths.headline, "Not recorded. This snapshot does not record a death for any of the 2 listed characters.")
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
        XCTAssertEqual(deaths.headline, "Not recorded. This snapshot does not list any queer characters for this show.")
    }

    /// Odile Brandt (dies 2017, a regular on show 102 in 2016-2018) also
    /// linked to show 101 with `years`, so the death-placement rule
    /// (DECISIONS 0030) can be read on both shows.
    private func odileAlsoIn101(years: [String], deathYears: [Int]? = nil) throws -> Snapshot {
        let data = try JSONEdit.editCharacter(try Repo.fixtureData(), index: 2) { odile in
            var shows = odile["shows"] as! [[String: Any]]
            shows.append(["show_id": "lwtv:show:101", "role": "guest", "years": years])
            odile["shows"] = shows
            if let deathYears {
                var death = odile["death"] as! [String: Any]
                death["years"] = deathYears
                death["dates"] = deathYears.map { ["date": NSNull(), "year": $0, "raw": "\($0)"] as [String: Any] }
                odile["death"] = death
            }
        }
        let s = try SnapshotDecoder().decode(data)
        XCTAssertEqual(try XCTUnwrap(s.character(id: "lwtv:character:203")).shows.count, 2, "the edit landed")
        return s
    }

    /// The L Word: Generation Q case. LezWatch records a death on the
    /// character; Dana Fairbanks dies in 2007 in The L Word and is a 2022
    /// guest in Generation Q. A death outside the character's years in this
    /// show is not counted here, and is not called "dies" here.
    func testADeathOutsideTheCharactersYearsInThisShowIsNotCountedHere() throws {
        let s = try odileAlsoIn101(years: ["2022"])
        let show = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        let deaths = Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show)
        XCTAssertEqual(deaths.headline, "Not recorded. This snapshot does not record a death in this show for any of the 3 listed characters.")
        XCTAssertEqual(deaths.lines, ["Odile Brandt: not recorded in this show. LezWatch.TV records a death for Odile Brandt (2017), but not in a year Odile Brandt appears in this show. It may happen in another show."])
        XCTAssertEqual(deaths.notes, ["One listed character has a recorded death that LezWatch.TV does not place in this show, so it is not counted here."])
        XCTAssertFalse(deaths.lines[0].contains(" dies"), deaths.lines[0])
        XCTAssertTrue(deaths.headline.hasPrefix("Not recorded."), "an unknown answer opens with Not recorded")
        // The show the death falls in still counts it, and says why.
        let home = try XCTUnwrap(s.show(id: "lwtv:show:102"))
        let there = Presentation.showDeaths(cast: s.characters(inShow: home.id), show: home)
        XCTAssertEqual(there.headline, "1 of 2 listed characters has a recorded death.")
        XCTAssertEqual(there.lines, ["Odile Brandt dies (2017). The record belongs to the character, not to one show; it is counted here because 2017 is among Odile Brandt\u{2019}s years in this show."])
        XCTAssertEqual(there.notes, [])
    }

    func testADeathInTheCharactersYearsInThisShowIsCountedHere() throws {
        let s = try odileAlsoIn101(years: ["2017", "2018"])
        let show = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        let deaths = Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show)
        XCTAssertEqual(deaths.headline, "1 of 3 listed characters has a recorded death.")
        XCTAssertEqual(deaths.lines, ["Odile Brandt dies (2017). The record belongs to the character, not to one show; it is counted here because 2017 is among Odile Brandt\u{2019}s years in this show."])
        XCTAssertEqual(deaths.notes, ["LezWatch.TV's own tally for this show is 0 deaths; its character records list 1."])
    }

    /// A link with no years, or a death with no year, cannot be placed, so
    /// for a multi-show character it is unknown here, not a guess.
    func testADeathThatCannotBePlacedIsUnknownHere() throws {
        let noLinkYears = try odileAlsoIn101(years: [])
        let show = try XCTUnwrap(noLinkYears.show(id: "lwtv:show:101"))
        let a = Presentation.showDeaths(cast: noLinkYears.characters(inShow: show.id), show: show)
        XCTAssertEqual(a.headline, "Not recorded. This snapshot does not record a death in this show for any of the 3 listed characters.")
        XCTAssertEqual(a.lines, ["Odile Brandt: not recorded in this show. LezWatch.TV records a death for Odile Brandt (2017) but not Odile Brandt\u{2019}s years in this show, so it cannot say whether it happens here."])

        let noDeathYear = try odileAlsoIn101(years: ["2021"], deathYears: [])
        let home = try XCTUnwrap(noDeathYear.show(id: "lwtv:show:102"))
        let b = Presentation.showDeaths(cast: noDeathYear.characters(inShow: home.id), show: home)
        XCTAssertEqual(b.headline, "Not recorded. This snapshot does not record a death in this show for any of the 2 listed characters.")
        XCTAssertEqual(b.lines, ["Odile Brandt: not recorded in this show. LezWatch.TV records a death for Odile Brandt but no year, so it cannot say whether it happens in this show."])
        XCTAssertEqual(b.notes, [
            "One listed character has a recorded death that LezWatch.TV does not place in this show, so it is not counted here.",
            "LezWatch.TV's own tally for this show is 1 death; its character records place 0 in this show.",
        ])
        let odile = try XCTUnwrap(noDeathYear.character(id: "lwtv:character:203"))
        XCTAssertEqual(Presentation.deathPlacement(odile, inShow: home.id), .noDeathYear)
        XCTAssertFalse(Presentation.deathPlacement(odile, inShow: home.id).counts)
    }

    /// A character in one show keeps its death there, with or without years.
    func testAOneShowCharacterKeepsItsDeath() throws {
        let s = try Repo.fixture()
        let odile = try XCTUnwrap(s.character(id: "lwtv:character:203"))
        XCTAssertEqual(Presentation.deathPlacement(odile, inShow: "lwtv:show:102"), .onlyShow)
        let alive = try XCTUnwrap(s.character(id: "lwtv:character:204"))
        XCTAssertEqual(Presentation.deathPlacement(alive, inShow: "lwtv:show:102"), .notRecorded)
    }

    // MARK: Trigger-warning level, labeled and explained

    func testTriggerLevelIsLabeledAndSaysWhatItMeasures() {
        let high = Presentation.triggerWarning([Term(slug: "high", name: "High")])
        XCTAssertEqual(high.heading, "LezWatch.TV trigger-warning level")
        XCTAssertEqual(high.level, "High")
        XCTAssertEqual(high.meaning, "LezWatch.TV: \u{201c}Scenes of explicit violence, drug use, suicide, sex, and/or abuse occur regularly. Not intended for children or sensitive viewers.\u{201d}")
        XCTAssertTrue(high.spoken.hasPrefix("LezWatch.TV trigger-warning level: High."), high.spoken)
        for slug in ["low", "medium"] {
            let w = Presentation.triggerWarning([Term(slug: slug, name: slug.capitalized)])
            XCTAssertTrue(w.meaning.hasPrefix("LezWatch.TV: \u{201c}"), w.meaning)
        }
    }

    func testAnUnratedShowSaysUnratedNeverNone() {
        let w = Presentation.triggerWarning([])
        XCTAssertEqual(w.level, "Not rated")
        XCTAssertEqual(w.meaning, "LezWatch.TV has not given this show a level. That does not mean it has no difficult content.")
        XCTAssertFalse(w.level.lowercased().contains("none"))
    }

    func testAnUnknownLevelIsShownAsItselfWithoutAMadeUpMeaning() {
        let w = Presentation.triggerWarning([Term(slug: "violence", name: "Violence")])
        XCTAssertEqual(w.level, "Violence")
        XCTAssertEqual(w.meaning, "LezWatch.TV gives this level without a description in this snapshot.")
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

    func testGeneratedAtIsLabeled() {
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
        XCTAssertEqual(deaths.headline, "Not recorded. This snapshot does not record a death for any of the 2 listed characters.")
        XCTAssertEqual(deaths.notes, ["LezWatch.TV tags this show “Bury Your Queers”."])
        XCTAssertFalse(Presentation.withoutSpoilers(show.tropes, Presentation.deathSpoilerTropeSlugs).contains { $0.slug == "dead-queers" })
    }
    func testEveryFateTropeIsASpoilerAndOrdinaryTropesStayVisible() {
        XCTAssertEqual(Presentation.deathSpoilerTropeSlugs, ["dead-queers", "happy-then-not", "none"])
        let tropes = [
            Term(slug: "coming-out", name: "Coming Out"),
            Term(slug: "happy-then-not", name: "Happiness then Tragedy"),
            Term(slug: "dead-queers", name: "Bury Your Queers"),
            Term(slug: "happy-ending", name: "Happy Ending"),
            Term(slug: "none", name: "None!"),
            Term(slug: "slow-burn", name: "Slow Burn"),
        ]
        XCTAssertEqual(Presentation.withoutSpoilers(tropes, Presentation.deathSpoilerTropeSlugs).map(\.slug), ["coming-out", "happy-ending", "slow-burn"])
    }

    func testHappinessThenTragedyMovesInsideTheShowReveal() throws {
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 0) { show in
            show["tropes"] = (show["tropes"] as! [[String: Any]]) + [
                ["slug": "happy-then-not", "name": "Happiness then Tragedy"],
                ["slug": "dead-queers", "name": "Bury Your Queers"],
            ]
        }
        let s = try SnapshotDecoder().decode(data)
        let show = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        XCTAssertTrue(show.tropes.contains { $0.slug == "happy-then-not" }, "the edit landed")
        let visible = Presentation.withoutSpoilers(show.tropes, Presentation.deathSpoilerTropeSlugs)
        XCTAssertFalse(visible.contains { $0.slug == "happy-then-not" || $0.slug == "dead-queers" })
        XCTAssertFalse(visible.isEmpty, "the fixture's ordinary tropes stay visible")
        let deaths = Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show)
        XCTAssertEqual(deaths.notes, [
            "LezWatch.TV tags this show “Happiness then Tragedy”.",
            "LezWatch.TV tags this show “Bury Your Queers”.",
        ])
        XCTAssertTrue(deaths.spoken.contains("Happiness then Tragedy"), "VoiceOver hears it only inside the reveal")
    }

    func testNoneTropeMovesInsideTheShowRevealEvenWithNoCast() throws {
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 0) { show in
            show["tropes"] = [["slug": "none", "name": "None!"]]
        }
        let s = try SnapshotDecoder().decode(data)
        let show = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        XCTAssertEqual(Presentation.withoutSpoilers(show.tropes, Presentation.deathSpoilerTropeSlugs), [])
        XCTAssertEqual(Presentation.showDeaths(cast: [], show: show).notes, ["LezWatch.TV lists no tropes for this show (“None!”)."])
        XCTAssertEqual(Presentation.showDeaths(cast: s.characters(inShow: show.id), show: show).notes.last, "LezWatch.TV lists no tropes for this show (“None!”).")
    }
}
