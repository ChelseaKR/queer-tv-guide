import Foundation

// The snapshot contract as `schema/snapshot.v1.json` (draft 2020-12 JSON
// Schema, owned by the pipeline lane) defines it. This file is the app-side
// mirror of that contract; reconcile it whenever the schema changes.
//
// Two rules from `schema/README.md` govern every absence in this model:
//
// 1. LezWatch records deaths, not survival. `Character.death` therefore has
//    only two states — recorded or not recorded — never a third "survives"
//    state manufactured by the app. `died` in the wire format is `true` or
//    `null`; `false` would be a contract violation.
// 2. A show's schedule has two distinct kinds of "no next episode": TVmaze
//    matched the show and confirms nothing is upcoming (a positive
//    statement), or TVmaze was never matched at all (the schedule itself is
//    unknown). `Schedule.scheduleKnown` is what distinguishes them; collapsing
//    both into "no next episode" is exactly the bug this model exists to
//    prevent.

public struct Snapshot: Equatable, Sendable {
    public static let supportedSchemaVersion = "1"

    public let schemaVersion: String
    public let generatedAt: Date
    public let contentDigest: String
    public let license: License
    public let attribution: [AttributionItem]
    public let coverage: Coverage
    public let taxonomies: Taxonomies
    public let shows: [Show]
    public let characters: [Character]

    public init(schemaVersion: String, generatedAt: Date, contentDigest: String, license: License, attribution: [AttributionItem], coverage: Coverage, taxonomies: Taxonomies, shows: [Show], characters: [Character]) {
        self.schemaVersion = schemaVersion
        self.generatedAt = generatedAt
        self.contentDigest = contentDigest
        self.license = license
        self.attribution = attribution
        self.coverage = coverage
        self.taxonomies = taxonomies
        self.shows = shows
        self.characters = characters
        showsByID = Dictionary(uniqueKeysWithValues: shows.map { ($0.id, $0) })
        charactersByID = Dictionary(uniqueKeysWithValues: characters.map { ($0.id, $0) })
        characterIDsByShow = Self.indexCharactersByShow(characters)
    }

    public func show(id: Show.ID) -> Show? { showsByID[id] }
    public func character(id: Character.ID) -> Character? { charactersByID[id] }

    /// Characters listed for a show, in snapshot order. O(cast), not
    /// O(all characters): the "no recorded deaths" filter calls this once per
    /// show, and a linear scan made that 2,272 × 7,375 on real data.
    public func characters(inShow id: Show.ID) -> [Character] {
        (characterIDsByShow[id] ?? []).compactMap { charactersByID[$0] }
    }

    public func shows(forCharacter id: Character.ID) -> [Show] {
        guard let character = character(id: id) else { return [] }
        return character.shows.compactMap { show(id: $0.showID) }
    }

    public func similarShows(to show: Show) -> [Show] {
        show.similarShowIDs.compactMap(self.show(id:))
    }

    // Indices built once at init time; `shows`/`characters` can each carry
    // ~2,300 / ~7,400 records, so a linear `first(where:)` per lookup would
    // make every detail screen and every filter pass O(n).
    private let showsByID: [Show.ID: Show]
    private let charactersByID: [Character.ID: Character]
    private let characterIDsByShow: [Show.ID: [Character.ID]]

    private static func indexCharactersByShow(_ characters: [Character]) -> [Show.ID: [Character.ID]] {
        var index: [Show.ID: [Character.ID]] = [:]
        for character in characters {
            // A character listed twice for one show (two stints) appears once.
            for showID in Set(character.shows.map(\.showID)) {
                index[showID, default: []].append(character.id)
            }
        }
        return index
    }
}

extension Snapshot: Decodable {
    private enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case generatedAt = "generated_at"
        case contentDigest = "content_digest"
        // Published snapshot field name: spelling kept so every v1 file still decodes.
        case license = "licence"
        case attribution
        case coverage
        case taxonomies
        case shows
        case characters
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let version = try c.decode(String.self, forKey: .schemaVersion)
        guard version == Snapshot.supportedSchemaVersion else {
            throw SnapshotDecodingError.unsupportedSchemaVersion(version)
        }
        schemaVersion = version
        generatedAt = try c.decode(TaggedDate.self, forKey: .generatedAt).date
        contentDigest = try c.decode(String.self, forKey: .contentDigest)
        license = try c.decode(License.self, forKey: .license)
        attribution = try c.decode([AttributionItem].self, forKey: .attribution)
        coverage = try c.decode(Coverage.self, forKey: .coverage)
        taxonomies = try c.decode(Taxonomies.self, forKey: .taxonomies)
        shows = try c.decode([Show].self, forKey: .shows)
        characters = try c.decode([Character].self, forKey: .characters)
        showsByID = Dictionary(uniqueKeysWithValues: shows.map { ($0.id, $0) })
        charactersByID = Dictionary(uniqueKeysWithValues: characters.map { ($0.id, $0) })
        characterIDsByShow = Self.indexCharactersByShow(characters)
    }
}

// MARK: - Shared value types

/// A LezWatch taxonomy term as embedded on a record (`{slug, name}`).
public struct Term: Codable, Equatable, Sendable, Identifiable, Hashable {
    public var id: String { slug }
    public let slug: String
    public let name: String
    public init(slug: String, name: String) {
        self.slug = slug
        self.name = name
    }
}

/// A full taxonomy entry as it appears in `taxonomies.*`, carrying LezWatch's
/// own usage count for browse/filter chips.
public struct TermCount: Codable, Equatable, Sendable, Identifiable {
    public var id: Int { lwtvID }
    public let lwtvID: Int
    public let slug: String
    public let name: String
    public let count: Int?

    private enum CodingKeys: String, CodingKey {
        case lwtvID = "lwtv_id"
        case slug, name, count
    }
}

public struct Taxonomies: Codable, Equatable, Sendable {
    public let tropes: [TermCount]
    public let cliches: [TermCount]
    public let genders: [TermCount]
    public let sexualities: [TermCount]
    public let romantic: [TermCount]
    public let stations: [TermCount]
    public let genres: [TermCount]
    public let countries: [TermCount]
    public let formats: [TermCount]
    public let triggers: [TermCount]
    public let intersections: [TermCount]
    public let stars: [TermCount]
}

public struct License: Codable, Equatable, Sendable {
    public struct SnapshotLicense: Codable, Equatable, Sendable {
        public let spdx: String
        public let name: String
        public let url: URL
    }
    public let snapshot: SnapshotLicense
    /// Plain-language notice the app shows verbatim on the About screen.
    public let notice: String
}

public struct AttributionItem: Codable, Equatable, Sendable, Identifiable {
    public var id: String { source }
    public let source: String
    public let name: String
    public let url: URL
    public let text: String
    public let licenseName: String
    public let licenseURL: URL
    public let termsURL: URL
    public let termsReadOn: String // YYYY-MM-DD, displayed as-is

    private enum CodingKeys: String, CodingKey {
        case source, name, url, text
        // Published snapshot field names: spelling kept so every v1 file still decodes.
        case licenseName = "licence_name"
        case licenseURL = "licence_url"
        case termsURL = "terms_url"
        case termsReadOn = "terms_read_on"
    }
}

// MARK: - Coverage (two numbers, everywhere absence could be mistaken for a value)

public struct FetchedVsAvailable: Codable, Equatable, Sendable {
    public let available: Int?
    public let fetched: Int
}

public struct PresentVsAbsent: Codable, Equatable, Sendable {
    public let present: Int
    public let absent: Int
}

public struct Coverage: Codable, Equatable, Sendable {
    public struct LezWatch: Codable, Equatable, Sendable {
        public let shows: FetchedVsAvailable
        public let characters: FetchedVsAvailable
        public let actors: FetchedVsAvailable
    }
    public struct TVmaze: Codable, Equatable, Sendable {
        public struct Misses: Codable, Equatable, Sendable {
            public let noKey: Int
            public let ignoredBySource: Int
            public let notFound: Int
            public let other: Int
            private enum CodingKeys: String, CodingKey {
                case noKey = "no_key", ignoredBySource = "ignored_by_source", notFound = "not_found", other
            }
        }
        public let showsTotal: Int
        public let withJoinKey: Int
        public let joined: Int
        public let joinRate: Double
        public let misses: Misses
        private enum CodingKeys: String, CodingKey {
            case showsTotal = "shows_total", withJoinKey = "with_join_key", joined, joinRate = "join_rate", misses
        }
    }
    public let lezwatch: LezWatch
    public let tvmaze: TVmaze
    /// Keyed by dotted field path, e.g. "shows.watch_links".
    public let fields: [String: PresentVsAbsent]
}

// MARK: - Show

public struct Years: Codable, Equatable, Sendable {
    public enum OnAir: String, Codable, Sendable {
        case yes, no, unknown
    }
    public let start: Int?
    /// `nil` whether the show is ongoing or the field is simply blank;
    /// read `onAir` for the distinction.
    public let end: Int?
    public let onAir: OnAir

    private enum CodingKeys: String, CodingKey {
        case start, end
        case onAir = "on_air"
    }
}

public struct Ratings: Codable, Equatable, Sendable {
    /// LezWatch's verdict as recorded, open text (observed: "Yes", "Meh",
    /// "No", "TBD"); `nil` when not rated. Not a closed enum in the
    /// contract — the app must trust the shape and render new values,
    /// falling back to the raw text for filters it doesn't recognize.
    public let worthIt: String?
    public let worthItDetails: String?
    public let quality: Int?
    public let realness: Int?
    public let screentime: Int?
    public let score: Double?
    public let showWeLove: Bool

    private enum CodingKeys: String, CodingKey {
        case worthIt = "worth_it", worthItDetails = "worth_it_details"
        case quality, realness, screentime, score
        case showWeLove = "show_we_love"
    }

    /// The known subset of `worthIt`, for filtering. `nil` covers both "not
    /// rated" and an unrecognized value — the raw text (`worthIt`) is what
    /// the UI shows either way.
    public var worthItKnown: WorthIt? {
        guard let worthIt else { return nil }
        return WorthIt(rawValue: worthIt)
    }
}

public enum WorthIt: String, Sendable, CaseIterable {
    case yes = "Yes"
    case meh = "Meh"
    case no = "No"
    case tbd = "TBD"
}

public struct Counts: Codable, Equatable, Sendable {
    public let characters: Int
    public let deaths: Int
    public let charactersSourceReported: Int?
    public let deathsSourceReported: Int?

    private enum CodingKeys: String, CodingKey {
        case characters, deaths
        case charactersSourceReported = "characters_source_reported"
        case deathsSourceReported = "deaths_source_reported"
    }
}

public struct ExternalIDs: Codable, Equatable, Sendable {
    public let imdb: String?
    public let tmdb: String?
    public let tvmaze: Int?
}

public struct WatchLink: Codable, Equatable, Sendable, Identifiable {
    public var id: String { url.absoluteString }
    public let url: URL
    /// Registrable host, e.g. "netflix.com" — the label the app shows.
    /// Never a guessed service name.
    public let host: String
}

public struct ShowNotes: Codable, Equatable, Sendable {
    /// May contain spoilers; the app hides this behind a tap.
    public let plot: String?
    public let queerEpisodes: String?
    private enum CodingKeys: String, CodingKey {
        case plot
        case queerEpisodes = "queer_episodes"
    }
}

public struct Channel: Codable, Equatable, Sendable {
    public let name: String
    public let countryCode: String?
    private enum CodingKeys: String, CodingKey {
        case name
        case countryCode = "country_code"
    }
}

public struct Episode: Codable, Equatable, Sendable, Identifiable {
    public var id: Int { tvmazeID }
    public let tvmazeID: Int
    public let season: Int?
    /// `nil` for specials.
    public let number: Int?
    public let name: String?
    public let airdate: String? // YYYY-MM-DD as TVmaze records it
    public let airtime: String?
    public let airstamp: String?
    public let runtime: Int?
    public let url: URL

    private enum CodingKeys: String, CodingKey {
        case tvmazeID = "tvmaze_id"
        case season, number, name, airdate, airtime, airstamp, runtime, url
    }

    /// `airdate` parsed as a day, UTC. `nil` if the string doesn't parse —
    /// the raw `airdate` and `airstamp` remain available regardless.
    public var airdateDay: Date? {
        guard let airdate else { return nil }
        return ISO8601DayFormatter.date(from: airdate)
    }

    /// TVmaze supplies a placeholder airstamp when it has no broadcast time.
    /// Only an episode with both fields has a known instant.
    public var airInstant: Date? {
        guard let airtime, !airtime.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              let airstamp else { return nil }
        return ISO8601DateFormatter().date(from: airstamp)
    }
}

public struct ScheduleJoin: Codable, Equatable, Sendable {
    public enum Method: String, Codable, Sendable {
        case lwtvTvmazeID = "lwtv_tvmaze_id"
        case lwtvTvmazeIDManual = "lwtv_tvmaze_id_manual"
        case imdbLookup = "imdb_lookup"
        case none
    }
    public let method: Method
    public let matched: Bool
}

public struct Schedule: Codable, Equatable, Sendable {
    /// `true` iff TVmaze returned a show record for this show. When
    /// `false`, every other field here is `nil` and the app must say
    /// "schedule unknown" — never "no upcoming episode", which is a
    /// different, positive statement `scheduleKnown == true` makes.
    public let scheduleKnown: Bool
    public let join: ScheduleJoin
    public let tvmazeID: Int?
    public let tvmazeURL: URL?
    public let status: String?
    public let premiered: String?
    public let ended: String?
    public let network: Channel?
    public let webChannel: Channel?
    /// `nil` with `scheduleKnown == true` means TVmaze lists no upcoming
    /// episode (a positive statement). `nil` with `scheduleKnown == false`
    /// means unknown. Never collapse the two.
    public let nextEpisode: Episode?
    public let previousEpisode: Episode?

    private enum CodingKeys: String, CodingKey {
        case scheduleKnown = "schedule_known"
        case join
        case tvmazeID = "tvmaze_id"
        case tvmazeURL = "tvmaze_url"
        case status, premiered, ended, network
        case webChannel = "web_channel"
        case nextEpisode = "next_episode"
        case previousEpisode = "previous_episode"
    }
}

public struct Show: Codable, Equatable, Sendable, Identifiable {
    public typealias ID = String

    public let id: ID
    public let lwtvID: Int
    public let slug: String
    public let title: String
    public let alternateNames: [String]
    public let sourceURL: URL
    public let summary: String?
    public let years: Years
    public let seasons: Int?
    public let format: Term?
    public let networks: [Term]
    public let countries: [Term]
    public let genres: [Term]
    public let tropes: [Term]
    public let triggers: [Term]
    public let intersections: [Term]
    public let stars: [Term]
    public let ratings: Ratings
    public let counts: Counts
    public let externalIDs: ExternalIDs
    public let watchLinks: [WatchLink]
    public let similarShowIDs: [Show.ID]
    public let notes: ShowNotes
    public let schedule: Schedule
    public let sourceModifiedAt: Date

    private enum CodingKeys: String, CodingKey {
        case id
        case lwtvID = "lwtv_id"
        case slug, title
        case alternateNames = "alternate_names"
        case sourceURL = "source_url"
        case summary, years, seasons, format, networks, countries, genres, tropes, triggers, intersections, stars, ratings, counts
        case externalIDs = "external_ids"
        case watchLinks = "watch_links"
        case similarShowIDs = "similar_show_ids"
        case notes, schedule
        case sourceModifiedAt = "source_modified_at"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(ID.self, forKey: .id)
        lwtvID = try c.decode(Int.self, forKey: .lwtvID)
        slug = try c.decode(String.self, forKey: .slug)
        title = try c.decode(String.self, forKey: .title)
        alternateNames = try c.decode([String].self, forKey: .alternateNames)
        sourceURL = try c.decode(URL.self, forKey: .sourceURL)
        summary = try c.decodeIfPresent(String.self, forKey: .summary)
        years = try c.decode(Years.self, forKey: .years)
        seasons = try c.decodeIfPresent(Int.self, forKey: .seasons)
        format = try c.decodeIfPresent(Term.self, forKey: .format)
        networks = try c.decode([Term].self, forKey: .networks)
        countries = try c.decode([Term].self, forKey: .countries)
        genres = try c.decode([Term].self, forKey: .genres)
        tropes = try c.decode([Term].self, forKey: .tropes)
        triggers = try c.decode([Term].self, forKey: .triggers)
        intersections = try c.decode([Term].self, forKey: .intersections)
        stars = try c.decode([Term].self, forKey: .stars)
        ratings = try c.decode(Ratings.self, forKey: .ratings)
        counts = try c.decode(Counts.self, forKey: .counts)
        externalIDs = try c.decode(ExternalIDs.self, forKey: .externalIDs)
        watchLinks = try c.decode([WatchLink].self, forKey: .watchLinks)
        similarShowIDs = try c.decode([Show.ID].self, forKey: .similarShowIDs)
        notes = try c.decode(ShowNotes.self, forKey: .notes)
        schedule = try c.decode(Schedule.self, forKey: .schedule)
        sourceModifiedAt = try c.decode(TaggedDate.self, forKey: .sourceModifiedAt).date
    }

    public func encode(to encoder: Encoder) throws {
        fatalError("Show is decode-only in this app")
    }
}

// MARK: - Character

/// LezWatch records deaths, not survival: `died` is `true` or absent, never
/// `false`. `deathKnown` mirrors `died`; the app reads `deathKnown == false`
/// as "no recorded death", never as "survives" and never blank.
public struct Death: Decodable, Equatable, Sendable {
    public struct DateEntry: Decodable, Equatable, Sendable {
        public let date: String?
        public let year: Int?
        /// LezWatch's value verbatim (usually YYYYMMDD).
        public let raw: String
    }
    public let died: Bool?
    public let deathKnown: Bool
    /// One entry per recorded death (a character can die more than once).
    /// Empty when `deathKnown == false`.
    public let dates: [DateEntry]
    public let years: [Int]

    private enum CodingKeys: String, CodingKey {
        case died
        case deathKnown = "death_known"
        case dates, years
    }

    public init(died: Bool?, deathKnown: Bool, dates: [DateEntry], years: [Int]) {
        self.died = died
        self.deathKnown = deathKnown
        self.dates = dates
        self.years = years
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let died = try c.decodeIfPresent(Bool.self, forKey: .died)
        // The schema constrains `died` to `true` or `null`. LezWatch records
        // deaths, not survival, so `false` here would be the source
        // asserting a fact it structurally cannot assert — a contract
        // violation, not a value to render.
        if died == false {
            throw SnapshotDecodingError.malformed("died at \(c.codingPath.map(\.stringValue).joined(separator: ".")) is false; the contract only allows true or null (LezWatch records deaths, not survival)")
        }
        self.died = died
        deathKnown = try c.decode(Bool.self, forKey: .deathKnown)
        dates = try c.decode([DateEntry].self, forKey: .dates)
        years = try c.decode([Int].self, forKey: .years)
    }
}

public struct CharacterActor: Codable, Equatable, Sendable, Identifiable {
    public var id: Int { lwtvID }
    public let lwtvID: Int
    public let slug: String?
    /// `nil` when the actor id did not resolve in the actor export.
    public let name: String?
    private enum CodingKeys: String, CodingKey {
        case lwtvID = "lwtv_id"
        case slug, name
    }
}

public struct CharacterShowLink: Codable, Equatable, Sendable {
    public let showID: Show.ID
    /// LezWatch chartype: "regular", "recurring", "guest".
    public let role: String?
    public let years: [String]
    private enum CodingKeys: String, CodingKey {
        case showID = "show_id"
        case role, years
    }
}

public struct Character: Codable, Equatable, Sendable, Identifiable {
    public typealias ID = String

    public let id: ID
    public let lwtvID: Int
    public let slug: String
    public let name: String
    public let sourceURL: URL
    public let gender: Term?
    public let sexuality: Term?
    /// Romantic orientation, recorded for a minority of characters.
    public let romantic: Term?
    /// Includes "Dead" for dead characters; `death.died` is the authority,
    /// not the presence of this trope.
    public let cliches: [Term]
    public let actors: [CharacterActor]
    public let shows: [CharacterShowLink]
    public let death: Death
    public let sourceModifiedAt: Date

    private enum CodingKeys: String, CodingKey {
        case id
        case lwtvID = "lwtv_id"
        case slug, name
        case sourceURL = "source_url"
        case gender, sexuality, romantic, cliches, actors, shows, death
        case sourceModifiedAt = "source_modified_at"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(ID.self, forKey: .id)
        lwtvID = try c.decode(Int.self, forKey: .lwtvID)
        slug = try c.decode(String.self, forKey: .slug)
        name = try c.decode(String.self, forKey: .name)
        sourceURL = try c.decode(URL.self, forKey: .sourceURL)
        gender = try c.decodeIfPresent(Term.self, forKey: .gender)
        sexuality = try c.decodeIfPresent(Term.self, forKey: .sexuality)
        romantic = try c.decodeIfPresent(Term.self, forKey: .romantic)
        cliches = try c.decode([Term].self, forKey: .cliches)
        actors = try c.decode([CharacterActor].self, forKey: .actors)
        shows = try c.decode([CharacterShowLink].self, forKey: .shows)
        death = try c.decode(Death.self, forKey: .death)
        sourceModifiedAt = try c.decode(TaggedDate.self, forKey: .sourceModifiedAt).date
    }

    public func encode(to encoder: Encoder) throws {
        fatalError("Character is decode-only in this app")
    }
}

// MARK: - Date decoding

/// `generated_at` / `source_modified_at` are `datetime` in the schema:
/// `YYYY-MM-DDTHH:MM:SSZ`, UTC, second precision. Decoded strictly — a
/// non-conforming string fails the whole snapshot decode rather than
/// silently becoming "now" or the epoch.
struct TaggedDate: Decodable {
    let date: Date
    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        guard let parsed = ISO8601SecondFormatter.date(from: raw) else {
            throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath, debugDescription: "'\(raw)' is not a UTC datetime (YYYY-MM-DDTHH:MM:SSZ)"))
        }
        date = parsed
    }
}

let ISO8601SecondFormatter: ISO8601DateFormatter = {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime]
    return f
}()

let ISO8601DayFormatter: ISO8601DateFormatter = {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withFullDate, .withDashSeparatorInDate]
    f.timeZone = TimeZone(identifier: "UTC")
    return f
}()
