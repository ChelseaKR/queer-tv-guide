import Foundation

/// What the app must credit, and where, per each source's terms
/// (docs/LICENSES-AND-ATTRIBUTION.md; audit in DECISIONS 0012):
///
/// - LezWatch.TV's terms: "link back to us, or note us by name". Every show
///   and character screen links to its LezWatch.TV page (`sourceURL`), and
///   the About screen names LezWatch.TV with a link.
/// - TVmaze's API licence is CC BY-SA 4.0, and attribution is met "by linking
///   back to TVmaze from within your application". Wherever a TVmaze
///   schedule or episode is shown, a TVmaze link and the CC BY-SA 4.0 licence
///   link are shown with it.
///
/// Every URL comes from the snapshot itself, so no host other than the
/// snapshot host appears in the app's source (SourceTreeGuardTests).
public enum Attribution {
    public static let lezWatchSource = "lezwatch"
    public static let tvmazeSource = "tvmaze"

    /// Shown on the About screen whatever the snapshot's own text says.
    public static let nonEndorsement = "LezWatch.TV and TVmaze do not endorse this app."

    public static let lezWatchLinkTitle = "View on LezWatch.TV"

    /// The VoiceOver label for a record's LezWatch.TV link: names the record,
    /// so a list of these links is not "View on LezWatch.TV" repeated.
    public static func lezWatchLinkLabel(for name: String) -> String {
        "View \(name) on LezWatch.TV"
    }

    public struct Link: Equatable, Sendable {
        public let title: String
        public let url: URL
    }

    /// The TVmaze credit to show next to TVmaze data.
    public struct TVmazeCredit: Equatable, Sendable {
        /// The show's own TVmaze page when known, else TVmaze itself.
        public let source: Link
        /// The CC BY-SA 4.0 licence.
        public let licence: Link
        /// For VoiceOver and for tests: the whole credit as one sentence.
        public var spoken: String { "\(source.title), licensed \(licence.title)." }
    }

    /// The credit for a show's schedule, or `nil` when there is no TVmaze
    /// data to credit (the show was never matched), or the snapshot lacks a
    /// TVmaze attribution entry.
    public static func tvmazeCredit(for schedule: Schedule, in snapshot: Snapshot) -> TVmazeCredit? {
        guard schedule.scheduleKnown else { return nil }
        return tvmazeCredit(in: snapshot, showPage: schedule.tvmazeURL)
    }

    /// The general TVmaze credit (e.g. under a list mixing several shows'
    /// episodes), linking TVmaze itself.
    public static func tvmazeCredit(in snapshot: Snapshot, showPage: URL? = nil) -> TVmazeCredit? {
        guard let item = snapshot.attribution(for: tvmazeSource) else { return nil }
        return TVmazeCredit(
            source: Link(title: "Schedule data from TVmaze", url: showPage ?? item.url),
            licence: Link(title: item.licenceName, url: item.licenceURL)
        )
    }
}

extension Snapshot {
    public func attribution(for source: String) -> AttributionItem? {
        attribution.first { $0.source == source }
    }
}
