import Foundation

/// Pure text for every state the UI can be in, including every absence.
/// Kept here (not in the views) so tests can assert that an absent value
/// is *stated*, never blank and never a number — and, per
/// `schema/README.md`, never a manufactured "no" where the source only
/// records "not recorded".
public enum Presentation {
    // MARK: Worth it / ratings

    /// `worthIt` is open text in the contract (observed: "Yes", "Meh", "No",
    /// "TBD"); an unrecognised non-nil value is shown as itself rather than
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

    /// Show-level summary after the reveal.
    public static func deathsSummary(cast: [Character]) -> String {
        guard !cast.isEmpty else { return noListedCast }
        let dead = cast.filter { $0.death.deathKnown && $0.death.died == true }
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
    ///   characters appear in more than one show (e.g. across a franchise),
    ///   so for them the record cannot say this show is where it happens.
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
    public static let deathSpoilerClicheSlugs: Set<String> = ["dead"]
    public static let deathSpoilerTropeSlugs: Set<String> = ["dead-queers"]

    /// `terms` minus any whose slug is in `spoilers`, order kept.
    public static func withoutSpoilers(_ terms: [Term], _ spoilers: Set<String>) -> [Term] {
        terms.filter { !spoilers.contains($0.slug) }
    }

    /// The show-level answer when the snapshot lists nobody to answer about.
    static let noListedCast = "Not recorded. This snapshot does not list any queer characters for this show."

    public static func showDeaths(cast: [Character], show: Show) -> ShowDeaths {
        var notes: [String] = []
        let spoilerTags = show.tropes.filter { deathSpoilerTropeSlugs.contains($0.slug) }
        guard !cast.isEmpty else {
            notes += spoilerTags.map { "LezWatch.TV tags this show “\($0.name)”." }
            return ShowDeaths(headline: noListedCast, lines: [], notes: notes)
        }
        let dead = cast.filter { $0.death.deathKnown && $0.death.died == true }
        let listed = "\(cast.count) listed \(cast.count == 1 ? "character" : "characters")"
        if let reported = show.counts.deathsSourceReported, reported != dead.count {
            notes.append("LezWatch.TV's own tally for this show is \(reported) \(reported == 1 ? "death" : "deaths"); its character records list \(dead.count).")
        }
        notes += spoilerTags.map { "LezWatch.TV tags this show “\($0.name)”." }
        guard !dead.isEmpty else {
            return ShowDeaths(
                headline: cast.count == 1
                    ? "Not recorded. This snapshot does not record a death for the one listed character."
                    : "Not recorded. This snapshot does not record a death for any of the \(listed).",
                lines: [],
                notes: notes
            )
        }
        let lines = dead.map { character -> String in
            let years = character.death.years.sorted().map(String.init).joined(separator: ", ")
            let when = years.isEmpty ? "" : " (\(years))"
            let showCount = Set(character.shows.map(\.showID)).count
            if showCount > 1 {
                return "\(character.name): a death is recorded\(when). \(character.name) appears in \(showCount) shows, and the record does not say which one."
            }
            return "\(character.name) dies\(when)."
        }
        return ShowDeaths(
            headline: "\(dead.count) of \(listed) \(dead.count == 1 ? "has" : "have") a recorded death.",
            lines: lines,
            notes: notes
        )
    }

    // MARK: Where to watch / schedule

    public static let noWatchLinks = "No where-to-watch link in this snapshot."
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
        if let t = e.name, !t.isEmpty { parts.append("“\(t)”") }
        let head = parts.isEmpty ? "Next episode" : parts.joined(separator: " ")
        guard let day = e.airdateDay else { return "\(head) — air date not recorded" }
        if isPast(day, today: today) {
            return "\(head) — listed for \(dayFormatter.string(from: day)), which has passed. This data may be out of date."
        }
        return "\(head) — \(dayFormatter.string(from: day))"
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
}
