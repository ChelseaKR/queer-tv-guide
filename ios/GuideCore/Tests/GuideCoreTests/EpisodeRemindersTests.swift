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

    /// With an air time, the reminder comes at the broadcast; without one,
    /// at 10:00 local on the air date.
    func testFireDateUsesTheAirstampElseTenInTheMorning() throws {
        let withStamp = try editedFixture(airstamp: "2026-09-21T02:00:00+00:00")
        let a = try XCTUnwrap(EpisodeReminders.plan(favoriteShowIDs: ["lwtv:show:101"], snapshot: withStamp, now: date("2026-09-14T00:00:00Z"), calendar: utc).first)
        XCTAssertEqual(a.fireDate, date("2026-09-21T02:00:00Z"))

        let noStamp = try editedFixture(airstamp: nil)
        let b = try XCTUnwrap(EpisodeReminders.plan(favoriteShowIDs: ["lwtv:show:101"], snapshot: noStamp, now: date("2026-09-14T00:00:00Z"), calendar: utc).first)
        XCTAssertEqual(b.fireDate, date("2026-09-20T10:00:00Z"))
        XCTAssertTrue(b.body.hasPrefix("S3E4 is listed for today."), b.body)
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

    private func editedFixture(airstamp: String?, airdate: String? = "2026-09-20") throws -> Snapshot {
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 0) { show in
            var schedule = show["schedule"] as! [String: Any]
            var episode = schedule["next_episode"] as! [String: Any]
            episode["airstamp"] = airstamp ?? NSNull()
            episode["airdate"] = airdate ?? NSNull()
            schedule["next_episode"] = episode
            show["schedule"] = schedule
        }
        let s = try SnapshotDecoder().decode(data)
        XCTAssertEqual(s.shows[0].schedule.nextEpisode?.airstamp, airstamp, "the edit landed")
        return s
    }
}
