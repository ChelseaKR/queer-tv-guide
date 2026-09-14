import Foundation

/// Local, case- and diacritic-insensitive search over shows and characters.
/// Built once per snapshot; queried per keystroke. No network, obviously.
public struct SearchIndex: Sendable {
    public enum Hit: Equatable, Sendable, Identifiable {
        case show(Show)
        case character(Character)

        public var id: String {
            switch self {
            case .show(let s): return "show:\(s.id)"
            case .character(let c): return "character:\(c.id)"
            }
        }
    }

    public struct Filters: Equatable, Sendable {
        /// Only shows whose worth-it verdict is one of these known values.
        /// Empty = no filter.
        public var worthIt: Set<WorthIt> = []
        /// Only shows in which no listed character has a recorded death. A
        /// show with no listed characters at all does NOT pass this filter:
        /// absence of any character is not the same as a checked, deathless
        /// cast (see `deathCoverage`).
        public var noRecordedDeaths: Bool = false
        /// Only shows with at least one where-to-watch link.
        public var hasWatchLink: Bool = false

        public init(worthIt: Set<WorthIt> = [], noRecordedDeaths: Bool = false, hasWatchLink: Bool = false) {
            self.worthIt = worthIt
            self.noRecordedDeaths = noRecordedDeaths
            self.hasWatchLink = hasWatchLink
        }

        public var isEmpty: Bool { worthIt.isEmpty && !noRecordedDeaths && !hasWatchLink }
    }

    private struct Entry: Sendable {
        let hit: Hit
        let primary: String      // folded title / name
        let secondary: [String]  // folded actors, networks, show titles
    }

    private let entries: [Entry]
    private let snapshot: Snapshot

    public init(snapshot: Snapshot) {
        self.snapshot = snapshot
        var entries: [Entry] = []
        entries.reserveCapacity(snapshot.shows.count + snapshot.characters.count)
        for show in snapshot.shows {
            entries.append(Entry(hit: .show(show), primary: Self.fold(show.title), secondary: (show.alternateNames + show.networks.map(\.name)).map(Self.fold)))
        }
        for character in snapshot.characters {
            let showTitles = character.shows.compactMap { snapshot.show(id: $0.showID)?.title }
            let actorNames = character.actors.compactMap(\.name)
            entries.append(Entry(hit: .character(character), primary: Self.fold(character.name), secondary: (actorNames + showTitles).map(Self.fold)))
        }
        self.entries = entries
    }

    /// Empty or whitespace-only queries return nothing: the screen shows a
    /// browse prompt instead of the whole catalogue.
    public func search(_ query: String, filters: Filters = Filters(), limit: Int = 50) -> [Hit] {
        let q = Self.fold(query)
        guard !q.isEmpty else { return [] }
        var scored: [(score: Int, order: Int, hit: Hit)] = []
        for (order, entry) in entries.enumerated() {
            guard let score = Self.score(entry, q) else { continue }
            guard passes(entry.hit, filters) else { continue }
            scored.append((score, order, entry.hit))
        }
        scored.sort { a, b in a.score != b.score ? a.score > b.score : a.order < b.order }
        return Array(scored.prefix(limit).map { $0.hit })
    }

    /// All shows that pass the filters, alphabetical. Used for browsing when
    /// the query is empty and a filter is on.
    public func browse(filters: Filters) -> [Show] {
        snapshot.shows
            .filter { passes(.show($0), filters) }
            .sorted { Self.fold($0.title) < Self.fold($1.title) }
    }

    public struct DeathCoverage: Equatable, Sendable {
        public let hasCharacters: Bool
        public let anyRecordedDeath: Bool
    }

    /// Whether any listed character in `show` has a recorded death,
    /// alongside whether the show has any listed characters at all — the
    /// two numbers a "no deaths" filter must not conflate.
    public func deathCoverage(_ show: Show) -> DeathCoverage {
        let cast = snapshot.characters(inShow: show.id)
        let anyDeath = cast.contains { $0.death.deathKnown && $0.death.died == true }
        return DeathCoverage(hasCharacters: !cast.isEmpty, anyRecordedDeath: anyDeath)
    }

    private func passes(_ hit: Hit, _ filters: Filters) -> Bool {
        guard !filters.isEmpty else { return true }
        switch hit {
        case .character(let c):
            // Filters describe shows; a character hit passes if any of its shows passes.
            return c.shows.compactMap { snapshot.show(id: $0.showID) }.contains { passes(.show($0), filters) }
        case .show(let show):
            if !filters.worthIt.isEmpty {
                guard let w = show.ratings.worthItKnown, filters.worthIt.contains(w) else { return false }
            }
            if filters.noRecordedDeaths {
                let coverage = deathCoverage(show)
                guard coverage.hasCharacters, !coverage.anyRecordedDeath else { return false }
            }
            if filters.hasWatchLink {
                guard !show.watchLinks.isEmpty else { return false }
            }
            return true
        }
    }

    private static func score(_ entry: Entry, _ q: String) -> Int? {
        if entry.primary == q { return 100 }
        if entry.primary.hasPrefix(q) { return 80 }
        if entry.primary.split(separator: " ").contains(where: { $0.hasPrefix(q) }) { return 60 }
        if entry.primary.contains(q) { return 40 }
        if entry.secondary.contains(where: { $0.hasPrefix(q) }) { return 30 }
        if entry.secondary.contains(where: { $0.contains(q) }) { return 20 }
        return nil
    }

    static func fold(_ s: String) -> String {
        s.folding(options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive], locale: nil)
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .split(whereSeparator: { $0.isWhitespace })
            .joined(separator: " ")
    }
}
