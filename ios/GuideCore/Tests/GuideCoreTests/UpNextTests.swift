import Foundation
import XCTest
@testable import GuideCore

/// The widget's file and its text (`UpNext`, `UpNextPresentation`).
final class UpNextTests: XCTestCase {
    private func day(_ ymd: String) -> Date {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate, .withDashSeparatorInDate]
        f.timeZone = TimeZone(identifier: "UTC")
        return f.date(from: ymd)!
    }

    // MARK: Building the file

    /// The four schedule states in the fixture map to the four statuses, in
    /// favorites order, and a favorite the snapshot lacks is counted.
    func testEveryScheduleStateIsKeptApart() throws {
        let s = try Repo.fixture()
        let upNext = UpNext(favoriteShowIDs: ["lwtv:show:101", "lwtv:show:102", "lwtv:show:103", "lwtv:show:gone"], snapshot: s)
        XCTAssertEqual(upNext.items.map(\.showID), ["lwtv:show:101", "lwtv:show:102", "lwtv:show:103"])
        XCTAssertEqual(upNext.items.map(\.status), [.dated, .noneListed, .unknown])
        XCTAssertEqual(upNext.missingShowCount, 1)
        XCTAssertEqual(upNext.snapshotGeneratedAt, s.generatedAt)
        let dated = upNext.items[0]
        XCTAssertEqual(dated.season, 3)
        XCTAssertEqual(dated.number, 4)
        XCTAssertEqual(dated.airdate, "2026-09-20")
    }

    func testAnEpisodeWithNoAirDateIsUndatedNotDated() throws {
        let data = try JSONEdit.editShow(try Repo.fixtureData(), index: 0) { show in
            var schedule = show["schedule"] as! [String: Any]
            var episode = schedule["next_episode"] as! [String: Any]
            episode["airdate"] = NSNull()
            schedule["next_episode"] = episode
            show["schedule"] = schedule
        }
        let s = try SnapshotDecoder().decode(data)
        let item = try XCTUnwrap(UpNext(favoriteShowIDs: ["lwtv:show:101"], snapshot: s).items.first)
        XCTAssertEqual(item.status, .undated, "the edit landed")
        XCTAssertNil(item.airdate)
        XCTAssertEqual(UpNextPresentation.line(item, today: day("2026-09-14")), "S3E4 · air date not recorded")
    }

    func testAShowStarredTwiceIsListedOnce() throws {
        let upNext = UpNext(favoriteShowIDs: ["lwtv:show:101", "lwtv:show:101"], snapshot: try Repo.fixture())
        XCTAssertEqual(upNext.items.count, 1)
    }

    // MARK: Spoiler safety

    /// Every key the file can carry. Nothing about a death, and no episode
    /// name: the widget sits on a screen anyone can glance at. Adding a
    /// field fails here, so a new one is a decision, not a drift.
    static let allowedKeys: Set<String> = [
        "formatVersion", "snapshotGeneratedAt", "items", "missingShowCount",
        "showID", "title", "status", "season", "number", "airdate",
    ]

    /// Every key in a JSON document, at any depth.
    static func keys(in json: Any) -> Set<String> {
        if let dict = json as? [String: Any] {
            return Set(dict.keys).union(dict.values.flatMap { keys(in: $0) })
        }
        if let array = json as? [Any] {
            return Set(array.flatMap { keys(in: $0) })
        }
        return []
    }

    /// Built from the real bundled snapshot with every show starred: the
    /// file holds only the allowed keys, and none of the real snapshot's
    /// episode names.
    func testTheFileCarriesNoDeathDataAndNoEpisodeNamesOnRealData() throws {
        let s = try SnapshotDecoder().decode(try Data(contentsOf: Repo.bundledSnapshot))
        let upNext = UpNext(favoriteShowIDs: s.shows.map(\.id), snapshot: s)
        XCTAssertEqual(upNext.items.count, s.shows.count)
        let data = try UpNextStore.encoder().encode(upNext)
        let json = try JSONSerialization.jsonObject(with: data)
        XCTAssertEqual(Self.keys(in: json).subtracting(Self.allowedKeys), [])

        let text = String(decoding: data, as: UTF8.self)
        for word in ["death", "died", "dies", "dead"] {
            XCTAssertFalse(Self.keys(in: json).contains { $0.lowercased().contains(word) }, word)
        }
        // Episode names that are not also a show title (a show can be named
        // like an episode of another) never reach the file.
        let titles = Set(s.shows.map(\.title))
        let names = s.shows.compactMap { $0.schedule.nextEpisode?.name }
            .filter { $0.count > 3 && !titles.contains($0) && $0 != "TBA" }
        XCTAssertFalse(names.isEmpty, "the real snapshot has no episode names to check for")
        for name in names {
            XCTAssertFalse(text.contains("\"\(name)\""), "episode name \(name) is in the widget file")
        }
    }

    /// Negative control for the key check: a field the file must not carry
    /// is caught.
    func testTheKeyCheckCatchesAnAddedField() throws {
        let upNext = UpNext(favoriteShowIDs: ["lwtv:show:101"], snapshot: try Repo.fixture())
        var json = try XCTUnwrap(JSONSerialization.jsonObject(with: try UpNextStore.encoder().encode(upNext)) as? [String: Any])
        var items = try XCTUnwrap(json["items"] as? [[String: Any]])
        items[0]["deathKnown"] = true
        items[0]["name"] = "Fog Signal"
        json["items"] = items
        XCTAssertEqual(Self.keys(in: json).subtracting(Self.allowedKeys), ["deathKnown", "name"])
    }

    /// The fixture's next episode is named "Fog Signal"; the file never
    /// says so.
    func testTheFixturesEpisodeNameIsLeftOut() throws {
        let upNext = UpNext(favoriteShowIDs: ["lwtv:show:101"], snapshot: try Repo.fixture())
        let text = String(decoding: try UpNextStore.encoder().encode(upNext), as: UTF8.self)
        XCTAssertFalse(text.contains("Fog Signal"))
        XCTAssertTrue(text.contains("Harbor Lights"), "the check reads the right file")
    }

    // MARK: Order

    func testOrderIsSoonestFirstThenPassedThenUndatedThenNoneThenUnknown() {
        let items = [
            UpNext.Item(showID: "unknown", title: "U", status: .unknown),
            UpNext.Item(showID: "none", title: "N", status: .noneListed),
            UpNext.Item(showID: "later", title: "L", status: .dated, season: 1, number: 2, airdate: "2026-10-20"),
            UpNext.Item(showID: "undated", title: "D", status: .undated, season: 1, number: 1),
            UpNext.Item(showID: "passed", title: "P", status: .dated, season: 1, number: 1, airdate: "2026-09-01"),
            UpNext.Item(showID: "soon", title: "S", status: .dated, season: 4, number: 1, airdate: "2026-09-20"),
        ]
        let upNext = UpNext(snapshotGeneratedAt: day("2026-09-18"), items: items, missingShowCount: 0)
        XCTAssertEqual(upNext.ordered(today: day("2026-09-18")).map(\.showID), ["soon", "later", "passed", "undated", "none", "unknown"])
        // Once "soon" has passed (after the one-day grace), it moves down.
        XCTAssertEqual(upNext.ordered(today: day("2026-09-23")).map(\.showID), ["later", "passed", "soon", "undated", "none", "unknown"])
    }

    // MARK: Text

    func testLinesStateEveryAbsenceAndNeverCallAPassedDateUpcoming() {
        let today = day("2026-09-18")
        let upcoming = UpNext.Item(showID: "a", title: "A", status: .dated, season: 23, number: 1, airdate: "2026-10-15")
        let passed = UpNext.Item(showID: "b", title: "B", status: .dated, season: 2, number: 5, airdate: "2026-09-01")
        let noNumber = UpNext.Item(showID: "c", title: "C", status: .dated, airdate: "2026-10-15")
        XCTAssertEqual(UpNextPresentation.line(upcoming, today: today), "S23E1 · Oct 15")
        XCTAssertEqual(UpNextPresentation.line(passed, today: today), "S2E5 · Sep 1, passed")
        XCTAssertEqual(UpNextPresentation.line(noNumber, today: today), "Next episode · Oct 15")
        XCTAssertEqual(UpNextPresentation.line(UpNext.Item(showID: "d", title: "D", status: .unknown), today: today), "Schedule unknown")
        XCTAssertEqual(UpNextPresentation.line(UpNext.Item(showID: "e", title: "E", status: .noneListed), today: today), "No upcoming episode listed")
    }

    /// VoiceOver hears words, not "S23E1", and a passed date says the data
    /// may be old.
    func testSpokenTextIsWords() {
        let today = day("2026-09-18")
        let upcoming = UpNext.Item(showID: "a", title: "Grey’s Anatomy", status: .dated, season: 23, number: 1, airdate: "2026-10-15")
        XCTAssertEqual(UpNextPresentation.spoken(upcoming, today: today), "Grey’s Anatomy. Season 23, episode 1, October 15.")
        let passed = UpNext.Item(showID: "b", title: "B", status: .dated, season: 2, number: 5, airdate: "2026-09-01")
        XCTAssertEqual(UpNextPresentation.spoken(passed, today: today), "B. Season 2, episode 5 was listed for September 1, which has passed. This data may be out of date.")
        XCTAssertEqual(UpNextPresentation.spoken(UpNext.Item(showID: "c", title: "C", status: .unknown), today: today), "C. Schedule unknown.")
    }

    /// The data's age is always stated; past 48 hours it says out of date,
    /// and a date in the future is never shown as current.
    func testDataAgeIsHonest() {
        let generated = ISO8601DateFormatter().date(from: "2026-09-18T09:44:42Z")!
        XCTAssertEqual(UpNextPresentation.dataAge(generated, now: generated.addingTimeInterval(3600)), "Data as of Sep 18")
        XCTAssertEqual(UpNextPresentation.freshness(of: generated, now: generated.addingTimeInterval(47 * 3600)), .current)
        XCTAssertEqual(UpNextPresentation.dataAge(generated, now: generated.addingTimeInterval(49 * 3600)), "Out of date: data as of Sep 18")
        XCTAssertEqual(UpNextPresentation.dataAge(generated, now: generated.addingTimeInterval(-2 * 3600)), "Data age unknown")
        XCTAssertEqual(UpNextPresentation.freshness(of: generated, now: generated.addingTimeInterval(-30 * 60)), .current, "a clock a few minutes slow is not an unknown age")
    }

    /// The same 48 hours the data cards promise.
    func testTheStaleThresholdIsTheDataCardsSLA() throws {
        XCTAssertEqual(UpNextPresentation.staleAfter, 48 * 3600)
        let repo = Repo.iosRoot.deletingLastPathComponent()
        for card in ["docs/data/lezwatch.md", "docs/data/tvmaze.md"] {
            let text = try String(contentsOf: repo.appendingPathComponent(card), encoding: .utf8)
            XCTAssertTrue(text.contains("| Staleness SLA | 48 hours"), "\(card) no longer promises 48 hours")
        }
    }

    func testMoreCountsOnlyWhatDidNotFit() {
        XCTAssertNil(UpNextPresentation.more(0))
        XCTAssertNil(UpNextPresentation.more(-2))
        XCTAssertEqual(UpNextPresentation.more(2), "+2 more")
        XCTAssertEqual(UpNextPresentation.more(2, missing: 1), "+2 more, 1 not in this data")
        XCTAssertEqual(UpNextPresentation.more(0, missing: 3), "3 not in this data")
    }

    // MARK: Store

    func testStoreRoundTripsAndWritesOnlyWhenChanged() throws {
        let store = UpNextStore(directory: try Repo.temporaryDirectory())
        XCTAssertNil(store.read(), "no file yet")
        let upNext = UpNext(favoriteShowIDs: ["lwtv:show:101"], snapshot: try Repo.fixture())
        XCTAssertTrue(try store.write(upNext))
        XCTAssertEqual(store.read(), upNext)
        XCTAssertFalse(try store.write(upNext), "an unchanged file is not rewritten")
        let changed = UpNext(favoriteShowIDs: ["lwtv:show:101", "lwtv:show:102"], snapshot: try Repo.fixture())
        XCTAssertTrue(try store.write(changed))
        XCTAssertEqual(store.read(), changed)
    }

    /// A file of another format version, or one that does not decode, reads
    /// as no file: the widget says to open the app rather than guessing.
    func testAnUnreadableOrOtherVersionFileReadsAsNone() throws {
        let store = UpNextStore(directory: try Repo.temporaryDirectory())
        let other = UpNext(formatVersion: 99, snapshotGeneratedAt: Date(), items: [], missingShowCount: 0)
        try UpNextStore.encoder().encode(other).write(to: store.fileURL)
        XCTAssertNil(store.read())
        try Data("not json".utf8).write(to: store.fileURL)
        XCTAssertNil(store.read())
    }

    /// The App Group both entitlements files name is the one the code uses.
    func testBothTargetsShareTheAppGroupTheCodeNames() throws {
        for path in ["QueerTVGuide/QueerTVGuide.entitlements", "QueerTVGuideWidgets/QueerTVGuideWidgets.entitlements"] {
            let data = try Data(contentsOf: Repo.iosRoot.appendingPathComponent(path))
            let plist = try XCTUnwrap(PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any])
            XCTAssertEqual(plist["com.apple.security.application-groups"] as? [String], [UpNext.appGroupIdentifier], path)
            XCTAssertEqual(plist.count, 1, "\(path) asks for more than the App Group")
        }
    }
}
