import Foundation

/// "Has anyone died so far?" (DECISIONS 0043): the recorded deaths up to where
/// the viewer is in a show, from the placements the pipeline matched by air date
/// (DECISIONS 0041). Pure: the same show, cast and position always give the
/// same words.
///
/// The rules, from growth/qf-progress-and-stats-2026-11-06.md:
/// - Only deaths at or before the viewer's episode are in `soFar`. Deaths after
///   it are in `later`, which the app keeps behind a second reveal.
/// - Each precision says only what it knows: one episode, "episode 7 or 8"
///   (never one of the two), a special by its air date, a season only, or "we
///   can't place it", said plainly. A death that might be on either side of the
///   viewer is never counted as either: it is in `uncertain`, without a name.
/// - Never "0" or "none" for a death that cannot be placed.
/// - A recorded death means the character died at some point. LezWatch.TV
///   records no date for a return, so nothing here says "still dead".
/// - `Show.episodeCounts` exists only for shows with a recorded death, so it is
///   read here, behind the reveal, and never to shape the picker
///   (`seasonRange`, `episodeRange`).
public enum SoFar {
    /// Where the viewer is: they have watched up to and including this episode.
    public struct Position: Equatable, Hashable, Codable, Sendable {
        public let season: Int
        public let episode: Int
        public init(season: Int, episode: Int) {
            self.season = season
            self.episode = episode
        }
        public static let start = Position(season: 1, episode: 1)

        /// "season 3, episode 4"
        public var spoken: String { "season \(season), episode \(episode)" }
    }

    /// One recorded death date in one show: who, the year LezWatch.TV
    /// records, and where it falls.
    public struct Event: Equatable, Sendable {
        public let name: String
        public let year: Int?
        public let placement: DeathPlacement
        public init(name: String, year: Int?, placement: DeathPlacement) {
            self.name = name
            self.year = year
            self.placement = placement
        }
    }

    public struct Answer: Equatable, Sendable {
        /// The so-far reveal: a verdict for the deaths up to the viewer.
        public let headline: String
        /// One named line per death at or before the viewer's episode.
        public let soFar: [String]
        /// Deaths we cannot put on either side of the viewer, unnamed.
        public let uncertain: [String]
        /// Anything else the reader should know (a position past the list).
        public let notes: [String]
        /// The second reveal's verdict and its named lines.
        public let laterHeadline: String
        public let later: [String]
        public let footer: String

        /// What VoiceOver reads for the so-far reveal, as one stop.
        public var spoken: String { ([headline] + soFar + uncertain + notes).joined(separator: " ") }
        /// What VoiceOver reads for the later reveal, as one stop.
        public var laterSpoken: String { ([laterHeadline] + later).joined(separator: " ") }
    }

    public static let footer = "Deaths as recorded by LezWatch.TV; episodes matched by air date using TVmaze. LezWatch.TV may not list every character. A recorded death means a character died at some point, not that they stay dead."

    /// The snapshot places deaths in episodes at all. Files built before
    /// DECISIONS 0041 do not, and the app does not offer the question for them.
    public static func isAvailable(in snapshot: Snapshot) -> Bool {
        snapshot.coverage.placements != nil
    }

    /// Seasons the picker offers: LezWatch.TV's season count, which the show
    /// screen already shows, plus one for a show still on air (LezWatch.TV can
    /// lag a new season). With no count, 1 to 99. Never the episode list's
    /// count: that list exists only for shows with a death.
    public static func seasonRange(for show: Show) -> ClosedRange<Int> {
        guard let seasons = show.seasons, seasons > 0 else { return 1...99 }
        return 1...(show.years.onAir == .yes ? seasons + 1 : seasons)
    }

    /// Episodes the picker offers, the same for every show and season (see
    /// `seasonRange` for why).
    public static let episodeRange: ClosedRange<Int> = 1...999

    /// A stored position brought inside the picker's ranges.
    public static func clamped(_ position: Position, for show: Show) -> Position {
        let seasons = seasonRange(for: show)
        return Position(
            season: min(max(position.season, seasons.lowerBound), seasons.upperBound),
            episode: min(max(position.episode, episodeRange.lowerBound), episodeRange.upperBound)
        )
    }

    /// Every recorded death date that counts for `show` (DECISIONS 0030, as
    /// the pipeline placed it), one event per date, so a character who died
    /// twice has two. A crossover date placed in another show is left out. A
    /// date without placements (not computed for it) is unplaced when the
    /// character's years in the show include its year, as under 0030.
    public static func events(cast: [Character], show: Show) -> [Event] {
        var out: [Event] = []
        for character in cast {
            for date in character.death.dates {
                if let placements = date.placements {
                    for placement in placements where placement.showID == show.id && placement.precision != .otherShow {
                        out.append(Event(name: character.name, year: date.year, placement: placement))
                    }
                } else if let year = date.year,
                          character.shows.contains(where: { $0.showID == show.id && $0.years.contains(String(year)) }) {
                    let unplaced = DeathPlacement(showID: show.id, precision: .unplaced, reason: "not_computed", season: nil, episodes: nil, airdate: nil)
                    out.append(Event(name: character.name, year: year, placement: unplaced))
                }
            }
        }
        return out
    }

    public static func answer(show: Show, cast: [Character], at position: Position) -> Answer {
        answer(events: events(cast: cast, show: show), castIsEmpty: cast.isEmpty, episodeCounts: show.episodeCounts, at: position)
    }

    private enum Side {
        case soFar(String)
        case later(String)
        /// Unnamed line for the so-far reveal, grouped by `key`; named line
        /// for the later reveal.
        case uncertain(key: String, line: (Int) -> String, named: String)
    }

    /// The core rule, on events alone, so every tier is testable without a
    /// snapshot.
    public static func answer(events: [Event], castIsEmpty: Bool = false, episodeCounts: [SeasonEpisodeCount]?, at position: Position) -> Answer {
        let through = position.spoken
        let counts = Dictionary((episodeCounts ?? []).map { ($0.season, $0.episodes) }, uniquingKeysWith: { a, _ in a })

        var soFar: [String] = []
        var later: [String] = []
        var maybeNamed: [String] = []
        var uncertainOrder: [String] = []
        var uncertainCount: [String: Int] = [:]
        var uncertainLine: [String: (Int) -> String] = [:]

        for event in events {
            switch side(of: event, at: position, counts: counts) {
            case .soFar(let line): soFar.append(line)
            case .later(let line): later.append(line)
            case let .uncertain(key, line, named):
                if uncertainCount[key] == nil {
                    uncertainOrder.append(key)
                    uncertainLine[key] = line
                }
                uncertainCount[key, default: 0] += 1
                maybeNamed.append(named)
            }
        }
        let uncertain = uncertainOrder.map { uncertainLine[$0]!(uncertainCount[$0]!) }

        var notes: [String] = []
        if let episodeCounts, !episodeCounts.isEmpty {
            if let inSeason = counts[position.season], position.episode > inSeason {
                notes.append("TVmaze lists \(inSeason) \(inSeason == 1 ? "episode" : "episodes") in season \(position.season), so this counts all of it.")
            } else if counts[position.season] == nil, let last = episodeCounts.map(\.season).max(), position.season > last {
                notes.append("TVmaze lists episodes up to season \(last), so this counts every listed episode.")
            }
        }

        let headline: String
        if castIsEmpty {
            headline = "Not recorded. LezWatch.TV lists no characters for this show, so there is nothing to check."
        } else if !soFar.isEmpty {
            headline = "Yes. \(deaths(soFar.count)) through \(through)."
        } else if uncertain.isEmpty {
            headline = "Not recorded through \(through). LezWatch.TV records no death of a listed character up to here."
        } else {
            headline = "Can't say for sure through \(through). A recorded death can't be placed before or after where you are."
        }

        let laterHeadline: String
        let laterLines: [String]
        if !later.isEmpty {
            laterHeadline = "After \(through): \(deaths(later.count)) placed later."
        } else if maybeNamed.isEmpty {
            laterHeadline = "Not recorded after \(through). LezWatch.TV records no later death of a listed character."
        } else {
            laterHeadline = "Not recorded as placed after \(through)."
        }
        if maybeNamed.isEmpty {
            laterLines = later
        } else {
            laterLines = later + ["May be before or after where you are:"] + maybeNamed
        }

        return Answer(headline: headline, soFar: soFar, uncertain: uncertain, notes: notes, laterHeadline: laterHeadline, later: laterLines, footer: footer)
    }

    private static func deaths(_ n: Int) -> String {
        n == 1 ? "1 recorded death" : "\(n) recorded deaths"
    }

    /// Which side of the viewer a death is on, with the words for it.
    private static func side(of event: Event, at position: Position, counts: [Int: Int]) -> Side {
        let p = event.placement
        let name = event.name
        // The viewer has watched every listed episode of `season`.
        func finished(_ season: Int) -> Bool {
            season < position.season || (season == position.season && counts[season].map { position.episode >= $0 } == true)
        }

        switch p.precision {
        case .episode:
            guard let season = p.season, let number = p.episodes?.first else { return unplaced(event) }
            let dayOff = p.reason == "one_day_off" ? " (matched to an episode a day from the recorded date)" : ""
            let line = "\(name): season \(season), episode \(number)\(dayOff)."
            return (season, number) <= (position.season, position.episode) ? .soFar(line) : .later(line)

        case .episodePair:
            guard let season = p.season, let first = p.episodes?.min(), let second = p.episodes?.max(), first != second else { return unplaced(event) }
            let line = "\(name): season \(season), episode \(first) or \(second) (both aired the same day)."
            if (season, second) <= (position.season, position.episode) { return .soFar(line) }
            if (season, first) > (position.season, position.episode) { return .later(line) }
            // The viewer is on the first of the two: never pick one.
            return .uncertain(
                key: "pair:\(season):\(first)",
                line: { n in n == 1
                    ? "A recorded death in this episode or the next (episodes \(first) and \(second) aired the same day)."
                    : "\(n) recorded deaths in this episode or the next (episodes \(first) and \(second) aired the same day)." },
                named: line
            )

        case .special:
            let aired = p.airdate.map(spokenDate) ?? "on a date we don't have"
            let line = "\(name): a special that aired \(aired)."
            guard let season = p.season else {
                return .uncertain(
                    key: "special:\(p.airdate ?? "")",
                    line: { n in "\(n == 1 ? "A recorded death" : "\(n) recorded deaths") in a special that aired \(aired), which we can't place before or after where you are." },
                    named: line
                )
            }
            if finished(season) { return .soFar(line) }
            if season > position.season { return .later(line) }
            return .uncertain(
                key: "special:\(season):\(p.airdate ?? "")",
                line: { n in "\(n == 1 ? "A recorded death" : "\(n) recorded deaths") in a special that aired \(aired), during season \(season). It may be before or after episode \(position.episode)." },
                named: line
            )

        case .season:
            guard let season = p.season else { return unplaced(event) }
            let line = "\(name): season \(season); we can't place the episode."
            if finished(season) { return .soFar(line) }
            if season > position.season { return .later(line) }
            let why = p.reason == "season_drop" ? " (the season was released all at once)" : ""
            return .uncertain(
                key: "season:\(season)",
                line: { n in n == 1
                    ? "Season \(season) has a recorded death we can't place in an episode\(why). It may be before or after episode \(position.episode)."
                    : "Season \(season) has \(n) recorded deaths we can't place in an episode\(why). They may be before or after episode \(position.episode)." },
                named: line
            )

        case .unplaced, .otherShow, .unrecognized:
            return unplaced(event)
        }
    }

    private static func unplaced(_ event: Event) -> Side {
        let named = "\(event.name): we can't place this death in an episode."
        switch event.placement.reason {
        case "no_tvmaze_join", "episodes_unavailable", "no_dated_episodes":
            return .uncertain(
                key: "no-list",
                line: { _ in "We don't have this show's episode list, so we can only answer for the whole show, in the reveal above." },
                named: named
            )
        default:
            let year = event.year.map(String.init)
            return .uncertain(
                key: "year:\(year ?? "")",
                line: { n in
                    let what = n == 1 ? "a death" : "\(n) deaths"
                    let when = year.map { " in \($0)" } ?? ""
                    return "LezWatch.TV records \(what)\(when) that we can't match to an episode, so we can't say whether \(n == 1 ? "it's" : "they're") before or after where you are."
                },
                named: named
            )
        }
    }

    /// "November 12, 2017" from "2017-11-12"; the raw string if it does not
    /// parse.
    static func spokenDate(_ iso: String) -> String {
        guard let date = ISO8601DayFormatter.date(from: iso) else { return iso }
        return spokenDateFormatter.string(from: date)
    }

    private static let spokenDateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "MMMM d, yyyy"
        return f
    }()
}

/// Where the viewer is in each show, kept on this device only (data posture,
/// DECISIONS 0002): never sent, never synced, not in the favorites backup.
public final class WatchPositionStore: @unchecked Sendable {
    static let keyPrefix = "soFar.position."
    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public func position(for showID: Show.ID) -> SoFar.Position? {
        guard let pair = defaults.array(forKey: Self.keyPrefix + showID) as? [Int], pair.count == 2,
              pair[0] >= 1, pair[1] >= 1 else { return nil }
        return SoFar.Position(season: pair[0], episode: pair[1])
    }

    public func set(_ position: SoFar.Position, for showID: Show.ID) {
        defaults.set([position.season, position.episode], forKey: Self.keyPrefix + showID)
    }

    public func clear(for showID: Show.ID) {
        defaults.removeObject(forKey: Self.keyPrefix + showID)
    }
}
