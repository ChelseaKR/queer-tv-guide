import Foundation

/// Plans the optional local reminders for favorite shows' next episodes:
/// which to set, when, and what each says. Pure, so tests cover every rule;
/// the app hands the plan to the system's local notification scheduler and
/// nothing leaves the device.
///
/// A reminder carries a show's title, an episode's season and number, and
/// the data's date. Never an episode name (a title can give an ending away
/// on a lock screen) and never anything about a death: nothing here reads
/// death data at all.
public enum EpisodeReminders {
    /// Every reminder's identifier starts with this, so the app replaces its
    /// own and touches nothing else.
    public static let identifierPrefix = "episode-reminder."
    /// iOS keeps at most 64 pending local notifications per app; the plan
    /// keeps the soonest 60.
    public static let limit = 60
    /// When an episode has an air date but no air time, its reminder comes
    /// at this hour, local time, on that date.
    public static let fallbackHour = 10

    public struct Planned: Equatable, Sendable {
        public let identifier: String
        public let showID: Show.ID
        public let fireDate: Date
        public let title: String
        public let body: String
    }

    /// The reminders to set for the favorite shows (ids, any order) as of
    /// `now`. Episodes already aired, undated, or on shows with an unknown
    /// or empty schedule get none.
    public static func plan(favoriteShowIDs: [Show.ID], snapshot: Snapshot, now: Date, calendar: Calendar = .current, limit: Int = EpisodeReminders.limit) -> [Planned] {
        var seen: Set<Show.ID> = []
        var planned: [Planned] = []
        for id in favoriteShowIDs where seen.insert(id).inserted {
            guard let show = snapshot.show(id: id),
                  show.schedule.scheduleKnown,
                  let episode = show.schedule.nextEpisode,
                  let fire = fireDate(for: episode, calendar: calendar),
                  fire > now
            else { continue }
            planned.append(Planned(
                identifier: "\(identifierPrefix)\(show.id).\(episode.tvmazeID)",
                showID: show.id,
                fireDate: fire,
                title: show.title,
                body: body(for: episode, atAirTime: airstampDate(episode) != nil, generatedAt: snapshot.generatedAt)
            ))
        }
        planned.sort { $0.fireDate != $1.fireDate ? $0.fireDate < $1.fireDate : $0.identifier < $1.identifier }
        return Array(planned.prefix(limit))
    }

    /// The broadcast time when TVmaze records one (`airstamp`); otherwise
    /// `fallbackHour` local time on the air date; `nil` with neither.
    static func fireDate(for episode: Episode, calendar: Calendar) -> Date? {
        if let date = airstampDate(episode) {
            return date
        }
        guard let airdate = episode.airdate else { return nil }
        let parts = airdate.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        return calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2], hour: fallbackHour))
    }

    static func airstampDate(_ episode: Episode) -> Date? {
        episode.airstamp.flatMap { airstampFormatter.date(from: $0) }
    }

    /// "S23E1 is listed to air now. Schedule from TVmaze, data as of Sep 18;
    /// it may have changed." A reminder set from an air date alone says
    /// "today" instead of "now".
    static func body(for episode: Episode, atAirTime: Bool, generatedAt: Date) -> String {
        let episodeCode = episode.season.flatMap { s in episode.number.map { "S\(s)E\($0)" } } ?? "A new episode"
        let when = atAirTime ? "to air now" : "for today"
        return "\(episodeCode) is listed \(when). Schedule from TVmaze, data as of \(dataDay.string(from: generatedAt)); it may have changed."
    }

    /// `airstamp` is ISO 8601 with an offset ("2026-10-16T02:00:00+00:00").
    static let airstampFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static let dataDay: DateFormatter = {
        let f = DateFormatter()
        f.setLocalizedDateFormatFromTemplate("MMMd")
        return f
    }()
}
