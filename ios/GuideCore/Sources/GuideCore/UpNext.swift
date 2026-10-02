import Foundation

/// What the home-screen widget shows: the next episode of each favorite show.
///
/// The app writes one small file (`fileName`) into the App Group container it
/// shares with the widget, and the widget reads only that file. The widget
/// makes no network request and never opens the snapshot itself.
///
/// Spoiler safety is structural. An item carries a show's title, its
/// schedule status, and an episode's season, number and air date. It has no
/// field that could hold death data, and no episode name either, because a
/// title such as "Goodbye, Lexa" can give an ending away on a screen anyone
/// can glance at. `UpNextTests` fails if a field is added.
public struct UpNext: Codable, Equatable, Sendable {
    /// Bumped whenever the file's shape changes. A widget that reads a file of
    /// another version shows "open the app" rather than guessing.
    public static let currentFormatVersion = 1
    public static let fileName = "up-next.v1.json"
    /// Shared by the app and the widget extension. Both targets' entitlements
    /// name it; `SourceTreeGuardTests` checks they agree with this constant.
    public static let appGroupIdentifier = "group.com.chelseakr.queertvguide"
    /// The widget's `kind`, which the app names when it asks WidgetKit to
    /// reload.
    public static let widgetKind = "UpNextWidget"

    public struct Item: Codable, Equatable, Sendable, Identifiable {
        /// The same four facts the Favorites screen states, kept apart: an
        /// unmatched show is never "nothing upcoming".
        public enum Status: String, Codable, Sendable {
            /// An episode is listed with an air date.
            case dated
            /// An episode is listed, with no air date recorded.
            case undated
            /// TVmaze matched the show and lists no upcoming episode.
            case noneListed
            /// The show was never matched to TVmaze: schedule unknown.
            case unknown
        }

        public let showID: String
        public let title: String
        public let status: Status
        public let season: Int?
        public let number: Int?
        /// `YYYY-MM-DD`, exactly as TVmaze records it.
        public let airdate: String?

        public var id: String { showID }

        public init(showID: String, title: String, status: Status, season: Int? = nil, number: Int? = nil, airdate: String? = nil) {
            self.showID = showID
            self.title = title
            self.status = status
            self.season = season
            self.number = number
            self.airdate = airdate
        }

        /// The air date as a UTC calendar day, as `Episode.airdateDay`.
        public var airdateDay: Date? {
            guard status == .dated, let airdate else { return nil }
            return ISO8601DayFormatter.date(from: airdate)
        }
    }

    public let formatVersion: Int
    /// The snapshot's `generated_at`: how old the data behind every line is.
    public let snapshotGeneratedAt: Date
    /// Favorite shows, in the order they were added (newest first).
    public let items: [Item]
    /// Favorite shows the snapshot no longer lists. Counted, never dropped
    /// silently.
    public let missingShowCount: Int

    public init(formatVersion: Int = UpNext.currentFormatVersion, snapshotGeneratedAt: Date, items: [Item], missingShowCount: Int) {
        self.formatVersion = formatVersion
        self.snapshotGeneratedAt = snapshotGeneratedAt
        self.items = items
        self.missingShowCount = missingShowCount
    }

    /// Builds the file's contents from the favorite show ids (newest first)
    /// and the snapshot the app has loaded.
    public init(favoriteShowIDs: [Show.ID], snapshot: Snapshot) {
        var items: [Item] = []
        var missing = 0
        var seen: Set<Show.ID> = []
        for id in favoriteShowIDs where seen.insert(id).inserted {
            guard let show = snapshot.show(id: id) else {
                missing += 1
                continue
            }
            items.append(Self.item(for: show))
        }
        self.init(snapshotGeneratedAt: snapshot.generatedAt, items: items, missingShowCount: missing)
    }

    static func item(for show: Show) -> Item {
        let schedule = show.schedule
        guard schedule.scheduleKnown else {
            return Item(showID: show.id, title: show.title, status: .unknown)
        }
        guard let episode = schedule.nextEpisode else {
            return Item(showID: show.id, title: show.title, status: .noneListed)
        }
        let dated = episode.airdateDay != nil
        return Item(
            showID: show.id,
            title: show.title,
            status: dated ? .dated : .undated,
            season: episode.season,
            number: episode.number,
            airdate: dated ? episode.airdate : nil
        )
    }

    /// The items in the order the widget lists them on `today`: the soonest
    /// air date first, then episodes whose listed date has passed (stale
    /// data), then undated episodes, then shows with nothing listed, then
    /// shows whose schedule is unknown. Ties keep the favorites order.
    public func ordered(today: Date) -> [Item] {
        func rank(_ item: Item) -> Int {
            switch item.status {
            case .dated:
                guard let day = item.airdateDay else { return 2 }
                return Presentation.isPast(day, today: today) ? 1 : 0
            case .undated: return 2
            case .noneListed: return 3
            case .unknown: return 4
            }
        }
        return items.enumerated().sorted { a, b in
            let ra = rank(a.element), rb = rank(b.element)
            if ra != rb { return ra < rb }
            if ra <= 1, let da = a.element.airdateDay, let db = b.element.airdateDay, da != db {
                return da < db
            }
            return a.offset < b.offset
        }.map(\.element)
    }
}

/// Reads and writes `UpNext` in a directory: the App Group container in the
/// app, a temporary directory in tests.
public struct UpNextStore: Sendable {
    public let directory: URL

    public init(directory: URL) {
        self.directory = directory
    }

    public var fileURL: URL { directory.appendingPathComponent(UpNext.fileName) }

    public static func encoder() -> JSONEncoder {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        e.outputFormatting = [.sortedKeys]
        return e
    }

    /// `nil` when there is no file, it does not decode, or it is another
    /// format version: the widget then asks for the app to be opened.
    public func read() -> UpNext? {
        guard let data = try? Data(contentsOf: fileURL) else { return nil }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        guard let upNext = try? decoder.decode(UpNext.self, from: data),
              upNext.formatVersion == UpNext.currentFormatVersion else { return nil }
        return upNext
    }

    /// Writes `upNext` atomically when it differs from what is stored.
    /// Returns whether it wrote, so the app asks WidgetKit to reload only
    /// when something changed.
    @discardableResult
    public func write(_ upNext: UpNext) throws -> Bool {
        if read() == upNext { return false }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try Self.encoder().encode(upNext).write(to: fileURL, options: [.atomic])
        return true
    }
}

/// The widget's text for every state, kept here so tests can hold each
/// absence to the same rules as the app: stated, never blank, and an unknown
/// schedule never reads as "nothing upcoming".
public enum UpNextPresentation {
    /// The data cards' 48-hour freshness promise
    /// (docs/data/lezwatch.md, docs/data/tvmaze.md). Past it, the widget
    /// says its data may be out of date.
    public static let staleAfter: TimeInterval = 48 * 60 * 60

    public static let title = "Up next"
    public static let noFavoriteShows = "Star a show to see its next episode here."
    public static let notLoaded = "Open the app once to show your favorite shows here."
    /// TVmaze's credit, by name, wherever the widget shows its schedule data.
    /// The link back lives in the app, which a tap on the widget opens.
    public static let tvmazeCredit = "Schedules: TVmaze"

    /// The line under a show's title, e.g. "S23E1 · Oct 15".
    public static func line(_ item: UpNext.Item, today: Date) -> String {
        switch item.status {
        case .unknown:
            return "Schedule unknown"
        case .noneListed:
            return "No upcoming episode listed"
        case .undated:
            return episodeCode(item).map { "\($0) · air date not recorded" } ?? "Next episode · air date not recorded"
        case .dated:
            guard let day = item.airdateDay else {
                return episodeCode(item).map { "\($0) · air date not recorded" } ?? "Next episode · air date not recorded"
            }
            let date = shortDay.string(from: day)
            let head = episodeCode(item) ?? "Next episode"
            if Presentation.isPast(day, today: today) {
                return "\(head) · \(date), passed"
            }
            return "\(head) · \(date)"
        }
    }

    /// What VoiceOver reads for a row: whole words, no "S23E1".
    public static func spoken(_ item: UpNext.Item, today: Date) -> String {
        var episode = "Next episode"
        if let s = item.season, let n = item.number {
            episode = "Season \(s), episode \(n)"
        }
        switch item.status {
        case .unknown:
            return "\(item.title). Schedule unknown."
        case .noneListed:
            return "\(item.title). No upcoming episode listed."
        case .undated:
            return "\(item.title). \(episode), air date not recorded."
        case .dated:
            guard let day = item.airdateDay else {
                return "\(item.title). \(episode), air date not recorded."
            }
            let date = spokenDay.string(from: day)
            if Presentation.isPast(day, today: today) {
                return "\(item.title). \(episode) was listed for \(date), which has passed. This data may be out of date."
            }
            return "\(item.title). \(episode), \(date)."
        }
    }

    /// "S23E1", or `nil` when the season or number is not recorded.
    static func episodeCode(_ item: UpNext.Item) -> String? {
        guard let s = item.season, let n = item.number else { return nil }
        return "S\(s)E\(n)"
    }

    public enum Freshness: Equatable, Sendable {
        case current
        case stale
        /// Dated more than an hour after the device's clock: its age cannot
        /// be known, so it is never shown as current.
        case unknownAge
    }

    public static func freshness(of generatedAt: Date, now: Date) -> Freshness {
        let age = now.timeIntervalSince(generatedAt)
        if age < -3600 { return .unknownAge }
        return age > staleAfter ? .stale : .current
    }

    /// The widget's footer: always the data's date, and a plain warning when
    /// it is past the freshness promise or its age cannot be known.
    public static func dataAge(_ generatedAt: Date, now: Date) -> String {
        let date = shortDay.string(from: generatedAt)
        switch freshness(of: generatedAt, now: now) {
        case .current: return "Data as of \(date)"
        case .stale: return "Out of date: data as of \(date)"
        case .unknownAge: return "Data age unknown"
        }
    }

    /// Under the rows: favorites with no room ("+2 more"), and favorites the
    /// data no longer lists ("1 not in this data"), so neither vanishes
    /// without a word.
    public static func more(_ count: Int, missing: Int = 0) -> String? {
        var parts: [String] = []
        if count > 0 { parts.append("+\(count) more") }
        if missing > 0 { parts.append("\(missing) not in this data") }
        return parts.isEmpty ? nil : parts.joined(separator: ", ")
    }

    /// "Oct 15", UTC, as the app reads TVmaze's air dates.
    public static let shortDay: DateFormatter = {
        let f = DateFormatter()
        f.setLocalizedDateFormatFromTemplate("MMMd")
        f.timeZone = TimeZone(identifier: "UTC")
        return f
    }()

    /// "October 15", for VoiceOver.
    public static let spokenDay: DateFormatter = {
        let f = DateFormatter()
        f.setLocalizedDateFormatFromTemplate("MMMMd")
        f.timeZone = TimeZone(identifier: "UTC")
        return f
    }()
}
