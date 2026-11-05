import Foundation

/// Pure text for every state the UI can be in, including every absence.
/// Kept here (not in the views) so tests can assert that an absent value
/// is *stated*, never blank and never a number — and, per
/// `schema/README.md`, never a manufactured "no" where the source only
/// records "not recorded".
public enum Presentation {
    // MARK: Worth it / ratings

    /// `worthIt` is open text in the contract (observed: "Yes", "Meh", "No",
    /// "TBD"); an unrecognized non-nil value is shown as itself rather than
    /// forced into a known bucket or hidden.
    public static func worthIt(_ value: String?) -> String {
        value ?? "Not rated"
    }

    public static func rating(_ value: Int?, label: String) -> String {
        guard let value else { return "\(label): not rated" }
        return "\(label): \(value) of 5"
    }

    /// Just the value half of `rating(_:label:)`, for a UI that supplies its
    /// own label (e.g. `LabeledContent`).
    public static func ratingValue(_ value: Int?) -> String {
        guard let value else { return "Not rated" }
        return "\(value) of 5"
    }

    public static func score(_ value: Double?) -> String {
        guard let value else { return "No score recorded" }
        return "Score \(String(format: "%.0f", value)) (an ordinal LezWatch ranking, not a percentage)"
    }

    // MARK: Death
    //
    // LezWatch records deaths, not survival: there is no "survives" state in
    // the contract. `deathKnown == false` means exactly "no death is
    // recorded in this snapshot" — it must never read as a confirmed "no"
    // or "she lives".
    //
    // Every unknown answer opens with "Not recorded." A sentence that opens
    // with "No …" ("No death is recorded …") is heard as "No" by a VoiceOver
    // user who moves on after the first word, and "No" answers "does she
    // die?" with a fact the source never asserts.

    /// The spoiler text itself, shown only after the user chooses to reveal
    /// it. `name` lets it read as a sentence about a person.
    public static func death(_ death: Death, name: String) -> String {
        guard death.deathKnown, death.died == true else {
            return "Not recorded. This snapshot does not record a death for \(name)."
        }
        if death.years.isEmpty {
            return "Yes. \(name) dies. The year is not recorded."
        }
        let list = death.years.sorted().map(String.init).joined(separator: ", ")
        return death.years.count > 1
            ? "Yes. \(name) dies more than once, recorded in \(list)."
            : "Yes. \(name) dies (\(list))."
    }

    public static func deathShort(_ death: Death) -> String {
        death.deathKnown && death.died == true ? "Dies" : "Death not recorded"
    }

    /// Show-level summary after the reveal. Counts only deaths placed in
    /// this show (`deathPlacement`, DECISIONS 0030).
    public static func deathsSummary(cast: [Character], showID: Show.ID) -> String {
        guard !cast.isEmpty else { return noListedCast }
        let dead = cast.filter { deathPlacement($0, inShow: showID).counts }
        if dead.isEmpty {
            return "Not recorded for any of the \(cast.count) listed \(cast.count == 1 ? "character" : "characters")."
        }
        return "\(dead.count) of \(cast.count) listed \(cast.count == 1 ? "character" : "characters") \(dead.count == 1 ? "dies" : "die"): \(dead.map(\.name).joined(separator: ", "))."
    }

    /// The show-level answer to "do any queer characters die?", as a
    /// headline plus one line per character with a recorded death.
    ///
    /// Two limits of the source are stated rather than papered over
    /// (measured on the 2026-09-17 snapshot):
    /// - LezWatch records a death on the *character*, not on a show. 21 dead
    ///   characters appear in more than one show (e.g. across a franchise).
    ///   For them a death counts in this show only when its year is one of
    ///   the character's years in this show (DECISIONS 0030, the site's
    ///   rule); otherwise the line says it is not recorded in this show and
    ///   a note says how many are not counted (`deathPlacement`).
    /// - LezWatch's own per-show death tally disagrees with its character
    ///   records for 31 shows. When it does, both numbers are shown.
    /// - The show's own death-revealing trope ("Bury Your Queers") is kept
    ///   out of the always-visible tropes list and stated here instead.
    public struct ShowDeaths: Equatable, Sendable {
        public let headline: String
        public let lines: [String]
        /// Source-level context: a disagreeing LezWatch tally, the
        /// death-revealing trope tag. Shown smaller, after the lines.
        public let notes: [String]

        /// Everything, in reading order, for a single VoiceOver element.
        public var spoken: String { ([headline] + lines + notes).joined(separator: " ") }
    }

    // MARK: Death spoilers outside the reveal

    /// LezWatch terms whose mere presence answers "does she die". They are
    /// kept out of the always-visible trope lists so the tap-to-reveal
    /// control is not defeated by the line above it. Measured on the
    /// 2026-09-17 snapshot: the character cliché "Dead Queers" (`dead`) is
    /// on 648 of the 677 characters with a recorded death and on no other
    /// character; the show trope "Bury Your Queers" (`dead-queers`) is on
    /// 427 shows.
    ///
    /// The show tropes, checked against every trope in the 2026-11-04
    /// snapshot (2,289 shows, 19% with a recorded death):
    /// - "Bury Your Queers" (`dead-queers`): 421 of 430 tagged shows have a
    ///   recorded death (98%).
    /// - "Happiness then Tragedy" (`happy-then-not`): 51 of 67 (76%), and
    ///   the name itself foretells the fate.
    /// - "None!" (`none`): 0 of 224. Seeing it says no "Bury Your Queers"
    ///   tag, so it answers the question the other way.
    /// No other trope is a fate tag or moves far from the 19% base rate
    /// ("Happy Ending" is 21%), so the rest stay visible. This is the one
    /// list: the show screen, the reveal's notes and the trope filter all
    /// read it.
    public static let deathSpoilerClicheSlugs: Set<String> = ["dead"]
    public static let deathSpoilerTropeSlugs: Set<String> = ["dead-queers", "happy-then-not", "none"]

    /// The reveal's note for a spoiler trope tag.
    static func spoilerTagNote(_ tag: Term) -> String {
        tag.slug == "none"
            ? "LezWatch.TV lists no tropes for this show (“None!”)."
            : "LezWatch.TV tags this show “\(tag.name)”."
    }

    /// `terms` minus any whose slug is in `spoilers`, order kept.
    public static func withoutSpoilers(_ terms: [Term], _ spoilers: Set<String>) -> [Term] {
        terms.filter { !spoilers.contains($0.slug) }
    }

    /// The show-level answer when the snapshot lists nobody to answer about.
    static let noListedCast = "Not recorded. This snapshot does not list any queer characters for this show."

    /// Where a character's recorded death falls for one show (DECISIONS
    /// 0030, the site's rule in `show_pages._death_status`). LezWatch
    /// records a death on the character, not on a show. For a character
    /// linked to more than one show, the death counts for this show only
    /// when a death year is one of the character's years in this show (the
    /// link's `years`). Otherwise the snapshot cannot place it here, so the
    /// answer for this show is unknown, never a guess either way.
    public enum DeathPlacement: Equatable, Sendable {
        /// No death is recorded for the character.
        case notRecorded
        /// A death is recorded and the character is linked to this show only.
        case onlyShow
        /// A multi-show character whose death year(s) fall in this show's
        /// years for them: counted here.
        case inShowYears([Int])
        /// Multi-show, and the death has no recorded year: not counted.
        case noDeathYear
        /// Multi-show, and the link to this show has no years: not counted.
        case noShowYears
        /// Multi-show, and no death year is a year the character appears in
        /// this show: not counted.
        case outsideShowYears

        /// True when the death counts as happening in this show.
        public var counts: Bool {
            switch self {
            case .onlyShow, .inShowYears: return true
            case .notRecorded, .noDeathYear, .noShowYears, .outsideShowYears: return false
            }
        }

        /// A death that could be in this show: counted, or one the snapshot
        /// cannot place either way. The "no recorded deaths" filter reads
        /// this, so it never admits a show on a guess.
        public var mayBeHere: Bool {
            switch self {
            case .onlyShow, .inShowYears, .noDeathYear, .noShowYears: return true
            case .notRecorded, .outsideShowYears: return false
            }
        }

        /// A recorded death that this show's years do not place here.
        public var elsewhere: Bool {
            switch self {
            case .noDeathYear, .noShowYears, .outsideShowYears: return true
            case .notRecorded, .onlyShow, .inShowYears: return false
            }
        }
    }

    public static func deathPlacement(_ character: Character, inShow showID: Show.ID) -> DeathPlacement {
        let death = character.death
        guard death.deathKnown, death.died == true else { return .notRecorded }
        let otherShows = Set(character.shows.map(\.showID)).subtracting([showID])
        if otherShows.isEmpty { return .onlyShow }
        let here = Set(character.shows.filter { $0.showID == showID }.flatMap(\.years))
        let matched = death.years.sorted().filter { here.contains(String($0)) }
        if !matched.isEmpty { return .inShowYears(matched) }
        if death.years.isEmpty { return .noDeathYear }
        if here.isEmpty { return .noShowYears }
        return .outsideShowYears
    }

    /// "2017", "2017 and 2019", "2015, 2017 and 2019".
    static func andList(_ items: [String]) -> String {
        guard items.count > 1 else { return items.first ?? "" }
        return items.dropLast().joined(separator: ", ") + " and " + items[items.count - 1]
    }

    /// The reveal's line for one character with a recorded death.
    static func deathLine(_ character: Character, _ placement: DeathPlacement) -> String? {
        let name = character.name
        let years = character.death.years.sorted().map(String.init).joined(separator: ", ")
        let when = years.isEmpty ? "" : " (\(years))"
        switch placement {
        case .notRecorded:
            return nil
        case .onlyShow:
            return "\(name) dies\(when)."
        case .inShowYears(let matched):
            let list = andList(matched.map(String.init))
            return "\(name) dies\(when). The record belongs to the character, not to one show; it is counted here because \(list) \(matched.count == 1 ? "is" : "are") among \(name)\u{2019}s years in this show."
        case .noDeathYear:
            return "\(name): not recorded in this show. LezWatch.TV records a death for \(name) but no year, so it cannot say whether it happens in this show."
        case .noShowYears:
            return "\(name): not recorded in this show. LezWatch.TV records a death for \(name)\(when) but not \(name)\u{2019}s years in this show, so it cannot say whether it happens here."
        case .outsideShowYears:
            return "\(name): not recorded in this show. LezWatch.TV records a death for \(name)\(when), but not in a year \(name) appears in this show. It may happen in another show."
        }
    }

    public static func showDeaths(cast: [Character], show: Show) -> ShowDeaths {
        var notes: [String] = []
        let spoilerTags = show.tropes.filter { deathSpoilerTropeSlugs.contains($0.slug) }
        guard !cast.isEmpty else {
            notes += spoilerTags.map(spoilerTagNote)
            return ShowDeaths(headline: noListedCast, lines: [], notes: notes)
        }
        let placed = cast.map { ($0, deathPlacement($0, inShow: show.id)) }
        let counted = placed.filter { $0.1.counts }
        let elsewhere = placed.filter { $0.1.elsewhere }
        let inThisShow = elsewhere.isEmpty ? "" : " in this show"
        let listed = "\(cast.count) listed \(cast.count == 1 ? "character" : "characters")"
        if !elsewhere.isEmpty {
            notes.append(elsewhere.count == 1
                ? "One listed character has a recorded death that LezWatch.TV does not place in this show, so it is not counted here."
                : "\(elsewhere.count) listed characters have a recorded death that LezWatch.TV does not place in this show, so they are not counted here.")
        }
        if let reported = show.counts.deathsSourceReported, reported != counted.count {
            let records = elsewhere.isEmpty ? "list \(counted.count)" : "place \(counted.count) in this show"
            notes.append("LezWatch.TV's own tally for this show is \(reported) \(reported == 1 ? "death" : "deaths"); its character records \(records).")
        }
        notes += spoilerTags.map(spoilerTagNote)
        // Counted deaths first, then the ones this show's years do not place.
        let lines = (counted + elsewhere).compactMap { deathLine($0.0, $0.1) }
        guard !counted.isEmpty else {
            return ShowDeaths(
                headline: cast.count == 1
                    ? "Not recorded. This snapshot does not record a death\(inThisShow) for the one listed character."
                    : "Not recorded. This snapshot does not record a death\(inThisShow) for any of the \(listed).",
                lines: lines,
                notes: notes
            )
        }
        return ShowDeaths(
            headline: "\(counted.count) of \(listed) \(counted.count == 1 ? "has" : "have") a recorded death\(inThisShow).",
            lines: lines,
            notes: notes
        )
    }

    // MARK: Trigger-warning level

    /// LezWatch.TV's trigger-warning level for a show, labeled and explained.
    /// The snapshot carries only the level's name ("High"); on its own that
    /// says nothing about what is measured. The meanings are LezWatch.TV's
    /// own wording, from its page for each level (checked 2026-11-05). No
    /// link to those pages: the app's source names one host only
    /// (SourceTreeGuardTests), and the show's own LezWatch.TV link is on
    /// the same screen. An unrated show says it is unrated, never "none".
    public struct TriggerWarning: Equatable, Sendable {
        public let heading: String
        /// "High", "Medium", "Low", or "Not rated".
        public let level: String
        /// What the level means, or what an unrated show does not mean.
        public let meaning: String

        public var spoken: String { "\(heading): \(level). \(meaning)" }
    }

    public static let triggerHeading = "LezWatch.TV trigger-warning level"

    static let triggerMeanings: [String: String] = [
        "high": "LezWatch.TV: \u{201c}Scenes of explicit violence, drug use, suicide, sex, and/or abuse occur regularly. Not intended for children or sensitive viewers.\u{201d}",
        "medium": "LezWatch.TV: \u{201c}Designated as \u{2018}strong content,\u{2019} subject matter regularly discusses and sometimes depicts violence and abuse. Viewer discretion is advised.\u{201d}",
        "low": "LezWatch.TV: \u{201c}While generally acceptable for the over 14 crowd, there may be some sensitive topics now and then.\u{201d}",
    ]

    public static func triggerWarning(_ triggers: [Term]) -> TriggerWarning {
        guard !triggers.isEmpty else {
            return TriggerWarning(
                heading: triggerHeading,
                level: "Not rated",
                meaning: "LezWatch.TV has not given this show a level. That does not mean it has no difficult content."
            )
        }
        let level = triggers.map(\.name).joined(separator: ", ")
        let known = triggers.compactMap { triggerMeanings[$0.slug] }
        let meaning = known.isEmpty
            ? "LezWatch.TV gives this level without a description in this snapshot."
            : known.joined(separator: " ")
        return TriggerWarning(heading: triggerHeading, level: level, meaning: meaning)
    }

    // MARK: Where to watch / schedule

    public static let noWatchLinks = "No where-to-watch link in this snapshot."

    /// A where-to-watch link's host as people write it: "www.amazon.com"
    /// becomes "amazon.com". Only a leading "www." is dropped.
    public static func displayHost(_ host: String) -> String {
        let lowered = host.lowercased()
        return lowered.hasPrefix("www.") ? String(host.dropFirst(4)) : host
    }

    /// The label for a where-to-watch link: "Watch on Netflix" when one of
    /// the show's own networks is the site's name, otherwise "Watch on
    /// amazon.com". A link carries only its URL and host, so a name is used
    /// only when it matches the host's site name exactly (letters and digits
    /// only, case ignored): "Prime Video" for primevideo.com, "HBO Max" for
    /// hbomax.com. Nothing is guessed: amazon.com is not called Prime
    /// Video, and tv.apple.com is not called Apple TV+.
    public static func watchLinkLabel(_ link: WatchLink, networks: [Term]) -> String {
        "Watch on \(watchLinkService(link, networks: networks))"
    }

    /// The service name from `watchLinkLabel`, without "Watch on".
    public static func watchLinkService(_ link: WatchLink, networks: [Term]) -> String {
        let host = displayHost(link.host)
        let parts = host.split(separator: ".")
        if parts.count >= 2 {
            let site = comparable(String(parts[parts.count - 2]))
            if !site.isEmpty, let network = networks.first(where: { comparable($0.name) == site }) {
                return network.name
            }
        }
        return host
    }

    private static func comparable(_ text: String) -> String {
        String(String.UnicodeScalarView(text.lowercased().unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) }))
    }
    public static let noTropes = "No tropes listed."
    public static let noTriggers = "No trigger warnings listed."
    public static let noSummary = "No summary in this snapshot."
    public static let noCharacters = "No characters listed for this show."
    public static let noPlot = "No plot notes in this snapshot."

    /// `scheduleKnown == false` ("TVmaze was never matched") and
    /// `scheduleKnown == true` with `nextEpisode == nil` ("TVmaze confirms
    /// nothing is upcoming") are different facts and must read differently.
    ///
    /// The snapshot can be days or months old (offline, or a failed
    /// refresh), so a "next" episode whose air date has already passed is
    /// said to be past — never presented as still upcoming. `today` is
    /// injectable for tests; the comparison is by calendar day, UTC, with a
    /// one-day grace so a broadcast-timezone date is never called past early.
    public static func nextEpisode(_ schedule: Schedule, today: Date = Date()) -> String {
        guard schedule.scheduleKnown else { return "Schedule unknown for this show." }
        guard let e = schedule.nextEpisode else { return "No upcoming episode is known." }
        var parts: [String] = []
        if let s = e.season, let n = e.number { parts.append("S\(s)E\(n)") }
        if let t = e.name, !t.isEmpty { parts.append("\u{201c}\(t)\u{201d}") }
        let head = parts.isEmpty ? "Next episode" : parts.joined(separator: " ")

        if let instant = e.airInstant {
            let cal = Calendar(identifier: .gregorian)
            let dayStart = cal.startOfDay(for: instant)
            let todayStart = cal.startOfDay(for: today)
            if dayStart < todayStart.addingTimeInterval(-86400) {
                return "\(head) — \(instantFormatter.string(from: instant)), which has passed. This data may be out of date."
            }
            return "\(head) — \(instantFormatter.string(from: instant))"
        }

        guard let day = e.airdateDay else { return "\(head) \u{2014} air date not recorded" }
        if isPast(day, today: today) {
            return "\(head) \u{2014} listed for \(dayFormatter.string(from: day)), which has passed. This data may be out of date."
        }
        return "\(head) \u{2014} \(dayFormatter.string(from: day)) (date as TVmaze lists it, in the network\u{2019}s time zone)"
    }

    /// True when `day` (a UTC calendar day) is more than one day before
    /// `today`'s UTC calendar day.
    public static func isPast(_ day: Date, today: Date) -> Bool {
        var utc = Calendar(identifier: .gregorian)
        utc.timeZone = TimeZone(identifier: "UTC")!
        let startOfToday = utc.startOfDay(for: today)
        guard let graceStart = utc.date(byAdding: .day, value: -1, to: startOfToday) else { return false }
        return day < graceStart
    }

    public static func years(_ y: Years) -> String {
        switch (y.start, y.end, y.onAir) {
        case (nil, _, .unknown): return "Air dates not recorded"
        case (let s?, nil, .yes): return "\(s) – present"
        case (let s?, nil, _): return "\(s) – ongoing status not recorded"
        case (let s?, let e?, _): return "\(s) – \(e)"
        case (nil, let e?, _): return "Ended \(e)"
        case (nil, nil, _): return "Air dates not recorded"
        }
    }

    /// LezWatch stores 0 for a season count never filled in (294 shows in
    /// the 2026-09-17 snapshot, including multi-season shows like Xena). The
    /// pipeline now maps that to null, but a snapshot bundled or cached
    /// before that fix still carries 0, so 0 reads as not recorded here too
    /// — never "0 seasons".
    public static func seasons(_ n: Int?) -> String {
        guard let n, n > 0 else { return "Seasons not recorded" }
        return n == 1 ? "1 season" : "\(n) seasons"
    }

    public static func terms(_ items: [Term], empty: String) -> String {
        items.isEmpty ? empty : items.map(\.name).joined(separator: ", ")
    }

    // MARK: Data status

    public static func generatedAt(_ date: Date) -> String {
        "Data as of \(dateTimeFormatter.string(from: date))"
    }

    /// The data-status line on every screen that reads the snapshot: when
    /// the data was last updated, and how long ago that was. An age that
    /// cannot be worked out is said to be unknown, never left off (which
    /// would read as current).
    public static func dataAsOf(_ date: Date, freshness: DataFreshness) -> String {
        switch freshness {
        case .current(let seconds), .stale(let seconds):
            return "\(generatedAt(date)) (\(age(seconds)))"
        case .unknown:
            return "\(generatedAt(date)) (age unknown: that is later than this device's clock)"
        }
    }

    /// "less than an hour ago", "1 hour ago", "30 hours ago", then whole
    /// days from two days on. Rounded down, so an age is never overstated
    /// into the next threshold, and never understated past it either: 48
    /// hours and one second is "2 days ago", and stale.
    public static func age(_ seconds: TimeInterval) -> String {
        let hours = Int(max(0, seconds) / 3600)
        if hours < 1 { return "less than an hour ago" }
        if hours < 48 { return hours == 1 ? "1 hour ago" : "\(hours) hours ago" }
        return "\(hours / 24) days ago"
    }

    /// "3 days", "6 hours", "1 hour": a length of time in whole days when it
    /// is one, else whole hours. For the wording of `refreshTriggers` only.
    static func span(_ seconds: TimeInterval) -> String {
        let hours = max(1, Int((seconds / 3600).rounded()))
        if hours >= 24, hours % 24 == 0 {
            let days = hours / 24
            return days == 1 ? "1 day" : "\(days) days"
        }
        return hours == 1 ? "1 hour" : "\(hours) hours"
    }

    /// When returning to the app looks for new data, in words, built from the
    /// numbers `ForegroundRefreshGate` acts on so the two cannot drift:
    /// "while its data is more than 3 days old (at most once every 6 hours)".
    /// The out-of-date banner, the About screen, the privacy policy and the
    /// support page all say this (ForegroundRefreshTests holds the pages to
    /// it).
    public static var returnRefreshRule: String {
        "while its data is more than \(span(ForegroundRefreshGate.staleAfter)) old (at most once every \(span(ForegroundRefreshGate.minimumInterval)))"
    }

    /// What a stale or unknown-age snapshot says about itself, above the
    /// content it affects. `nil` only when the data is current.
    public struct FreshnessWarning: Equatable, Sendable {
        public let title: String
        public let detail: String
        /// Everything, in reading order, for one VoiceOver element. Opens
        /// with "Warning" so a listener who moves on after the first word
        /// still hears that something is wrong.
        public var spoken: String { "Warning. \(title). \(detail)" }
    }

    public static func freshnessWarning(generatedAt date: Date, freshness: DataFreshness) -> FreshnessWarning? {
        switch freshness {
        case .current:
            return nil
        case .stale(let seconds):
            return FreshnessWarning(
                title: "This data is out of date",
                detail: "It was last updated \(age(seconds)), on \(dateTimeFormatter.string(from: date)). Next episodes and where-to-watch links may have changed since then. The app looks for new data each time it opens, and when you return to it \(returnRefreshRule). Pull down on Search to look now."
            )
        case .unknown:
            return FreshnessWarning(
                title: "This data's age is unknown",
                detail: "It is dated \(dateTimeFormatter.string(from: date)), which is later than this device's clock, so the app can't tell how old it is. Treat it as possibly out of date, and check the date and time in Settings."
            )
        }
    }

    // MARK: Favorites backup

    /// What an import did, counted: every entry in the file is accounted
    /// for, including the ones skipped.
    public static func importSummary(added: Int, alreadySaved: Int, notInSnapshot: Int, unreadable: Int) -> String {
        func count(_ n: Int, _ one: String, _ many: String) -> String { "\(n) \(n == 1 ? one : many)" }
        if added + alreadySaved + notInSnapshot + unreadable == 0 {
            return "The file lists no favorites. Nothing was added."
        }
        var sentences = [added == 0 ? "No new favorites were added." : "Added \(count(added, "favorite", "favorites"))."]
        if alreadySaved > 0 {
            sentences.append("\(count(alreadySaved, "was", "were")) already saved.")
        }
        if notInSnapshot > 0 {
            sentences.append("\(count(notInSnapshot, "is", "are")) not in this snapshot and \(notInSnapshot == 1 ? "was" : "were") skipped.")
        }
        if unreadable > 0 {
            sentences.append("\(count(unreadable, "entry", "entries")) could not be read and \(unreadable == 1 ? "was" : "were") skipped.")
        }
        return sentences.joined(separator: " ")
    }

    public static let dayFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateStyle = .medium
        f.timeStyle = .none
        f.timeZone = TimeZone(identifier: "UTC")
        return f
    }()

    public static let dateTimeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateStyle = .medium
        f.timeStyle = .short
        return f
    }()

    public static let instantFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateStyle = .medium
        f.timeStyle = .short
        f.timeZone = TimeZone.current
        return f
    }()
}
