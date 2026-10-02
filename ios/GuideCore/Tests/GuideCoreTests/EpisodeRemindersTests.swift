import Foundation
import XCTest
@testable import GuideCore

final class EpisodeRemindersTests: XCTestCase {
    private var utc: Calendar {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "UTC")!
        return c
    }

    private func date(_ iso: String) -> Date {
        ISO8601DateFormatter().date(from: iso)!
    }

    /// The fixture's Harbor Lights lists S3E4 "Fog Signal" on 2026-09-20.
    /// Its reminder names the show and the episode number, never the
    /// episode's name.
    func testAReminderNamesTheShowAndEpisodeButNotTheEpisodeTitle() throws {
        let s = try Repo.fixture()
        let plan = EpisodeReminders.plan(favoriteShowIDs: ["lwtv:show:101"], snapshot: s, now: date("2026-09-14T00:00:00Z"), calendar: utc)
        let r = try XCTUnwrap(plan.first)
        XCTAssertEqual(plan.count, 1)
        XCTAssertEqual(r.title, "Harbor Lights")
        // The fixture records an air time, so the reminder comes then.
        XCTAssertTrue(r.body.hasPrefix("S3E4 is listed to air now."), r.body)
        XCTAssertTrue(r.body.contains("TVmaze"), "the schedule's source is named")
        XCTAssertFalse(r.body.contains("Fog Signal"))
        XCTAssertFalse(r.title.contains("Fog Signal"))
        XCTAssertTrue(r.identifier.hasPrefix(EpisodeReminders.identifierPrefix))
    }

    /// Unknown and empty schedules get no reminder; a favorite the snapshot
    /// lacks is skipped; a show starred twice gets one.
    func testOnlyAListedFutureEpisodeGetsAReminder() throws {
        let s = try Repo.fixture()
        let ids = ["lwtv:show:101", "lwtv:show:101", "lwtv:show:102", "lwtv:show:103", "lwtv:show:104", "lwtv:show:gone"]
        let plan = EpisodeReminders.plan(favoriteShowIDs: ids, snapshot: s, now: date("2026-09-14T00:00:00Z"), calendar: utc)
        XCTAssertEqual(plan.map(\.showID), ["lwtv:show:101"])
    }

    func testAnEpisodeAlreadyAiredGetsNone() throws {
        let s = try Repo.fixture()
        XCTAssertEqual(EpisodeReminders.plan(favoriteShowIDs: ["lwtv:show:101"], snapshot: s, now: date("2026-09-25T00:00:00Z"), calendar: utc), [])
    }

    /// With a recorded air time, the reminder comes at the broadcast; with
    /// none (here the stamp is gone too), at 10:00 local on the air date,
    /// with words that give the date and never claim a time.
    func testFireDateUsesTheAirTimeElseTenInTheMorning() throws {
        let withTime = try editedFixture(airstamp: "2026-09-21T02:00:00+00:00")
        let a = try XCTUnwrap(EpisodeReminders.plan(favoriteShowIDs: ["lwtv:show:101"], snapshot: withTime, now: date("2026-09-14T00:00:00Z"), calendar: utc).first)
        XCTAssertEqual(a.fireDate, date("2026-09-21T02:00:00Z"))
        XCTAssertTrue(a.body.hasPrefix("S3E4 is listed to air now."), a.body)

        let dateOnly = try editedFixture(airstamp: nil)
        let b = try XCTUnwrap(EpisodeReminders.plan(favoriteShowIDs: ["lwtv:show:101"], snapshot: dateOnly, now: date("2026-09-14T00:00:00Z"), calendar: utc).first)
        XCTAssertEqual(b.fireDate, date("2026-09-20T10:00:00Z"))
        XCTAssertTrue(b.body.hasPrefix("S3E4 is listed for \(dayText("2026-09-20T10:00:00Z", in: utc)), the network's date, with no air time."), b.body)
        XCTAssertFalse(b.body.contains("now"), b.body)
        XCTAssertFalse(b.body.contains("today"), "the date is the network's, so the reminder never says today: \(b.body)")
    }

    /// TVmaze sends an `airstamp` even for an episode with no air time, and
    /// it is a placeholder (Ted Lasso's is 12:00 UTC, 5:00 a.m. Pacific). A
    /// reminder must not fire at it or word itself as if it were a time: it
    /// comes at 10:00 local on the air date and says no air time is listed.
    func testAPlaceholderAirstampIsNeverAFireTime() throws {
        var pacific = Calendar(identifier: .gregorian)
        pacific.timeZone = TimeZone(identifier: "America/Los_Angeles")!
        let placeholder = try editedFixture(airstamp: "2026-09-23T12:00:00+00:00", airdate: "2026-09-23", airtime: nil)
        let r = try XCTUnwrap(EpisodeReminders.plan(favoriteShowIDs: ["lwtv:show:101"], snapshot: placeholder, now: date("2026-09-14T00:00:00Z"), calendar: pacific).first)
        XCTAssertEqual(r.fireDate, date("2026-09-23T17:00:00Z"), "10:00 in Los Angeles, not the placeholder's 12:00 UTC")
        XCTAssertNotEqual(r.fireDate, date("2026-09-23T12:00:00Z"))
        XCTAssertTrue(r.body.hasPrefix("S3E4 is listed for \(dayText("2026-09-23T17:00:00Z", in: pacific)), the network's date, with no air time."), r.body)
        XCTAssertFalse(r.body.contains("to air now"), r.body)
    }

    /// The negative control for the test above. The same episode, the same
    /// stamp, changed in one field only: with an air time recorded the stamp
    /// is real and the reminder comes at it; with none it is not and the
    /// reminder comes at 10:00 local. So the outcome depends on `airtime`
    /// alone, and the placeholder test can fail.
    func testOnlyARecordedAirTimeMakesTheAirstampCount() throws {
        var pacific = Calendar(identifier: .gregorian)
        pacific.timeZone = TimeZone(identifier: "America/Los_Angeles")!
        let now = date("2026-09-14T00:00:00Z")
        let stamp = "2026-09-23T12:00:00+00:00"
        let noTime = try editedFixture(airstamp: stamp, airdate: "2026-09-23", airtime: nil)
        let emptyTime = try editedFixture(airstamp: stamp, airdate: "2026-09-23", airtime: "")
        let withTime = try editedFixture(airstamp: stamp, airdate: "2026-09-23", airtime: "12:00")
        let fires = try [noTime, emptyTime, withTime].map { snapshot in
            try XCTUnwrap(EpisodeReminders.plan(favoriteShowIDs: ["lwtv:show:101"], snapshot: snapshot, now: now, calendar: pacific).first)
        }
        XCTAssertEqual(fires[0].fireDate, date("2026-09-23T17:00:00Z"))
        XCTAssertEqual(fires[1].fireDate, date("2026-09-23T17:00:00Z"), "an empty air time is no air time")
        XCTAssertEqual(fires[2].fireDate, date("2026-09-23T12:00:00Z"), "a recorded air time makes the stamp count")
        XCTAssertTrue(fires[2].body.hasPrefix("S3E4 is listed to air now."), fires[2].body)
        XCTAssertNotEqual(fires[0].body, fires[2].body)
    }

    /// The real placeholders quoted in issue #56 (11 of 49 next episodes in
    /// the 2026-09-19 snapshot have no air time), in three time zones. Each
    /// fires at 10:00 local on its own air date; Grey's Anatomy has a real
    /// time and fires at it.
    func testTheRealPlaceholdersFireAtTenLocalAndTheRealTimeAtTheBroadcast() throws {
        let cases: [(name: String, airdate: String, airtime: String?, airstamp: String)] = [
            ("Days of Our Lives", "2026-09-21", nil, "2026-09-21T16:00:00+00:00"),
            ("Ted Lasso", "2026-09-23", nil, "2026-09-23T12:00:00+00:00"),
            ("Helluva Boss", "2026-10-14", nil, "2026-10-14T12:00:00+00:00"),
        ]
        for zone in ["America/Los_Angeles", "Asia/Tokyo", "Pacific/Auckland"] {
            var calendar = Calendar(identifier: .gregorian)
            calendar.timeZone = TimeZone(identifier: zone)!
            for c in cases {
                let episode = makeEpisode(airdate: c.airdate, airtime: c.airtime, airstamp: c.airstamp)
                let fire = try XCTUnwrap(EpisodeReminders.fireDate(for: episode, calendar: calendar), "\(c.name) in \(zone)")
                let parts = calendar.dateComponents([.year, .month, .day, .hour, .minute], from: fire)
                let want = c.airdate.split(separator: "-").compactMap { Int($0) }
                XCTAssertEqual([parts.year, parts.month, parts.day, parts.hour, parts.minute], [want[0], want[1], want[2], EpisodeReminders.fallbackHour, 0], "\(c.name) in \(zone)")
            }
            let greys = makeEpisode(airdate: "2026-10-15", airtime: "22:00", airstamp: "2026-10-16T02:00:00+00:00")
            XCTAssertEqual(EpisodeReminders.fireDate(for: greys, calendar: calendar), date("2026-10-16T02:00:00Z"), zone)
        }
    }

    func testNoAirDateMeansNoReminder() throws {
        let s = try editedFixture(airstamp: nil, airdate: nil)
        XCTAssertEqual(EpisodeReminders.plan(favoriteShowIDs: ["lwtv:show:101"], snapshot: s, now: date("2026-09-14T00:00:00Z"), calendar: utc), [])
    }

    /// On the real snapshot with every show starred: at most 60, soonest
    /// first, all in the future, none carrying an episode name or a word
    /// about death.
    func testRealSnapshotPlanIsCappedSortedAndSpoilerFree() throws {
        let s = try SnapshotDecoder().decode(try Data(contentsOf: Repo.bundledSnapshot))
        let now = s.generatedAt
        let plan = EpisodeReminders.plan(favoriteShowIDs: s.shows.map(\.id), snapshot: s, now: now)
        XCTAssertFalse(plan.isEmpty, "the real snapshot lists no upcoming episode")
        XCTAssertLessThanOrEqual(plan.count, EpisodeReminders.limit)
        XCTAssertEqual(plan.map(\.fireDate), plan.map(\.fireDate).sorted())
        XCTAssertTrue(plan.allSatisfy { $0.fireDate > now })
        XCTAssertEqual(Set(plan.map(\.identifier)).count, plan.count, "identifiers collide")

        let titles = Set(s.shows.map(\.title))
        let names = s.shows.compactMap { $0.schedule.nextEpisode?.name }.filter { $0.count > 3 && $0 != "TBA" && !titles.contains($0) }
        for r in plan {
            // The body only: a show's own title can hold these words
            // ("The Walking Dead") and is shown on every screen anyway.
            let text = r.body.lowercased()
            for word in ["dies", "died", "death", "dead"] {
                XCTAssertFalse(text.contains(word), "\(r.identifier) says \(word)")
            }
            XCTAssertEqual(r.title, s.show(id: r.showID)?.title, "the title is the show's, nothing more")
            for name in names where r.body.contains(name) {
                XCTFail("\(r.identifier) carries the episode name \(name)")
            }
        }
    }

    /// On the real snapshot, an episode with no recorded air time never has
    /// a reminder at its placeholder stamp: it is at 10:00 local on the air
    /// date, and its words claim no air time. (It asserts nothing about how
    /// many such episodes there are: that changes with the data.)
    func testRealSnapshotDateOnlyEpisodesFireAtTenLocalOnTheirDate() throws {
        let s = try SnapshotDecoder().decode(try Data(contentsOf: Repo.bundledSnapshot))
        let plan = EpisodeReminders.plan(favoriteShowIDs: s.shows.map(\.id), snapshot: s, now: s.generatedAt, calendar: utc, limit: .max)
        for r in plan {
            let episode = try XCTUnwrap(s.show(id: r.showID)?.schedule.nextEpisode)
            let hasTime = !(episode.airtime ?? "").trimmingCharacters(in: .whitespaces).isEmpty
            if hasTime {
                XCTAssertEqual(r.fireDate, episode.airInstant, r.identifier)
            } else {
                let parts = utc.dateComponents([.year, .month, .day, .hour], from: r.fireDate)
                let want = (episode.airdate ?? "").split(separator: "-").compactMap { Int($0) }
                XCTAssertEqual([parts.year, parts.month, parts.day, parts.hour], want + [EpisodeReminders.fallbackHour], "\(r.identifier) is not 10:00 on its air date")
                XCTAssertFalse(r.body.contains("to air now"), r.body)
                XCTAssertTrue(r.body.contains("no air time"), r.body)
            }
        }
    }

    /// The cap keeps the soonest reminders and drops only later ones. The
    /// real snapshot lists fewer than 60 upcoming episodes, so the cap is
    /// exercised with a smaller limit on the same data.
    func testTheCapKeepsTheSoonest() throws {
        let s = try SnapshotDecoder().decode(try Data(contentsOf: Repo.bundledSnapshot))
        let all = EpisodeReminders.plan(favoriteShowIDs: s.shows.map(\.id), snapshot: s, now: s.generatedAt, limit: .max)
        XCTAssertGreaterThan(all.count, 5, "too few upcoming episodes to test a cap")
        let capped = EpisodeReminders.plan(favoriteShowIDs: s.shows.map(\.id), snapshot: s, now: s.generatedAt, limit: 5)
        XCTAssertEqual(capped, Array(all.prefix(5)))
        XCTAssertEqual(EpisodeReminders.limit, 60, "iOS keeps at most 64 pending local notifications per app")
    }

    /// The fixture's first show, its next episode edited. Its own air time
    /// is "21:00"; pass `airtime: nil` for a JSON null.
    private func editedFixture(airstamp: String?, airdate: String? = "2026-09-20", airtime: String? = "21:00") throws -> Snapshot {
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 0) { show in
            var schedule = show["schedule"] as! [String: Any]
            var episode = schedule["next_episode"] as! [String: Any]
            episode["airstamp"] = airstamp ?? NSNull()
            episode["airdate"] = airdate ?? NSNull()
            episode["airtime"] = airtime ?? NSNull()
            schedule["next_episode"] = episode
            show["schedule"] = schedule
        }
        let s = try SnapshotDecoder().decode(data)
        let edited = try XCTUnwrap(s.shows[0].schedule.nextEpisode)
        XCTAssertEqual(edited.airstamp, airstamp, "the edit landed")
        XCTAssertEqual(edited.airdate, airdate, "the edit landed")
        XCTAssertEqual(edited.airtime, airtime, "the edit landed")
        return s
    }

    private func makeEpisode(airdate: String?, airtime: String?, airstamp: String?) -> Episode {
        Episode(tvmazeID: 1, season: 1, number: 1, name: nil, airdate: airdate, airtime: airtime, airstamp: airstamp, runtime: nil, url: URL(fileURLWithPath: "/episodes/1"))
    }

    /// `iso` (an instant) as "Sep 20" in `calendar`'s zone: what the
    /// reminder's words should say for that air date.
    private func dayText(_ iso: String, in calendar: Calendar) -> String {
        let f = DateFormatter()
        f.calendar = calendar
        f.timeZone = calendar.timeZone
        f.setLocalizedDateFormatFromTemplate("MMMd")
        return f.string(from: date(iso))
    }
}
