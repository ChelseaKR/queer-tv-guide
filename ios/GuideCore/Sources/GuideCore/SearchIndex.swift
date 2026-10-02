import Foundation

/// Local, case- and diacritic-insensitive search over shows and characters.
/// Built once per snapshot; queried per keystroke. No network, obviously.
///
/// Punctuation does not have to be typed: "greys anatomy" finds "Grey’s
/// Anatomy", "xena warrior" finds "Xena: Warrior Princess", and the words of
/// a query can come in any order ("adam degrassi" finds Adam Torres, from
/// Degrassi). Every entry's words are folded once, here, so a keystroke
/// costs comparisons, not string building.
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
        /// Only shows with a where-to-watch link on one of these hosts
        /// (`WatchHost.key`). Empty = no filter.
        public var watchHosts: Set<String> = []
        /// Only shows tagged with at least one of these tropes (slugs).
        /// Empty = no filter.
        public var tropes: Set<String> = []
        /// Leaves out shows whose trigger warning is one of these levels
        /// (slugs). A show with no trigger warning listed is kept: "none
        /// listed" is not a level, and it is not hidden.
        public var hiddenTriggerWarnings: Set<String> = []

        public init(
            worthIt: Set<WorthIt> = [],
            noRecordedDeaths: Bool = false,
            hasWatchLink: Bool = false,
            watchHosts: Set<String> = [],
            tropes: Set<String> = [],
            hiddenTriggerWarnings: Set<String> = []
        ) {
            self.worthIt = worthIt
            self.noRecordedDeaths = noRecordedDeaths
            self.hasWatchLink = hasWatchLink
            self.watchHosts = watchHosts
            self.tropes = tropes
            self.hiddenTriggerWarnings = hiddenTriggerWarnings
        }

        public var isEmpty: Bool { activeCount == 0 }

        /// How many filters are on, for the Filter button and the summary
        /// above the results. Each selected value counts once.
        public var activeCount: Int {
            worthIt.count + (noRecordedDeaths ? 1 : 0) + (hasWatchLink ? 1 : 0)
                + watchHosts.count + tropes.count + hiddenTriggerWarnings.count
        }
    }

    /// A where-to-watch site, as the filter offers it: the link's host
    /// without a leading "www.", so "www.netflix.com" and "netflix.com" are
    /// one choice.
    public struct WatchHost: Equatable, Sendable, Identifiable, Hashable {
        public let key: String
        /// Shows in this snapshot with at least one link on this host.
        public let showCount: Int
        public var id: String { key }

        public static func key(for host: String) -> String {
            let lower = host.lowercased()
            return lower.hasPrefix("www.") ? String(lower.dropFirst(4)) : lower
        }
    }

    /// A taxonomy term the filter offers, with how many shows carry it.
    public struct FilterTerm: Equatable, Sendable, Identifiable, Hashable {
        public let slug: String
        public let name: String
        public let showCount: Int
        public var id: String { slug }
    }

    /// What the filter screen can offer for this snapshot.
    public struct FilterOptions: Equatable, Sendable {
        /// Most shows first, then by name.
        public let watchHosts: [WatchHost]
        /// Alphabetical. Death-revealing tropes are left out: picking
        /// "Bury Your Queers" from a list would answer "does she die" for
        /// every show that list returns (`Presentation.deathSpoilerTropeSlugs`).
        public let tropes: [FilterTerm]
        /// Low, Medium, High, then any other level in the snapshot's order.
        public let triggerWarnings: [FilterTerm]
    }

    private struct Entry: Sendable {
        let hit: Hit
        let primary: String       // folded title / name
        let primaryWords: [String]
        let primaryCompact: String // folded, without spaces: "xfiles" finds "X-Files"
        let secondary: [String]   // folded actors, networks, show titles
        let secondaryWords: [String]
    }

    private let entries: [Entry]
    private let snapshot: Snapshot
    /// Shows in folded-title order, sorted once here rather than on every
    /// browse (which SwiftUI re-runs on each render of the Search screen).
    private let showsByTitle: [Show]
    private let watchHostKeysByShow: [Show.ID: Set<String>]
    public let filterOptions: FilterOptions

    public init(snapshot: Snapshot) {
        self.snapshot = snapshot
        var entries: [Entry] = []
        entries.reserveCapacity(snapshot.shows.count + snapshot.characters.count)
        for show in snapshot.shows {
            entries.append(Self.entry(.show(show), primary: show.title, secondary: show.alternateNames + show.networks.map(\.name)))
        }
        for character in snapshot.characters {
            let showTitles = character.shows.compactMap { snapshot.show(id: $0.showID)?.title }
            let actorNames = character.actors.compactMap(\.name)
            entries.append(Self.entry(.character(character), primary: character.name, secondary: actorNames + showTitles))
        }
        self.entries = entries
        self.showsByTitle = snapshot.shows
            .map { (Self.fold($0.title), $0) }
            .sorted { $0.0 < $1.0 }
            .map(\.1)

        var hostKeys: [Show.ID: Set<String>] = [:]
        var hostCounts: [String: Int] = [:]
        var tropeCounts: [String: Int] = [:]
        var triggerCounts: [String: Int] = [:]
        for show in snapshot.shows {
            let keys = Set(show.watchLinks.map { WatchHost.key(for: $0.host) })
            hostKeys[show.id] = keys
            for key in keys { hostCounts[key, default: 0] += 1 }
            for slug in Set(show.tropes.map(\.slug)) { tropeCounts[slug, default: 0] += 1 }
            for slug in Set(show.triggers.map(\.slug)) { triggerCounts[slug, default: 0] += 1 }
        }
        self.watchHostKeysByShow = hostKeys
        let hosts = hostCounts
            .map { WatchHost(key: $0.key, showCount: $0.value) }
            .sorted { $0.showCount != $1.showCount ? $0.showCount > $1.showCount : $0.key < $1.key }
        let tropes = snapshot.taxonomies.tropes
            .filter { !Presentation.deathSpoilerTropeSlugs.contains($0.slug) && (tropeCounts[$0.slug] ?? 0) > 0 }
            .map { FilterTerm(slug: $0.slug, name: $0.name, showCount: tropeCounts[$0.slug] ?? 0) }
            .sorted { Self.fold($0.name) < Self.fold($1.name) }
        let severity = ["low": 0, "medium": 1, "high": 2]
        let triggers = snapshot.taxonomies.triggers
            .filter { (triggerCounts[$0.slug] ?? 0) > 0 }
            .map { FilterTerm(slug: $0.slug, name: $0.name, showCount: triggerCounts[$0.slug] ?? 0) }
            .enumerated()
            .sorted { (severity[$0.element.slug] ?? 3, $0.offset) < (severity[$1.element.slug] ?? 3, $1.offset) }
            .map(\.element)
        self.filterOptions = FilterOptions(watchHosts: hosts, tropes: tropes, triggerWarnings: triggers)
    }

    private static func entry(_ hit: Hit, primary: String, secondary: [String]) -> Entry {
        let folded = fold(primary)
        let foldedSecondary = secondary.map(fold)
        return Entry(
            hit: hit,
            primary: folded,
            primaryWords: words(folded),
            primaryCompact: folded.replacingOccurrences(of: " ", with: ""),
            secondary: foldedSecondary,
            secondaryWords: foldedSecondary.flatMap(words)
        )
    }

    /// Empty or whitespace-only queries return nothing: the screen shows a
    /// browse prompt instead of the whole catalog.
    public func search(_ query: String, filters: Filters = Filters(), limit: Int = 50) -> [Hit] {
        results(for: query, filters: filters, limit: limit).hits
    }

    /// The best `limit` hits for a query, together with how many entries
    /// matched in all. A capped list must be able to say so: without the
    /// total, 50 rows look like the whole answer to a query that matches 500.
    /// One pass over the entries, same as `search`.
    public func results(for query: String, filters: Filters = Filters(), limit: Int = 50) -> SearchResults {
        let q = Self.fold(query)
        guard !q.isEmpty else { return SearchResults() }
        let query = Query(text: q, words: Self.words(q), compact: q.replacingOccurrences(of: " ", with: ""))
        var scored: [(score: Int, order: Int, hit: Hit)] = []
        for (order, entry) in entries.enumerated() {
            guard let score = Self.score(entry, query) else { continue }
            guard passes(entry.hit, filters) else { continue }
            scored.append((score, order, entry.hit))
        }
        scored.sort { a, b in a.score != b.score ? a.score > b.score : a.order < b.order }
        return SearchResults(hits: Array(scored.prefix(limit).map { $0.hit }), totalCount: scored.count)
    }

    /// All shows that pass the filters, alphabetical. Used for browsing when
    /// the query is empty.
    public func browse(filters: Filters) -> [Show] {
        showsByTitle.filter { passes(.show($0), filters) }
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
            if filters.hasWatchLink {
                guard !show.watchLinks.isEmpty else { return false }
            }
            if !filters.watchHosts.isEmpty {
                guard let keys = watchHostKeysByShow[show.id], !keys.isDisjoint(with: filters.watchHosts) else { return false }
            }
            if !filters.tropes.isEmpty {
                guard show.tropes.contains(where: { filters.tropes.contains($0.slug) }) else { return false }
            }
            if !filters.hiddenTriggerWarnings.isEmpty {
                guard !show.triggers.contains(where: { filters.hiddenTriggerWarnings.contains($0.slug) }) else { return false }
            }
            // Last: the one check that walks the cast.
            if filters.noRecordedDeaths {
                let coverage = deathCoverage(show)
                guard coverage.hasCharacters, !coverage.anyRecordedDeath else { return false }
            }
            return true
        }
    }

    private struct Query {
        let text: String
        let words: [String]
        let compact: String
    }

    /// Higher is better; `nil` is no match. Whole title first, then a title
    /// that starts with the query, then every query word starting a word of
    /// the title (any order), then the query anywhere in the title, then the
    /// same against actors, networks and show titles.
    private static func score(_ entry: Entry, _ q: Query) -> Int? {
        if entry.primary == q.text { return 100 }
        if entry.primary.hasPrefix(q.text) { return 80 }
        if allWordsStart(q.words, in: entry.primaryWords) { return 60 }
        if entry.primary.contains(q.text) || (!q.compact.isEmpty && entry.primaryCompact.contains(q.compact)) { return 40 }
        if entry.secondary.contains(where: { $0.hasPrefix(q.text) }) { return 30 }
        if allWordsStart(q.words, in: entry.primaryWords, or: entry.secondaryWords) { return 25 }
        if entry.secondary.contains(where: { $0.contains(q.text) }) { return 20 }
        return nil
    }

    /// Every query word starts some word in `words` (or in `more`), in any
    /// order. No arrays are built per keystroke.
    private static func allWordsStart(_ queryWords: [String], in words: [String], or more: [String] = []) -> Bool {
        guard !queryWords.isEmpty else { return false }
        return queryWords.allSatisfy { q in
            words.contains { $0.hasPrefix(q) } || more.contains { $0.hasPrefix(q) }
        }
    }

    private static func words(_ folded: String) -> [String] {
        folded.split(separator: " ").map(String.init)
    }

    /// Case, diacritics and width folded; "&" read as "and"; apostrophes
    /// dropped ("Grey’s" is "greys"); every other punctuation mark a space.
    static func fold(_ s: String) -> String {
        let folded = s.folding(options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive], locale: nil)
        var out = ""
        out.reserveCapacity(folded.count)
        for ch in folded {
            if ch == "&" {
                out += " and "
            } else if apostrophes.contains(ch) {
                continue
            } else if ch.isLetter || ch.isNumber {
                out.append(ch)
            } else {
                out.append(" ")
            }
        }
        return out.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
    }

    private static let apostrophes: Set<Swift.Character> = ["'", "’", "‘", "ʼ", "`", "´"]
}

/// What a search found: the hits it returns (the best few, ranked) and how
/// many entries matched in all.
public struct SearchResults: Equatable, Sendable {
    public let hits: [SearchIndex.Hit]
    /// Every entry that matched and passed the filters, before the cap.
    /// Never less than `hits.count`.
    public let totalCount: Int

    public init(hits: [SearchIndex.Hit] = [], totalCount: Int? = nil) {
        self.hits = hits
        self.totalCount = max(totalCount ?? hits.count, hits.count)
    }

    /// `true` when matches exist beyond the hits returned.
    public var isTruncated: Bool { totalCount > hits.count }

    /// One sentence saying the list is capped and by how much, or `nil` when
    /// every match is in the list. Shown above the results whether or not a
    /// filter is on: a list that stops short must not read as the whole
    /// answer. Words only, so it reads the same to VoiceOver.
    public func truncationNote(locale: Locale = .current) -> String? {
        guard isTruncated else { return nil }
        let total = totalCount.formatted(.number.locale(locale))
        let shown = hits.count.formatted(.number.locale(locale))
        let counted = hits.count == 1 ? "Showing the first match of \(total)." : "Showing the first \(shown) of \(total) matches."
        return "\(counted) Type more to narrow them."
    }
}
