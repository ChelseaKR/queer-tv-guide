import Foundation
import XCTest
@testable import GuideCore

/// The Android app's parity contract with GuideCore (DECISIONS 0018).
///
/// One file, `Tests/Fixtures/parity.golden.json`, holds inputs (the test
/// fixture, edited the way `EpisodeRemindersTests` edits it, in five time
/// zones and at several clocks) and what GuideCore makes of them: the
/// reminders it plans (fire instant, words), the next-episode sentence in
/// the viewer's time zone, the widget's lines, every absence's wording,
/// search hits and filters, and the favorites backup bytes. This test
/// rebuilds the file from GuideCore and fails if it differs from the
/// committed copy; `android/core`'s `ParityGoldenTest` reads the same file
/// and fails if the Kotlin port says anything different. So a change on
/// either side that the other does not make fails one of the two suites.
///
/// To regenerate after a deliberate GuideCore change:
/// `QF_WRITE_PARITY_GOLDEN=1 swift test --filter ParityGoldenTests`, then
/// make the same change in `android/core` until its test passes.
///
/// Wording is pinned in US English, the app's only language
/// (docs/I18N.md). The formatters GuideCore keeps as statics are pointed at
/// en_US and each case's time zone for the duration, and put back after.
/// The reminder's air-date words use the process locale, so the test is
/// skipped where that locale does not write "Sep 20" (it is what US
/// English writes, on a developer Mac and on CI).
final class ParityGoldenTests: XCTestCase {
    static let goldenURL = Repo.iosRoot.appendingPathComponent("GuideCore/Tests/Fixtures/parity.golden.json")

    static let zones = ["UTC", "America/Los_Angeles", "America/New_York", "Asia/Tokyo", "Pacific/Auckland"]
    static let clocks = ["2026-09-14T00:00:00Z", "2026-09-21T03:00:00Z", "2026-09-25T00:00:00Z"]
    static let favorites = ["lwtv:show:101", "lwtv:show:101", "lwtv:show:104", "lwtv:show:102", "lwtv:show:103", "lwtv:show:gone"]

    /// Edits to the fixture's first show's next episode (`airstamp`,
    /// `airdate`, `airtime`; nil is a JSON null), and optionally a second
    /// listed episode on Night Shift Radio, so the plan has two shows to
    /// order.
    struct Variant {
        let name: String
        let airstamp: String?
        let airdate: String?
        let airtime: String?
        var nightShift: (airstamp: String?, airdate: String?, airtime: String?)? = nil
    }

    static let variants: [Variant] = [
        Variant(name: "fixture", airstamp: "2026-09-20T21:00:00-04:00", airdate: "2026-09-20", airtime: "21:00"),
        Variant(name: "placeholder-stamp", airstamp: "2026-09-23T12:00:00+00:00", airdate: "2026-09-23", airtime: nil),
        Variant(name: "empty-airtime", airstamp: "2026-09-23T12:00:00+00:00", airdate: "2026-09-23", airtime: ""),
        Variant(name: "late-utc-broadcast", airstamp: "2026-10-16T02:00:00+00:00", airdate: "2026-10-15", airtime: "22:00"),
        Variant(name: "date-only-no-stamp", airstamp: nil, airdate: "2026-09-20", airtime: "21:00"),
        Variant(name: "no-air-date", airstamp: nil, airdate: nil, airtime: nil),
        Variant(
            name: "two-shows",
            airstamp: "2026-09-20T21:00:00-04:00", airdate: "2026-09-20", airtime: "21:00",
            nightShift: ("2026-09-18T12:00:00+00:00", "2026-09-18", nil)
        ),
        Variant(
            name: "two-shows-undated",
            airstamp: "2026-09-20T21:00:00-04:00", airdate: "2026-09-20", airtime: "21:00",
            nightShift: (nil, nil, nil)
        ),
    ]

    static let searchQueries = [
        "harbor", "HARBOR lights", "lights harbor", "Harbor Lights", "ines", "INÉS", "salt and", "salt & ember",
        "salt ember", "x", "mara quill", "quill mara", "  ", "", "zzz", "example network", "example actor",
        "cartographers", "the", "night-shift", "nightshift", "a",
    ]

    func testTheGoldenFileIsWhatGuideCoreSays() throws {
        let probe = DateFormatter()
        probe.setLocalizedDateFormatFromTemplate("MMMd")
        guard probe.dateFormat == "MMM d" else {
            throw XCTSkip("the process locale writes \(probe.dateFormat ?? "?") for MMMd; the golden file is US English")
        }
        let built = try withPinnedFormatters { try Self.build() }
        let data = try JSONSerialization.data(withJSONObject: built, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
        if ProcessInfo.processInfo.environment["QF_WRITE_PARITY_GOLDEN"] == "1" {
            try (data + Data("\n".utf8)).write(to: Self.goldenURL)
            return
        }
        let stored = try JSONSerialization.jsonObject(with: Data(contentsOf: Self.goldenURL)) as? NSDictionary
        let fresh = try JSONSerialization.jsonObject(with: data) as? NSDictionary
        XCTAssertNotNil(stored)
        XCTAssertEqual(stored, fresh, "GuideCore no longer says what parity.golden.json records. Regenerate it (see this file's header) and port the change to android/core.")
    }

    /// The comparison above can fail: one changed word in a copy of the
    /// golden file is a difference.
    func testTheComparisonCanFail() throws {
        let stored = try XCTUnwrap(try JSONSerialization.jsonObject(with: Data(contentsOf: Self.goldenURL)) as? [String: Any])
        var edited = stored
        var presentation = try XCTUnwrap(edited["presentation"] as? [String: Any])
        presentation["no_watch_links"] = "Something else."
        edited["presentation"] = presentation
        XCTAssertNotEqual(stored as NSDictionary, edited as NSDictionary)
    }

    // MARK: Building the file

    private func withPinnedFormatters<T>(_ body: () throws -> T) rethrows -> T {
        let formatters = [Presentation.dayFormatter, Presentation.dateTimeFormatter, Presentation.instantFormatter, EpisodeReminders.dataDay, UpNextPresentation.shortDay, UpNextPresentation.spokenDay]
        let saved = formatters.map { ($0.locale, $0.timeZone, $0.dateFormat) }
        let savedDefaultZone = NSTimeZone.default
        defer {
            NSTimeZone.default = savedDefaultZone
            for (f, s) in zip(formatters, saved) {
                f.locale = s.0
                f.timeZone = s.1
                f.dateFormat = s.2
            }
        }
        let us = Locale(identifier: "en_US")
        for f in [Presentation.dayFormatter, Presentation.dateTimeFormatter, Presentation.instantFormatter] {
            f.locale = us
        }
        for (f, template) in [(EpisodeReminders.dataDay, "MMMd"), (UpNextPresentation.shortDay, "MMMd"), (UpNextPresentation.spokenDay, "MMMMd")] {
            f.locale = us
            f.setLocalizedDateFormatFromTemplate(template)
        }
        return try body()
    }

    /// The device's time zone, as the app sees it: the zone a reminder's
    /// calendar uses, every "local" formatter, and `TimeZone.current` (which
    /// `Presentation.nextEpisode`'s calendar reads), so the file does not
    /// depend on the zone of the machine that runs the test.
    private static func setDeviceZone(_ zone: TimeZone) {
        NSTimeZone.default = zone
        Presentation.dateTimeFormatter.timeZone = zone
        Presentation.instantFormatter.timeZone = zone
        EpisodeReminders.dataDay.timeZone = zone
    }

    private static func iso(_ date: Date) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        f.timeZone = TimeZone(identifier: "UTC")
        return f.string(from: date)
    }

    private static func date(_ text: String) -> Date {
        ISO8601DateFormatter().date(from: text)!
    }

    private static func json(_ value: Any?) -> Any { value ?? NSNull() }

    static func snapshot(for variant: Variant) throws -> Snapshot {
        var data = try JSONEdit.editShow(try Repo.fixtureData(), index: 0) { show in
            var schedule = show["schedule"] as! [String: Any]
            var episode = schedule["next_episode"] as! [String: Any]
            episode["airstamp"] = json(variant.airstamp)
            episode["airdate"] = json(variant.airdate)
            episode["airtime"] = json(variant.airtime)
            schedule["next_episode"] = episode
            show["schedule"] = schedule
        }
        if let night = variant.nightShift {
            data = try JSONEdit.editShow(data, index: 3) { show in
                var schedule = show["schedule"] as! [String: Any]
                schedule["next_episode"] = [
                    "tvmaze_id": 900104, "season": 2, "number": 1, "name": "Static",
                    "airdate": json(night.airdate), "airtime": json(night.airtime), "airstamp": json(night.airstamp),
                    "runtime": 30, "url": "https://www.tvmaze.com/episodes/900104/night-shift-radio-2x01-static",
                ] as [String: Any]
                show["schedule"] = schedule
            }
        }
        return try SnapshotDecoder().decode(data)
    }

    static func build() throws -> [String: Any] {
        let base = try Repo.fixture()
        var root: [String: Any] = [
            "format": "queer-frame-parity",
            "version": 1,
            "fixture": "ios/GuideCore/Tests/Fixtures/snapshot.fixture.json",
            "locale": "en_US",
            "zones": zones,
            "clocks": clocks,
            "favorites": favorites,
        ]
        root["variants"] = try variants.map { try variantCase($0) }
        root["presentation"] = presentation(base)
        root["freshness"] = freshness(base)
        root["search"] = search(base)
        root["backup"] = try backup()
        return root
    }

    private static func variantCase(_ variant: Variant) throws -> [String: Any] {
        let snapshot = try snapshot(for: variant)
        var out: [String: Any] = [
            "name": variant.name,
            "edit": ["airstamp": json(variant.airstamp), "airdate": json(variant.airdate), "airtime": json(variant.airtime)],
        ]
        if let night = variant.nightShift {
            out["night_shift_edit"] = ["airstamp": json(night.airstamp), "airdate": json(night.airdate), "airtime": json(night.airtime)]
        }
        var byZone: [String: Any] = [:]
        for zoneID in zones {
            let zone = TimeZone(identifier: zoneID)!
            setDeviceZone(zone)
            var calendar = Calendar(identifier: .gregorian)
            calendar.timeZone = zone
            var byClock: [String: Any] = [:]
            for clock in clocks {
                let now = date(clock)
                let plan = EpisodeReminders.plan(favoriteShowIDs: favorites, snapshot: snapshot, now: now, calendar: calendar)
                byClock[clock] = [
                    "reminders": plan.map { ["identifier": $0.identifier, "show_id": $0.showID, "fire_at": iso($0.fireDate), "title": $0.title, "body": $0.body] },
                    "next_episode": Dictionary(uniqueKeysWithValues: snapshot.shows.map { ($0.id, Presentation.nextEpisode($0.schedule, today: now)) }),
                ]
            }
            byZone[zoneID] = byClock
        }
        out["by_zone"] = byZone

        let upNext = UpNext(favoriteShowIDs: favorites, snapshot: snapshot)
        var widget: [String: Any] = [
            "missing_show_count": upNext.missingShowCount,
            "items": upNext.items.map { ["show_id": $0.showID, "title": $0.title, "status": $0.status.rawValue, "season": json($0.season), "number": json($0.number), "airdate": json($0.airdate)] },
        ]
        var byClock: [String: Any] = [:]
        for clock in clocks {
            let today = date(clock)
            let ordered = upNext.ordered(today: today)
            byClock[clock] = [
                "ordered": ordered.map(\.showID),
                "lines": ordered.map { UpNextPresentation.line($0, today: today) },
                "spoken": ordered.map { UpNextPresentation.spoken($0, today: today) },
            ]
        }
        widget["by_clock"] = byClock
        out["widget"] = widget
        return out
    }

    private static func presentation(_ s: Snapshot) -> [String: Any] {
        setDeviceZone(TimeZone(identifier: "UTC")!)
        var shows: [String: Any] = [:]
        for show in s.shows {
            let cast = s.characters(inShow: show.id)
            let deaths = Presentation.showDeaths(cast: cast, show: show)
            shows[show.id] = [
                "years": Presentation.years(show.years),
                "seasons": Presentation.seasons(show.seasons),
                "worth_it": Presentation.worthIt(show.ratings.worthIt),
                "quality": Presentation.ratingValue(show.ratings.quality),
                "realness": Presentation.ratingValue(show.ratings.realness),
                "screentime": Presentation.ratingValue(show.ratings.screentime),
                "rating_quality": Presentation.rating(show.ratings.quality, label: "Quality"),
                "score": Presentation.score(show.ratings.score),
                "deaths": ["headline": deaths.headline, "lines": deaths.lines, "notes": deaths.notes, "spoken": deaths.spoken],
                "deaths_summary": Presentation.deathsSummary(cast: cast),
                "tropes_shown": Presentation.terms(Presentation.withoutSpoilers(show.tropes, Presentation.deathSpoilerTropeSlugs), empty: Presentation.noTropes),
                "triggers": Presentation.terms(show.triggers, empty: Presentation.noTriggers),
                "watch_links": show.watchLinks.map { ["label": Presentation.watchLinkLabel($0, networks: show.networks), "display_host": Presentation.displayHost($0.host)] },
                "tvmaze_credit": json(Attribution.tvmazeCredit(for: show.schedule, in: s).map { ["source_title": $0.source.title, "source_url": $0.source.url.absoluteString, "license_title": $0.license.title, "license_url": $0.license.url.absoluteString, "spoken": $0.spoken] }),
                "lezwatch_link_label": Attribution.lezWatchLinkLabel(for: show.title),
                "share_url": Sharing.cleanURL(show.sourceURL).absoluteString,
                "death_coverage": ["has_characters": SearchIndex(snapshot: s).deathCoverage(show).hasCharacters, "any_recorded_death": SearchIndex(snapshot: s).deathCoverage(show).anyRecordedDeath],
            ]
        }
        var characters: [String: Any] = [:]
        for c in s.characters {
            characters[c.id] = [
                "death": Presentation.death(c.death, name: c.name),
                "death_short": Presentation.deathShort(c.death),
                "tropes_shown": Presentation.withoutSpoilers(c.cliches, Presentation.deathSpoilerClicheSlugs).map(\.name),
            ]
        }
        let yearCases: [(start: Int?, end: Int?, onAir: String)] = [
            (nil, nil, "unknown"), (2001, nil, "yes"), (2001, nil, "no"), (2001, nil, "unknown"), (1995, 2001, "no"), (nil, 2001, "no"), (nil, nil, "no"),
        ]
        let years: [[String: Any]] = yearCases.map { c in
            let object: [String: Any] = ["start": json(c.start), "end": json(c.end), "on_air": c.onAir]
            let y = try! JSONDecoder().decode(Years.self, from: JSONSerialization.data(withJSONObject: object))
            return ["start": json(c.start), "end": json(c.end), "on_air": c.onAir, "text": Presentation.years(y)]
        }
        let imports: [[Int]] = [[0, 0, 0, 0], [1, 0, 0, 0], [3, 1, 0, 0], [0, 2, 1, 1], [2, 0, 3, 2], [0, 1, 0, 0]]
        var out: [String: Any] = [:]
        out["shows"] = shows
        out["characters"] = characters
        out["years"] = years
        var seasons: [[String: Any]] = [-1, 0, 1, 2, 12].map { n -> [String: Any] in ["n": n, "text": Presentation.seasons(n)] }
        seasons.append(["n": NSNull(), "text": Presentation.seasons(nil)])
        out["seasons"] = seasons
        let ageSeconds: [Int] = [-5, 0, 3599, 3600, 7199, 7200, 86400, 172799, 172800, 172801, 259200, 864000]
        out["ages"] = ageSeconds.map { n -> [String: Any] in ["seconds": n, "text": Presentation.age(TimeInterval(n))] }
        let spanSeconds: [Int] = [3600, 6 * 3600, 24 * 3600, 3 * 24 * 3600, 25 * 3600, 1800]
        out["spans"] = spanSeconds.map { n -> [String: Any] in ["seconds": n, "text": Presentation.span(TimeInterval(n))] }
        out["return_refresh_rule"] = Presentation.returnRefreshRule
        out["import_summaries"] = imports.map { i -> [String: Any] in
            ["added": i[0], "already_saved": i[1], "not_in_snapshot": i[2], "unreadable": i[3],
             "text": Presentation.importSummary(added: i[0], alreadySaved: i[1], notInSnapshot: i[2], unreadable: i[3])]
        }
        out["no_watch_links"] = Presentation.noWatchLinks
        out["no_characters"] = Presentation.noCharacters
        out["non_endorsement"] = Attribution.nonEndorsement
        let general = Attribution.tvmazeCredit(in: s).map { c -> [String: Any] in
            ["source_title": c.source.title, "source_url": c.source.url.absoluteString, "license_title": c.license.title, "license_url": c.license.url.absoluteString]
        }
        out["tvmaze_general_credit"] = json(general)
        let more: [[Int]] = [[0, 0], [2, 0], [0, 1], [2, 1]]
        out["widget_more"] = more.map { m -> [String: Any] in ["count": m[0], "missing": m[1], "text": json(UpNextPresentation.more(m[0], missing: m[1]))] }
        return out
    }

    private static func freshness(_ s: Snapshot) -> [[String: Any]] {
        let offsets = [-7200, -3601, -3600, -1800, 0, 3599, 3600, 86400, 172800, 172801, 259200, 259201, 864000]
        var out: [[String: Any]] = []
        for zoneID in zones {
            setDeviceZone(TimeZone(identifier: zoneID)!)
            for offset in offsets {
                let now = s.generatedAt.addingTimeInterval(TimeInterval(offset))
                let freshness = DataFreshness.assess(generatedAt: s.generatedAt, now: now)
                let warning = Presentation.freshnessWarning(generatedAt: s.generatedAt, freshness: freshness)
                var gate = ForegroundRefreshGate()
                let first = gate.shouldRefresh(generatedAt: s.generatedAt, now: now)
                let again = gate.shouldRefresh(generatedAt: s.generatedAt, now: now.addingTimeInterval(3600))
                let later = gate.shouldRefresh(generatedAt: s.generatedAt, now: now.addingTimeInterval(6 * 3600))
                let state: String
                switch freshness {
                case .current: state = "current"
                case .stale: state = "stale"
                case .unknown: state = "unknown"
                }
                out.append([
                    "zone": zoneID,
                    "offset_seconds": offset,
                    "state": state,
                    "data_as_of": Presentation.dataAsOf(s.generatedAt, freshness: freshness),
                    "warning": json(warning.map { ["title": $0.title, "detail": $0.detail, "spoken": $0.spoken] }),
                    "widget_age": UpNextPresentation.dataAge(s.generatedAt, now: now),
                    "return_refresh": [first, again, later],
                ])
            }
        }
        return out
    }

    private static func search(_ s: Snapshot) -> [String: Any] {
        let index = SearchIndex(snapshot: s)
        let queries: [[String: Any]] = searchQueries.map { q in
            let r = index.search(q)
            let filtered = index.search(q, filters: SearchIndex.Filters(noRecordedDeaths: true))
            let capped = index.search(q, limit: 2)
            return [
                "query": q,
                "hits": r.hits.map(\.id), "total": r.totalCount,
                "no_recorded_deaths_hits": filtered.hits.map(\.id),
                "limit_2_hits": capped.hits.map(\.id), "limit_2_total": capped.totalCount,
            ]
        }
        let filterSets: [(String, SearchIndex.Filters)] = [
            ("none", SearchIndex.Filters()),
            ("no_recorded_deaths", SearchIndex.Filters(noRecordedDeaths: true)),
            ("worth_it_yes", SearchIndex.Filters(worthIt: [.yes])),
            ("worth_it_yes_meh", SearchIndex.Filters(worthIt: [.yes, .meh])),
            ("worth_it_tbd", SearchIndex.Filters(worthIt: [.tbd])),
            ("has_watch_link", SearchIndex.Filters(hasWatchLink: true)),
            ("host_example_com", SearchIndex.Filters(watchHosts: ["example.com"])),
            ("host_store_example_org", SearchIndex.Filters(watchHosts: ["store.example.org"])),
            ("trope_slow_burn", SearchIndex.Filters(tropes: ["slow-burn"])),
            ("hide_violence", SearchIndex.Filters(hiddenTriggerWarnings: ["violence"])),
            ("all", SearchIndex.Filters(worthIt: [.yes, .no], noRecordedDeaths: true, hasWatchLink: true, watchHosts: ["example.com"], tropes: ["slow-burn"], hiddenTriggerWarnings: ["violence"])),
        ]
        let browse: [[String: Any]] = filterSets.map { name, filters in
            [
                "name": name,
                "active_count": filters.activeCount,
                "shows": index.browse(filters: filters).map(\.id),
                "harbor_hits": index.search("harbor", filters: filters).hits.map(\.id),
                "example_hits": index.search("example", filters: filters).hits.map(\.id),
            ]
        }
        let options = index.filterOptions
        return [
            "queries": queries,
            "browse": browse,
            "filter_options": [
                "watch_hosts": options.watchHosts.map { ["key": $0.key, "show_count": $0.showCount] },
                "tropes": options.tropes.map { ["slug": $0.slug, "name": $0.name, "show_count": $0.showCount] },
                "trigger_warnings": options.triggerWarnings.map { ["slug": $0.slug, "name": $0.name, "show_count": $0.showCount] },
            ],
            "folds": ["Grey’s Anatomy", "Xena: Warrior Princess", "Salt & Ember", "INÉS  Varga", "Ｆｕｌｌ ｗｉｄｔｈ", "rock'n'roll", "L.A. Law", "Ōoku", "  spaced   out  "].map { ["text": $0, "folded": SearchIndex.fold($0)] },
            "watch_host_keys": ["www.Netflix.com", "netflix.com", "WWW.example.org", "store.example.org", "www"].map { ["host": $0, "key": SearchIndex.WatchHost.key(for: $0)] },
        ]
    }

    private static func backup() throws -> [String: Any] {
        let entries = [
            FavoritesStore.Entry(kind: .show, id: "lwtv:show:101", addedAt: date("2026-09-18T09:44:42Z")),
            FavoritesStore.Entry(kind: .character, id: "lwtv:character:203", addedAt: date("2026-09-19T10:00:00Z")),
        ]
        let exported = try FavoritesBackup.export(entries)
        let empty = try FavoritesBackup.export([])
        return [
            "entries": entries.map { ["kind": $0.kind.rawValue, "id": $0.id, "added_at": iso($0.addedAt)] },
            "export": String(decoding: exported, as: UTF8.self),
            "export_empty": String(decoding: empty, as: UTF8.self),
            "well_formed": ["lwtv:show:1", "lwtv:show:", "lwtv:show:12a", "lwtv:character:1", "lwtv:show:1234567890123", "lwtv:show:123456789012", "show:1", "lwtv:show:١"].map {
                ["id": $0, "as_show": FavoritesBackup.isWellFormed($0, kind: .show), "as_character": FavoritesBackup.isWellFormed($0, kind: .character)]
            },
        ]
    }
}
