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
///
/// Date only unless the air time is real. A reminder fires at the broadcast
/// instant only when TVmaze records an air time (`Episode.airInstant`). For
/// every other episode TVmaze gives a date and nothing else (its `airstamp`
/// is then a placeholder, not a time), so the reminder comes at
/// `fallbackHour` local time on that date, and its words give the date and
/// say no air time is listed. That hour is a delivery time, never a claim
/// about when the episode airs.
public enum EpisodeReminders {
    /// Every reminder's identifier starts with this, so the app replaces its
    /// own and touches nothing else.
    public static let identifierPrefix = "episode-reminder."
    /// iOS keeps at most 64 pending local notifications per app; the plan
    /// keeps the soonest 60.
    public static let limit = 60
    /// When an episode has an air date but no recorded air time, its
    /// reminder is delivered at this hour, local time, on that date. It is
    /// when the reminder arrives, not when the episode airs.
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
                body: body(for: episode, fireDate: fire, calendar: calendar, generatedAt: snapshot.generatedAt)
            ))
        }
        planned.sort { $0.fireDate != $1.fireDate ? $0.fireDate < $1.fireDate : $0.identifier < $1.identifier }
        return Array(planned.prefix(limit))
    }

    /// The broadcast instant when TVmaze records an air time
    /// (`Episode.airInstant`); otherwise `fallbackHour` local time on the air
    /// date; `nil` with neither. A placeholder `airstamp` (no air time) is
    /// never used: only `airInstant` reads it.
    static func fireDate(for episode: Episode, calendar: Calendar) -> Date? {
        if let instant = episode.airInstant {
            return instant
        }
        guard let airdate = episode.airdate else { return nil }
        let parts = airdate.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        return calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2], hour: fallbackHour))
    }

    /// With a real air time: "S23E1 is listed to air now. Schedule from
    /// TVmaze, data as of Sep 18; it may have changed."
    ///
    /// With a date only, it gives the date and says there is no air time:
    /// "S23E1 is listed for Sep 21, the network's date, with no air time.
    /// Schedule from TVmaze, ...". The date is TVmaze's, in the network's
    /// time zone, so it never says "today" (in another time zone the
    /// episode can air the next day) and never gives a time.
    static func body(for episode: Episode, fireDate: Date, calendar: Calendar, generatedAt: Date) -> String {
        let episodeCode = episode.season.flatMap { s in episode.number.map { "S\(s)E\($0)" } } ?? "A new episode"
        let listed: String
        if episode.airInstant != nil {
            listed = "is listed to air now"
        } else {
            // `fireDate` is `fallbackHour` on the air date in `calendar`, so
            // formatting it in that calendar's zone gives the air date back.
            let day = DateFormatter()
            day.calendar = calendar
            day.timeZone = calendar.timeZone
            day.setLocalizedDateFormatFromTemplate("MMMd")
            listed = "is listed for \(day.string(from: fireDate)), the network's date, with no air time"
        }
        return "\(episodeCode) \(listed). Schedule from TVmaze, data as of \(dataDay.string(from: generatedAt)); it may have changed."
    }

    static let dataDay: DateFormatter = {
        let f = DateFormatter()
        f.setLocalizedDateFormatFromTemplate("MMMd")
        return f
    }()
}
