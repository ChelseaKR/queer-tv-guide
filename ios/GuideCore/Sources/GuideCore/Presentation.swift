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

    /// The spoiler text itself, shown only after the user chooses to reveal
    /// it. `name` lets it read as a sentence about a person.
    public static func death(_ death: Death, name: String) -> String {
        guard death.deathKnown, death.died == true else {
            return "No death is recorded for \(name) in this snapshot."
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
        death.deathKnown && death.died == true ? "Dies" : "No recorded death"
    }

    /// Show-level summary after the reveal.
    public static func deathsSummary(cast: [Character]) -> String {
        guard !cast.isEmpty else { return "No queer characters are listed for this show in this snapshot." }
        let dead = cast.filter { $0.death.deathKnown && $0.death.died == true }
        if dead.isEmpty {
            return "No recorded deaths among \(cast.count) listed \(cast.count == 1 ? "character" : "characters")."
        }
        return "\(dead.count) of \(cast.count) listed \(cast.count == 1 ? "character" : "characters") \(dead.count == 1 ? "dies" : "die"): \(dead.map(\.name).joined(separator: ", "))."
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
    public static func nextEpisode(_ schedule: Schedule) -> String {
        guard schedule.scheduleKnown else { return "Schedule unknown for this show." }
        guard let e = schedule.nextEpisode else { return "No upcoming episode is known." }
        var parts: [String] = []
        if let s = e.season, let n = e.number { parts.append("S\(s)E\(n)") }
        if let t = e.name, !t.isEmpty { parts.append("“\(t)”") }
        let head = parts.isEmpty ? "Next episode" : parts.joined(separator: " ")
        guard let day = e.airdateDay else { return "\(head) — air date not recorded" }
        return "\(head) — \(dayFormatter.string(from: day))"
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

    public static func seasons(_ n: Int?) -> String {
        guard let n else { return "Seasons not recorded" }
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
